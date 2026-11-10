"""Prepare the Assignment 3 evidence sites for the MapLibre tutorial.

The source GeoPackage is kept in its original EPSG:2263 CRS. Polygon and
centroid GeoJSON files are exported in EPSG:4326, which web maps require.
"""

from pathlib import Path

import geopandas as gpd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parents[1] / "assignment03/data/processed/vacancy_vegetation_2022.gpkg"
OUTPUT = ROOT / "public/data"

DURATION_COLORS = {
    "long-open by 1996": "#3e5848",
    "cleared between 1996 and 2018": "#b27855",
}


def vegetation_class(value: float) -> str:
    if value < 20:
        return "under 20 percent"
    if value < 50:
        return "20 to under 50 percent"
    if value < 80:
        return "50 to under 80 percent"
    return "80 percent or more"


gdf = gpd.read_file(SOURCE)

fields = [
    "sample_id",
    "bbl",
    "address",
    "lotarea",
    "duration_group",
    "evidence_years",
    "veg_pct",
    "ndvi_mean",
    "qa_note",
    "geometry",
]
gdf = gdf[fields].copy()

gdf["duration_color"] = gdf["duration_group"].map(DURATION_COLORS)
gdf["archive_evidence"] = gdf["duration_group"].map({
    "long-open by 1996": "open ground in 1996 and 2018",
    "cleared between 1996 and 2018": "building visible in 1996; open ground in 2018",
})
gdf["current_record"] = "classified vacant in PLUTO 26v2 - 2026 administrative record"
gdf["vegetation_class"] = gdf["veg_pct"].map(vegetation_class)
gdf["veg_pct"] = gdf["veg_pct"].round(1)
gdf["ndvi_mean"] = gdf["ndvi_mean"].round(3)
gdf["lotarea"] = gdf["lotarea"].round().astype(int)

if gdf["duration_color"].isna().any():
    unknown = sorted(gdf.loc[gdf["duration_color"].isna(), "duration_group"].unique())
    raise ValueError(f"Unmapped duration groups: {unknown}")

OUTPUT.mkdir(parents=True, exist_ok=True)

polygons = gdf.to_crs(4326)
polygons.to_file(OUTPUT / "temporary_forest_parcels.geojson", driver="GeoJSON")

# Calculate centroids in the projected source CRS, then transform the points.
sites = gdf.copy()
sites["geometry"] = sites.geometry.centroid
sites = sites.to_crs(4326)
sites.to_file(OUTPUT / "temporary_forest_sites.geojson", driver="GeoJSON")

print(f"Exported {len(polygons)} polygons and {len(sites)} centroids in {polygons.crs}.")
print(f"Vegetation range: {polygons.veg_pct.min():.1f} to {polygons.veg_pct.max():.1f} percent.")
