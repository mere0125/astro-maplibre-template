#!/usr/bin/env python3
"""Prepare source-backed data and real aerial-image excerpts for Assignment 4.

Run with the existing course workspace retained alongside this repository:
    /opt/anaconda3/bin/python3 scripts/prepare_assignment04_data.py

No original datasets are modified. The fourteen parcel measurements are copied
at their original precision, not estimated from the web display or screenshots.
The 254-parcel context is the exact original screening set used in Assignment 3.
"""

from __future__ import annotations

import hashlib
import json
import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
from PIL import Image, ImageDraw
from pyproj import Transformer
from shapely.ops import transform as transform_geometry
import tifffile


REPO = Path(__file__).resolve().parents[1]
WORKSPACE = REPO.parents[1]
DATA = REPO / "public/data/assignment04"
IMAGES = REPO / "public/images/assignment04"
PARCEL_SOURCE = WORKSPACE / "assignment03/data/processed/vacancy_vegetation_2022.gpkg"
SCREEN_SOURCE = WORKSPACE / "assignment03/data/original/vacant_lots_current_mappluto26v2.gpkg"
CITY_SOURCE = REPO / "public/data/nyc_vacant_land_26v2.geojson"
ORIGINAL_NAIP = WORKSPACE / "assignment03/data/original/naip_2022_east_new_york_4band.tif"

HISTORY = {
    "long-open by 1996": {
        "group": "open_in_both",
        "label": "Open in 1996 and 2018",
        "color": "#42634d",
    },
    "cleared between 1996 and 2018": {
        "group": "built_then_open",
        "label": "Built in 1996, open in 2018",
        "color": "#b47e60",
    },
}
BOROUGH_NAMES = {"MN": "Manhattan", "BX": "Bronx", "BK": "Brooklyn", "QN": "Queens", "SI": "Staten Island"}
VEGETATION_COLORS = ["#eee6cc", "#cbd8b7", "#98b487", "#4c7257"]
IMAGE_SIZE = 512
CONTEXT_SIDE_FEET = 450.0


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")


def export_geojson(frame: gpd.GeoDataFrame, filename: str, precision: int = 7) -> None:
    # GeoPandas emits RFC 7946 WGS84 coordinates. Feature IDs are stable BBLs.
    value = json.loads(frame.to_crs(4326).to_json(drop_id=True))

    def rounded(coordinates):
        if isinstance(coordinates, list):
            return [rounded(item) for item in coordinates]
        return round(coordinates, precision) if isinstance(coordinates, float) else coordinates

    for feature in value["features"]:
        if feature["properties"].get("bbl"):
            feature["id"] = str(feature["properties"]["bbl"])
        if precision == 6 and feature["geometry"]:
            feature["geometry"]["coordinates"] = rounded(feature["geometry"]["coordinates"])
    write_json(DATA / filename, value)


def raster_source(path: Path) -> dict:
    with tifffile.TiffFile(path) as source:
        metadata = source.geotiff_metadata
        channels = source.pages[0].shape[-1]
        if channels == 3:
            # Pillow uses the installed libtiff JPEG decoder. This avoids
            # requiring an extra imagecodecs package for the archival TIFFs.
            array = np.asarray(Image.open(path).convert("RGB"))
        else:
            array = source.asarray()
    if int(metadata["ProjectedCSTypeGeoKey"]) != 3857:
        raise ValueError(f"Expected EPSG:3857 image, received {path}")
    scale_x, scale_y, _ = metadata["ModelPixelScale"]
    tie = metadata["ModelTiepoint"]
    return {"path": path, "array": array, "left": tie[3], "top": tie[4], "scale_x": scale_x, "scale_y": scale_y}


def image_extent(source: dict, bounds: list[float]) -> tuple[float, float, float, float]:
    left, bottom, right, top = bounds
    return (
        (left - source["left"]) / source["scale_x"],
        (source["top"] - top) / source["scale_y"],
        (right - source["left"]) / source["scale_x"],
        (source["top"] - bottom) / source["scale_y"],
    )


def draw_boundary(image: Image.Image, geometry_3857, bounds: list[float]) -> None:
    left, bottom, right, top = bounds
    draw = ImageDraw.Draw(image)
    polygons = list(geometry_3857.geoms) if geometry_3857.geom_type == "MultiPolygon" else [geometry_3857]
    for polygon in polygons:
        for ring in [polygon.exterior, *polygon.interiors]:
            points = [((x-left)/(right-left)*IMAGE_SIZE, (top-y)/(top-bottom)*IMAGE_SIZE) for x, y in ring.coords]
            draw.line(points, fill="#243f2d", width=5, joint="curve")
            draw.line(points, fill="#fff4c3", width=2, joint="curve")


def crop_image(source: dict, bounds: list[float], geometry, destination: Path, ndvi: bool = False, render: bool = True) -> dict:
    extent = image_extent(source, bounds)
    height, width = source["array"].shape[:2]
    complete = extent[0] >= 0 and extent[1] >= 0 and extent[2] <= width and extent[3] <= height
    if not complete:
        raise ValueError(f"Context crop falls outside retained source coverage: {destination.name}")
    if not render and destination.exists():
        return {"file": "/images/assignment04/" + destination.name, "width": IMAGE_SIZE, "height": IMAGE_SIZE, "coverage_complete": complete}
    array = source["array"]
    if ndvi and "ndvi_image" not in source:
        red = array[:, :, 0].astype(np.float32)
        nir = array[:, :, 3].astype(np.float32)
        denominator = nir + red
        values = np.divide(nir-red, denominator, out=np.full_like(red, -1), where=denominator > 0)
        # A continuous display stretch from -0.2 to 0.8; this is a display
        # palette only. The analysed vegetation percentage uses NDVI > 0.20.
        stops = np.array([-0.2, 0.2, 0.4, 0.6, 0.8])
        colors = np.array([[225, 218, 201], [212, 220, 194], [157, 181, 141], [91, 133, 94], [38, 83, 57]])
        rgb = np.stack([np.interp(values, stops, colors[:, channel]) for channel in range(3)], axis=-1).astype(np.uint8)
        source["ndvi_image"] = Image.fromarray(rgb)
    if ndvi:
        result = source["ndvi_image"].transform((IMAGE_SIZE, IMAGE_SIZE), Image.Transform.EXTENT, extent, resample=Image.Resampling.NEAREST)
    else:
        base = Image.fromarray(array[:, :, :3])
        result = base.transform((IMAGE_SIZE, IMAGE_SIZE), Image.Transform.EXTENT, extent, resample=Image.Resampling.BILINEAR)
    draw_boundary(result, geometry, bounds)
    result.save(destination, format="WEBP", quality=91, method=6)
    return {"file": "/images/assignment04/" + destination.name, "width": IMAGE_SIZE, "height": IMAGE_SIZE, "coverage_complete": complete}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-images", action="store_true", help="Reuse already generated image files while refreshing dataset metadata")
    args = parser.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)
    IMAGES.mkdir(parents=True, exist_ok=True)

    city = gpd.read_file(CITY_SOURCE)
    null_count = sum(geometry is None for geometry in city.geometry)
    empty_count = sum(geometry is not None and geometry.is_empty for geometry in city.geometry)
    mapped = city.loc[[geometry is not None and not geometry.is_empty for geometry in city.geometry]].copy()
    if (len(city), null_count, empty_count, len(mapped)) != (24663, 423, 27, 24213):
        raise ValueError("Unexpected PLUTO snapshot counts; investigate before publishing")

    screen = gpd.read_file(SCREEN_SOURCE)
    parcels = gpd.read_file(PARCEL_SOURCE)
    if (len(screen), len(parcels)) != (254, 14):
        raise ValueError("Unexpected original screening or analytical sample count")
    screen["bbl"] = screen["bbl"].astype(str)
    parcels["bbl"] = parcels["bbl"].astype(str)
    if not set(parcels.bbl).issubset(set(screen.bbl)):
        raise ValueError("Analysed sample must be a subset of the original screening set")
    if parcels.bbl.duplicated().any() or screen.bbl.duplicated().any():
        raise ValueError("BBL keys must be unique")

    mapped["bbl"] = mapped.bbl.astype(str)
    mapped["borough_name"] = mapped.borough.map(BOROUGH_NAMES)
    mapped["administrative_status"] = "Vacant land - PLUTO land-use code 11"
    city_fields = ["bbl", "borough", "borough_name", "geometry"]
    export_geojson(mapped[city_fields], "citywide.geojson", precision=6)

    city_centers = mapped.to_crs(2263)
    city_centers["geometry"] = city_centers.geometry.representative_point()
    export_geojson(city_centers[city_fields], "citywide_sites.geojson", precision=6)

    screen["administrative_status"] = "Vacant land - MapPLUTO 26v2, 2026"
    export_geojson(screen[["bbl", "address", "lotarea", "administrative_status", "geometry"]], "screening.geojson")

    parcels["confidence_1996"] = parcels.interpretation_confidence
    parcels["history_group"] = parcels.duration_group.map(lambda value: HISTORY[value]["group"])
    parcels["history_label"] = parcels.duration_group.map(lambda value: HISTORY[value]["label"])
    parcels["history_color"] = parcels.duration_group.map(lambda value: HISTORY[value]["color"])
    parcels["veg_class"] = parcels.veg_pct.map(lambda value: 0 if value < 20 else 1 if value < 50 else 2 if value < 80 else 3)
    parcels["vegetation_color"] = parcels.veg_class.map(lambda value: VEGETATION_COLORS[value])
    parcels["current_status"] = "Classified vacant in MapPLUTO 26v2, 2026"
    parcels["historical_evidence"] = "NYC aerial imagery from 1996 and 2018"
    parcels["vegetation_evidence"] = "2022 NAIP red and near-infrared image bands"
    parcels["evidence_note"] = "Historical snapshots and 2026 administrative status; continuous vacancy is not established"
    fields = ["bbl", "address", "sample_id", "lotarea", "condition_1996", "condition_2018", "confidence_1996", "confidence_2018", "history_group", "history_label", "history_color", "veg_pct", "veg_class", "vegetation_color", "ndvi_mean", "ndvi_median", "pixel_count", "current_status", "historical_evidence", "vegetation_evidence", "evidence_note", "geometry"]
    export_geojson(parcels[fields], "parcels.geojson")
    centers = parcels.copy()
    centers["geometry"] = centers.geometry.representative_point()
    export_geojson(centers[fields], "sites.geojson")

    screen_bounds = list(screen.to_crs(4326).total_bounds)
    sample_bounds = list(parcels.to_crs(4326).total_bounds)
    transform_2263_3857 = Transformer.from_crs(2263, 3857, always_xy=True)
    transform_3857_4326 = Transformer.from_crs(3857, 4326, always_xy=True)

    rasters = {
        "1996": raster_source(WORKSPACE / "assignment02/data/processed/east_new_york_1996_georef.tif"),
        "2018": raster_source(WORKSPACE / "assignment02/data/processed/east_new_york_2018_georef.tif"),
        "2022": raster_source(ORIGINAL_NAIP),
    }
    imagery = {}
    for _, parcel in parcels.iterrows():
        center = parcel.geometry.centroid
        radius = CONTEXT_SIDE_FEET / 2
        bounds = list(transform_2263_3857.transform_bounds(center.x-radius, center.y-radius, center.x+radius, center.y+radius))
        geometry = transform_geometry(transform_2263_3857.transform, parcel.geometry)
        bbl = parcel.bbl
        records = {}
        for year in ["1996", "2018", "2022"]:
            records[year] = crop_image(rasters[year], bounds, geometry, IMAGES / f"{bbl}_{year}.webp", render=not args.skip_images)
        records["ndvi"] = crop_image(rasters["2022"], bounds, geometry, IMAGES / f"{bbl}_2022_ndvi.webp", ndvi=True, render=not args.skip_images)
        records["bounds_3857"] = bounds
        records["bounds_4326"] = list(transform_3857_4326.transform_bounds(*bounds))
        records["ground_context_side_feet"] = CONTEXT_SIDE_FEET
        records["boundary_note"] = "Pale line traces the current tax-lot boundary; it does not reconstruct historical ownership boundaries"
        imagery[bbl] = records

    group_summaries = []
    for key, label in [("open_in_both", "Open in 1996 and 2018"), ("built_then_open", "Built in 1996, open in 2018")]:
        group = parcels[parcels.history_group == key]
        group_summaries.append({"id": key, "label": label, "parcels": len(group), "median_veg_pct": float(group.veg_pct.median()), "median_parcel_median_ndvi": float(group.ndvi_median.median()), "min_veg_pct": float(group.veg_pct.min()), "max_veg_pct": float(group.veg_pct.max())})

    boroughs = []
    for code, name in BOROUGH_NAMES.items():
        all_records = city[city.borough == code]
        drawn = mapped[mapped.borough == code]
        boroughs.append({"code": code, "name": name, "records": len(all_records), "mapped": len(drawn), "not_mapped": len(all_records)-len(drawn), "bounds": list(drawn.total_bounds)})

    manifest = {
        "version": "2026-11-10",
        "project": "The Temporary Forest",
        "author": "Mere Cui",
        "dataset_version": "PLUTO and MapPLUTO 26v2",
        "counts": {"city_records": len(city), "city_mapped": len(mapped), "city_null": null_count, "city_empty": empty_count, "screening": len(screen), "samples": len(parcels)},
        "boroughs": boroughs,
        "group_summaries": group_summaries,
        "bounds": {"citywide": list(mapped.total_bounds), "screening": screen_bounds, "sample": sample_bounds},
        "crs": {"web_data": "EPSG:4326", "original_parcels": "EPSG:2263 - NAD83 New York Long Island, US survey feet", "image_grid": "EPSG:3857 - Web Mercator"},
        "method": {"ndvi_formula": "(near infrared - red) / (near infrared + red)", "red_band": 1, "near_infrared_band": 4, "vegetation_threshold": 0.20, "vegetation_comparison": "strictly greater than", "percentage_denominator": "valid raster pixels assigned to each current parcel using GDAL ALL_TOUCHED rasterisation", "display_classes": [{"minimum": 0, "maximum_exclusive": 20, "label": "Under 20%", "color": VEGETATION_COLORS[0]}, {"minimum": 20, "maximum_exclusive": 50, "label": "20% to under 50%", "color": VEGETATION_COLORS[1]}, {"minimum": 50, "maximum_exclusive": 80, "label": "50% to under 80%", "color": VEGETATION_COLORS[2]}, {"minimum": 80, "maximum_inclusive": 100, "label": "80% or more", "color": VEGETATION_COLORS[3]}]},
        "sources": [
            {"id": "pluto", "label": "NYC Department of City Planning - PLUTO and MapPLUTO 26v2", "url": "https://www.nyc.gov/content/planning/pages/resources/datasets/mappluto-pluto-change", "year": 2026, "role": "Citywide vacant-land classification and lot attributes"},
            {"id": "tax_lots", "label": "NYC Department of Finance - current tax-lot geometry", "url": "https://www.nyc.gov/assets/finance/jump/digitaxmaps.html", "role": "Original 254-lot screening and fourteen parcel geometries"},
            {"id": "aerial_1996", "label": "NYC OTI - 1996 aerial photography", "url": "https://maps.nyc.gov/tms/1.0.0/photo/1996/", "year": 1996, "role": "Interpretive historical built or open condition"},
            {"id": "aerial_2018", "label": "NYC OTI - 2018 orthophotography", "url": "https://maps.nyc.gov/tms/1.0.0/photo/2018/", "year": 2018, "role": "Interpretive historical built or open condition"},
            {"id": "naip", "label": "USDA NAIP - New York 2022 imagery", "url": "https://imagery.geoplatform.gov/iipp/rest/services/NAIP/NAIP_plus/ImageServer", "year": 2022, "catalog_ids": [391364, 391366, 392276, 392277], "role": "RGB context and near-infrared vegetation response"},
        ],
        "limitations": ["The fourteen parcels are a purposive sample selected from the original thirty-six archival cases, not a random sample of New York City", "1996 and 2018 are historical snapshots; neither continuous vacancy nor an exact clearance date is established", "2026 vacancy comes from an administrative land-use classification, not a 2026 image", "2022 NDVI response does not establish current vegetation, tree canopy, forest status, habitat quality or biodiversity", "Current tax-lot boundaries are used retrospectively and may differ from historical parcel boundaries", "The NDVI threshold of 0.20 is exploratory, not a universal ecological boundary", "Citywide geometry was simplified by two US survey feet for the web context; fourteen analytical parcels retain their source geometry"],
        "interpretation": "The two small groups have nearly equal median vegetation response. These observations do not support a simple claim that earlier observed vacancy produces more vegetation.",
        "imagery": imagery,
        "images": {bbl: {"1996": item["1996"]["file"], "2018": item["2018"]["file"], "2022_rgb": item["2022"]["file"], "2022_ndvi": item["ndvi"]["file"]} for bbl, item in imagery.items()},
        "image_bounds": {bbl: {"epsg3857": item["bounds_3857"], "epsg4326": item["bounds_4326"], "ground_context_side_feet": CONTEXT_SIDE_FEET} for bbl, item in imagery.items()},
        "image_display": {"context_side_feet": CONTEXT_SIDE_FEET, "size_pixels": IMAGE_SIZE, "rgb_resampling": "bilinear for display only", "ndvi_resampling": "nearest neighbour for display only", "ndvi_palette_stops": [-0.2, 0.2, 0.4, 0.6, 0.8], "ndvi_palette": [{"value": -0.2, "color": "#e1dac9"}, {"value": 0.2, "color": "#d4dcc2"}, {"value": 0.4, "color": "#9db58d"}, {"value": 0.6, "color": "#5b855e"}, {"value": 0.8, "color": "#265339"}], "ndvi_display_min": -0.2, "ndvi_display_max": 0.8, "ndvi_display_clipping": "Values below -0.2 and above 0.8 use the end colours; values are unchanged in the underlying raster", "measurement_source": "full retained NAIP raster, not these display crops"},
        "lineage": {"citywide_source_sha256": sha256(CITY_SOURCE), "screening_source_sha256": sha256(SCREEN_SOURCE), "parcel_source_sha256": sha256(PARCEL_SOURCE), "naip_source_sha256": sha256(ORIGINAL_NAIP), "screening_membership": "Exact original Assignment 3 set, selected by BBL and copied without reconstructing a study window", "measurement_precision": "Original numerical precision retained in GeoJSON; interface may round for readability"},
    }
    write_json(DATA / "manifest.json", manifest)
    print(json.dumps({"counts": manifest["counts"], "imagery_sets": len(imagery), "group_summaries": group_summaries}, indent=2))


if __name__ == "__main__":
    main()
