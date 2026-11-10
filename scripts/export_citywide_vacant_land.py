#!/usr/bin/env python3
"""Prepare the two context scales used by the interactive map.

Input is PLUTO/MapPLUTO release 26v2 as GeoParquet.  The source file used for
this build is the `nyc_pluto.parquet` file distributed by the open-source
`nycpluto` package, which reproduces NYC Department of City Planning's 26v2
release and preserves the MapPLUTO lot polygons.

Only tax lots with PLUTO LandUse code 11 (Vacant Land) are exported.  The
East New York screening set is the exact 5,540 x 5,327 ft window used in the
earlier QGIS assignments; 254 of the current vacant lots fall wholly inside.
The fourteen parcels with historical and NDVI evidence are exported by the
separate `export_temporary_forest_web_data.py` script.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
from shapely.geometry import box


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "data"

# This is the analysis window used to create the Assignment 2/3 sample, in
# NAD83 / New York Long Island (ftUS), EPSG:2263.
STUDY_BOUNDS_2263 = (
    1_013_383.05766554,
    181_589.61744812,
    1_018_923.38789672,
    186_917.06596741,
)

BOROUGH_NAMES = {
    "MN": "Manhattan",
    "BX": "Bronx",
    "BK": "Brooklyn",
    "QN": "Queens",
    "SI": "Staten Island",
}


def write_geojson(frame: gpd.GeoDataFrame, destination: Path) -> None:
    frame.to_file(
        destination,
        driver="GeoJSON",
        engine="pyogrio",
        coordinate_precision=6,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="PLUTO 26v2 GeoParquet")
    args = parser.parse_args()

    lots = gpd.read_parquet(
        args.source,
        columns=["borough", "bbl", "address", "lotarea", "landuse", "geometry"],
        filters=[("landuse", "=", "11")],
    )
    if lots.crs.to_epsg() != 2263:
        raise ValueError(f"Expected EPSG:2263, received {lots.crs}")

    lots = lots[["borough", "bbl", "address", "lotarea", "geometry"]].copy()
    lots["borough_name"] = lots["borough"].map(BOROUGH_NAMES)
    lots["map_role"] = "NYC vacant tax lot - PLUTO land-use code 11"

    # A two-foot simplification is below the line weight at citywide web-map
    # scale, while reducing the download from the full tax-lot geometry.
    citywide = lots.copy()
    citywide["geometry"] = citywide.geometry.simplify(2, preserve_topology=True)
    citywide = citywide.to_crs(4326)

    study_window = box(*STUDY_BOUNDS_2263)
    screened = lots[lots.within(study_window)].copy().to_crs(4326)
    screened["map_role"] = "East New York screening set"

    window = gpd.GeoDataFrame(
        {
            "name": ["East New York field-study window"],
            "description": [
                "254 current vacant lots were screened here; 14 comparable lots "
                "have historical imagery and 2022 vegetation measurements."
            ],
        },
        geometry=[study_window],
        crs=2263,
    ).to_crs(4326)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_geojson(citywide, OUT_DIR / "nyc_vacant_land_26v2.geojson")
    write_geojson(screened, OUT_DIR / "east_new_york_screening_lots.geojson")
    write_geojson(window, OUT_DIR / "east_new_york_study_window.geojson")

    print(f"Citywide vacant lots: {len(citywide):,}")
    print(f"East New York screening set: {len(screened):,}")


if __name__ == "__main__":
    main()
