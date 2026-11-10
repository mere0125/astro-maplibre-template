#!/usr/bin/env python3
"""Render fourteen source-backed parcel specimens at one projected ground scale.

Run with the retained course-workspace inputs:
    /opt/anaconda3/bin/python3 scripts/prepare_assignment04_specimens.py

These are display renderings of real 2022 NAIP RGB values. They do not create
vegetation, change a parcel measurement, or increase source image resolution.
Only this script, its PNG outputs, specimens.json and field_register.csv are written.
"""

from __future__ import annotations

import hashlib
import csv
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image
from pyproj import Transformer
from shapely import contains_xy
from shapely.geometry import shape
from shapely.ops import transform as transform_geometry
import tifffile


REPO = Path(__file__).resolve().parents[1]
WORKSPACE = REPO.parents[1]
PARCELS = REPO / "public/data/assignment04/parcels.geojson"
SOURCE = WORKSPACE / "assignment03/data/original/naip_2022_east_new_york_4band.tif"
OUTPUT = REPO / "public/images/assignment04/specimens"
MANIFEST = REPO / "public/data/assignment04/specimens.json"
REGISTER = REPO / "public/data/assignment04/field_register.csv"
IMAGE_WIDTH = 700
MINIMUM_MARGIN_FEET = 20.0
SCALE_BAR_FEET = 50.0


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def polygon_rings(geometry):
    polygons = list(geometry.geoms) if geometry.geom_type == "MultiPolygon" else [geometry]
    for polygon in polygons:
        yield polygon.exterior
        yield from polygon.interiors


def svg_path(geometry, left: float, top: float, extent: float, units: float) -> str:
    """Use the same grid transform as the PNG, including polygon holes."""
    paths = []
    for ring in polygon_rings(geometry):
        coordinates = list(ring.coords)
        points = [((x - left) / extent * units, (top - y) / extent * units) for x, y in coordinates[:-1]]
        paths.append("M" + "L".join(f"{x:.8f},{y:.8f}" for x, y in points) + "Z")
    return "".join(paths)


def bilinear_rgb(source: np.ndarray, column: np.ndarray, row: np.ndarray) -> np.ndarray:
    """Sample unmodified RGB bands, with no contrast stretch or colour ramp."""
    x0 = np.floor(column).astype(np.int32)
    y0 = np.floor(row).astype(np.int32)
    x1 = x0 + 1
    y1 = y0 + 1
    height, width = source.shape[:2]
    if min(x0.min(), y0.min()) < 0 or x1.max() >= width or y1.max() >= height:
        raise ValueError("Common-scale output extends beyond retained raster coverage")
    dx = (column - x0)[..., None]
    dy = (row - y0)[..., None]
    upper = source[y0, x0, :3].astype(np.float64) * (1 - dx) + source[y0, x1, :3] * dx
    lower = source[y1, x0, :3].astype(np.float64) * (1 - dx) + source[y1, x1, :3] * dx
    return np.clip(np.rint(upper * (1 - dy) + lower * dy), 0, 255).astype(np.uint8)


def main() -> None:
    geojson = json.loads(PARCELS.read_text())
    features = geojson["features"]
    keys = [str(feature["properties"]["bbl"]) for feature in features]
    if len(features) != 14 or len(set(keys)) != 14:
        raise ValueError("Expected the exact fourteen unique analytical parcels")

    to_ground = Transformer.from_crs(4326, 2263, always_xy=True)
    to_image = Transformer.from_crs(2263, 3857, always_xy=True)
    geometries = [transform_geometry(to_ground.transform, shape(feature["geometry"])) for feature in features]
    if not all(geometry.is_valid and not geometry.is_empty for geometry in geometries):
        raise ValueError("Parcel geometries must be valid and nonempty")

    # Center on the projected area centroid. The common extent adds forty
    # feet to the widest bounding-box side and also accommodates any centroid
    # offset in irregular lots. The actual minimum margins are retained below.
    largest_bbox_side = max(max(g.bounds[2] - g.bounds[0], g.bounds[3] - g.bounds[1]) for g in geometries)
    largest_centered_side = max(
        2 * max(g.centroid.x - g.bounds[0], g.bounds[2] - g.centroid.x, g.centroid.y - g.bounds[1], g.bounds[3] - g.centroid.y)
        for g in geometries
    )
    common_extent = float(math.ceil(max(largest_bbox_side + 2 * MINIMUM_MARGIN_FEET, largest_centered_side) / 50.0) * 50.0)

    with tifffile.TiffFile(SOURCE) as handle:
        metadata = handle.geotiff_metadata
        source = handle.asarray()
    if int(metadata["ProjectedCSTypeGeoKey"]) != 3857:
        raise ValueError("Expected the retained EPSG:3857 four-band NAIP raster")
    if source.ndim != 3 or source.shape[2] != 4 or source.dtype != np.uint8:
        raise ValueError("Expected four uint8 bands: red, green, blue, near infrared")
    sx, sy, _ = metadata["ModelPixelScale"]
    tie = metadata["ModelTiepoint"]
    raster_left = tie[3] - tie[0] * sx
    raster_top = tie[4] + tie[1] * sy

    OUTPUT.mkdir(parents=True, exist_ok=True)
    entries = {}
    validations = []
    offsets = (np.arange(IMAGE_WIDTH, dtype=np.float64) + 0.5) / IMAGE_WIDTH * common_extent
    for feature, geometry in zip(features, geometries):
        properties = feature["properties"]
        bbl = str(properties["bbl"])
        center = geometry.centroid
        half = common_extent / 2
        left, bottom, right, top = center.x - half, center.y - half, center.x + half, center.y + half
        minimum_margin = min(geometry.bounds[0] - left, geometry.bounds[1] - bottom, right - geometry.bounds[2], top - geometry.bounds[3])
        if minimum_margin <= 0:
            raise ValueError(f"Parcel does not fit completely within common extent: {bbl}")

        grid_x, grid_y = np.meshgrid(left + offsets, top - offsets)
        image_x, image_y = to_image.transform(grid_x, grid_y)
        # GeoTIFF tiepoint references the outer upper-left pixel edge; convert
        # world coordinates to zero-based source pixel-center coordinates.
        column = (image_x - raster_left) / sx - 0.5
        row = (raster_top - image_y) / sy - 0.5
        rgb = bilinear_rgb(source, column, row)
        inside = contains_xy(geometry, grid_x, grid_y)
        if not inside.any():
            raise ValueError(f"Parcel mask is unexpectedly empty: {bbl}")
        alpha = np.where(inside, 255, 0).astype(np.uint8)
        rgba = np.dstack((rgb, alpha))
        # Transparent pixels carry no visible source content. Clearing their
        # unused RGB channels avoids downloading a full invisible aerial crop.
        rgba[~inside, :3] = 0
        destination = OUTPUT / f"{bbl}.png"
        Image.fromarray(rgba, mode="RGBA").save(destination, format="PNG", optimize=True)

        # Verify the written output, not only the arrays used to create it.
        actual = np.asarray(Image.open(destination).convert("RGBA"))
        if not np.array_equal(actual[..., :3][inside], rgb[inside]):
            raise ValueError(f"RGB channels changed while writing output: {bbl}")
        if not np.array_equal(actual[..., 3] > 0, inside):
            raise ValueError(f"PNG transparency differs from exact parcel-center mask: {bbl}")
        if actual.shape != (IMAGE_WIDTH, IMAGE_WIDTH, 4):
            raise ValueError(f"Unexpected PNG dimensions: {bbl}")

        entries[bbl] = {
            "file": f"/images/assignment04/specimens/{bbl}.png",
            "outline_path": svg_path(geometry, left, top, common_extent, IMAGE_WIDTH),
            "normalized_outline_path": svg_path(geometry, left, top, common_extent, 1.0),
            "outline_fill_rule": "evenodd",
            "address": properties["address"],
            "veg_pct": properties["veg_pct"],
            "ndvi_mean": properties["ndvi_mean"],
            "pixel_count": properties["pixel_count"],
            "lotarea": properties["lotarea"],
            "history_group": properties["history_group"],
            "bounds_2263": [left, bottom, right, top],
            "geometry_bounds_2263": list(geometry.bounds),
            "centroid_2263": [center.x, center.y],
            "minimum_margin_feet": minimum_margin,
            "opaque_display_pixels": int(inside.sum()),
            "coverage_complete": True,
            "sha256": sha256(destination),
        }
        validations.append({"bbl": bbl, "inside_pixels": int(inside.sum()), "visible_rgb_max_write_difference": int(np.abs(actual[..., :3][inside].astype(np.int16) - rgb[inside].astype(np.int16)).max()), "minimum_margin_feet": round(minimum_margin, 3)})

    manifest = {
        "version": "2026-11-10",
        "common_extent_feet": common_extent,
        "image_width": IMAGE_WIDTH,
        "image_height": IMAGE_WIDTH,
        "crs": "EPSG:2263",
        "crs_name": "NAD83 New York Long Island - US survey feet",
        "orientation": "Projected grid north up - no per-parcel rotation",
        "centering": "Area centroid of each actual current tax-lot polygon",
        "source_year": 2022,
        "source": "USDA NAIP - retained four-band New York 2022 imagery",
        "source_url": "https://imagery.geoplatform.gov/iipp/rest/services/NAIP/NAIP_plus/ImageServer",
        "catalog_ids": [391364, 391366, 392276, 392277],
        "source_raster_sha256": sha256(SOURCE),
        "source_parcels_sha256": sha256(PARCELS),
        "scale_bar": {"length_feet": SCALE_BAR_FEET, "width_fraction": SCALE_BAR_FEET / common_extent, "width_pixels": SCALE_BAR_FEET / common_extent * IMAGE_WIDTH},
        "svg_viewbox": f"0 0 {IMAGE_WIDTH} {IMAGE_WIDTH}",
        "method": {
            "sampling": "Bilinear interpolation of the original red, green and blue bands at EPSG:2263 output pixel centers transformed into EPSG:3857",
            "colour": "Original RGB values with no colour ramp, contrast stretch, saturation adjustment or synthetic content",
            "mask": "Alpha is 255 exactly where the output pixel center lies inside the actual polygon; zero elsewhere, including holes",
            "transparent_rgb": "Unused RGB channels of fully transparent pixels are zeroed for efficient lossless PNG compression; all visible RGB samples are unchanged",
            "display_pixel_side_feet": common_extent / IMAGE_WIDTH,
            "source_resolution_note": "700 pixels is the display grid size; resampling does not increase the resolution or information in the source imagery",
            "measurement_note": "Original vegetation percentage, mean NDVI and assigned-pixel counts are copied unchanged; these PNGs are not new analytical inputs",
            "outline_note": "SVG outlines and PNG masks use the same source geometry and common projected grid",
        },
        "specimens": entries,
        "validation": {"unique_bbls": len(entries), "all_geometry_fits": True, "all_raster_coverage_complete": True, "all_visible_png_rgb_matches_bilinear_samples": True, "all_alpha_matches_polygon_center_mask": True},
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")) + "\n")
    register_fields = ["bbl", "address", "lotarea", "condition_1996", "condition_2018", "record_year", "imagery_year", "veg_pct", "ndvi_mean", "pixel_count", "ndvi_threshold", "history_group"]
    with REGISTER.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=register_fields)
        writer.writeheader()
        for feature in features:
            p = feature["properties"]
            writer.writerow({key: p[key] for key in ["bbl", "address", "lotarea", "condition_1996", "condition_2018", "veg_pct", "ndvi_mean", "pixel_count", "history_group"]} | {"record_year": 2026, "imagery_year": 2022, "ndvi_threshold": 0.20})
    print(json.dumps({"common_extent_feet": common_extent, "image_width": IMAGE_WIDTH, "scale_bar": manifest["scale_bar"], "validation": manifest["validation"], "parcels": validations}, indent=2))


if __name__ == "__main__":
    main()
