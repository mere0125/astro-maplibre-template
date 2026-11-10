#!/usr/bin/env python3
"""Reduce basemap contrast so the project data remain the visual subject."""

from __future__ import annotations

import json
from pathlib import Path


STYLE = Path(__file__).resolve().parents[1] / "public" / "style.json"


def main() -> None:
    document = json.loads(STYLE.read_text())
    layers = {layer["id"]: layer for layer in document["layers"]}

    layers["background"]["paint"]["background-color"] = "#f4f1e9"
    layers["park"]["paint"]["fill-color"] = "#dce6d7"
    layers["water"]["paint"]["fill-color"] = "#dce7e5"
    layers["building"]["paint"].update(
        {
            "fill-color": "#e6e0d6",
            "fill-outline-color": "#d9d2c8",
            "fill-opacity": 0.72,
        }
    )
    layers["landuse_residential"]["paint"]["fill-opacity"] = 0.18

    for layer in document["layers"]:
        if layer.get("type") == "line" and layer.get("source-layer") == "transportation":
            paint = layer.setdefault("paint", {})
            if "casing" in layer["id"]:
                paint["line-color"] = "#d9d9d3"
                paint["line-opacity"] = 0.58
            elif "inner" in layer["id"]:
                paint["line-color"] = "#fbfaf6"
                paint["line-opacity"] = 0.82
            else:
                paint["line-color"] = "#e7e7e1"
                paint["line-opacity"] = 0.55

    for layer_id in ("highway_name_other", "highway_name_motorway"):
        layer = layers[layer_id]
        layer["paint"]["text-color"] = "#858a82"
        layer["paint"]["text-halo-color"] = "#f7f4ed"
        layer["paint"]["text-halo-width"] = 1.2
        layer["paint"]["text-opacity"] = 0.58
        layer["layout"]["text-size"] = 9
        layer["layout"]["symbol-spacing"] = 470
        layer["layout"]["text-transform"] = "none"

    for layer in document["layers"]:
        if layer.get("type") == "symbol" and layer.get("source-layer") == "place":
            paint = layer.setdefault("paint", {})
            paint["text-color"] = "#677166"
            paint["text-halo-color"] = "#f4f1e9"
            paint["text-opacity"] = 0.72
            layer.setdefault("layout", {})["text-transform"] = "none"

    layers["water_name"]["paint"]["text-color"] = "#829597"
    layers["water_name"]["paint"]["text-opacity"] = 0.62

    STYLE.write_text(json.dumps(document, indent=2) + "\n")


if __name__ == "__main__":
    main()
