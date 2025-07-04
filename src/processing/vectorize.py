#!/usr/bin/env python3
"""vectorize.py — binary burn‑mask ➜ GeoJSON polygons"""
from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import shapes
from shapely.geometry import shape, Polygon
from shapely.validation import make_valid
from skimage.morphology import closing, opening, square

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class Config:
    mask_tif: Path
    out_geojson: Path
    clean: bool = True # This is the morphological clean (opening/closing)

    def __post_init__(self) -> None:  # normalise paths
        object.__setattr__(self, "mask_tif", Path(self.mask_tif))
        object.__setattr__(self, "out_geojson", Path(self.out_geojson))


# ───────────────────────── I/O helpers ──────────────────────────

def _load_mask(path: Path):
    with rasterio.open(path) as src:
        return src.read(1, out_dtype=np.uint8), src.transform, src.crs


def _write_gdf(gdf: gpd.GeoDataFrame, out_: Path) -> None:
    out_.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(out_, driver="GeoJSON")


# ────────────────────── geometry generation ─────────────────────

def _clean(mask: np.ndarray) -> np.ndarray:
    """Performs morphological opening and closing to clean the mask."""
    k = square(3)
    return closing(opening(mask, k), k)


def _iter_polys(mask: np.ndarray, transform) -> Iterable[Polygon]:
    """Iterates over shapes in the raster and yields valid polygons."""
    for geom, val in shapes(mask, mask=mask == 1, transform=transform):
        if val:
            poly = shape(geom)
            yield poly if poly.is_valid else make_valid(poly)


def _ha(poly: Polygon) -> float:
    """Calculates the area of a polygon in hectares."""
    return poly.area / 10_000.0


# ─────────────────────────── engine ─────────────────────────────

def vectorize(cfg: Config) -> None:
    """Main vectorization function."""
    mask, transform, crs = _load_mask(cfg.mask_tif)
    if cfg.clean:
        mask = _clean(mask)

    # Check for a completely empty mask first.
    if not (mask == 1).any():
        _LOG.warning("no burn pixels — writing empty layer")
        _write_gdf(gpd.GeoDataFrame(columns=["geometry", "area_ha"], crs=crs), cfg.out_geojson)
        return

    # --- MODIFIED ---
    # Generate ALL polygons without any size filtering.
    feats = [
        {"geometry": p, "area_ha": _ha(p)}
        for p in _iter_polys(mask, transform)
    ]

    # --- MODIFIED ---
    # Unconditionally write whatever was found.
    _LOG.info("Found %d polygons. Writing to file...", len(feats))
    _write_gdf(gpd.GeoDataFrame(feats, crs=crs), cfg.out_geojson)


# ─────────────────────────── CLI ────────────────────────────────

def _parser() -> argparse.ArgumentParser:
    """Parses command-line arguments."""
    p = argparse.ArgumentParser()
    p.add_argument("--mask", required=True, type=Path, help="Input binary raster mask.")
    p.add_argument("--out", required=True, type=Path, help="Output GeoJSON file.")
    # --- REMOVED --min-area-ha argument ---
    p.add_argument("--no-clean", dest="clean", action="store_false", help="Disable morphological cleaning.")
    return p


def _main(argv: list[str] | None = None) -> None:
    """CLI entrypoint."""
    a = _parser().parse_args(argv)
    # --- MODIFIED: Removed min_area_ha from Config ---
    cfg = Config(a.mask, a.out, a.clean)
    try:
        vectorize(cfg)
    except Exception as e:
        _LOG.error("%s", e)
        sys.exit(1)


if __name__ == "__main__":
    _main()