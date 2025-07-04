#!/usr/bin/env python3
"""
workflow.py
===========
End-to-end SAR wildfire burn-scar workflow that orchestrates the entire pipeline.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path
import shutil
import time

import geopandas as gpd
import rasterio
from rasterio.features import sieve

try:
    from processing.preproc import run_gpt_graph
    from processing.change_detection import calculate_change_detection
    from processing.vectorize import vectorize, Config as VectorizeConfig
except ImportError as e:
    print(
        "ERROR: Could not import custom modules. \n"
        "Ensure you run this script from the project root directory with: \n"
        "PYTHONPATH=src python src/workflow.py ...",
        file=sys.stderr,
    )
    sys.exit(1)


def parse_args() -> argparse.Namespace:
    """Parses command-line arguments for the workflow."""
    parser = argparse.ArgumentParser(description="End-to-end SAR burn scar detection pipeline.")
    
    parser.add_argument("--master", type=Path, required=True, help="Path to the pre-fire (master) SAFE .zip file.")
    parser.add_argument("--slave", type=Path, required=True, help="Path to the post-fire (slave) SAFE .zip file.")
    parser.add_argument("--aoi", type=Path, required=True, help="Path to the AOI (Area of Interest) GeoJSON file.")
    parser.add_argument("--output", type=Path, required=True, help="Path for the final output GeoJSON file.")
    
    parser.add_argument("--median-size", type=int, default=10, help="Size of the median filter kernel. Default is 10.")
    parser.add_argument("--threshold", type=float, default=3.0, help="Threshold value to create the binary mask. Default is 3.0.")
    parser.add_argument("--sieve-size", type=int, default=500, help="Minimum size in pixels for a burn scar to be kept after sieving. Default is 500.")
    
    # --- REMOVED --min-area-ha argument ---
    
    parser.add_argument("--debug", action="store_true", help="Save intermediate files in the output directory for debugging.")
    parser.add_argument("--timer", action="store_true", help="Time each step and the total runtime.")
    
    return parser.parse_args()


def format_duration(seconds: float) -> str:
    """Formats seconds into a human-readable string (e.g., 1m 25.3s)."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, seconds = divmod(seconds, 60)
    return f"{int(minutes)}m {seconds:.1f}s"


def threshold_raster(input_path: Path, output_path: Path, threshold: float) -> None:
    print(f"▶ 3. Thresholding raster at a value of {threshold}...")
    with rasterio.open(input_path) as src:
        profile = src.profile.copy()
        image = src.read(1)
        mask = (image >= threshold).astype(rasterio.uint8)
        profile.update(dtype=rasterio.uint8, count=1, nodata=0)
        with rasterio.open(output_path, 'w', **profile) as dst:
            dst.write(mask, 1)


def sieve_raster(input_path: Path, output_path: Path, size: int) -> None:
    print(f"▶ 4. Sieving mask to remove pixel clusters smaller than {size} pixels...")
    with rasterio.open(input_path) as src:
        profile = src.profile.copy()
        mask = src.read(1)
        sieve(mask, size=size, out=mask, connectivity=8)
        with rasterio.open(output_path, 'w', **profile) as dst:
            dst.write(mask, 1)


def main() -> None:
    """Main function to run the entire burn-scar detection workflow."""
    args = parse_args()
    
    workflow_start_time = time.monotonic() if args.timer else None
    
    master_zip = args.master.resolve(strict=True)
    slave_zip = args.slave.resolve(strict=True)
    aoi_path = args.aoi.resolve(strict=True)
    output_geojson = args.output.resolve()
    
    output_geojson.parent.mkdir(parents=True, exist_ok=True)

    if args.debug:
        debug_path = output_geojson.parent / f"{output_geojson.stem}_intermediates"
        debug_path.mkdir(exist_ok=True)
        print(f"🐞 Debug mode is ON. Intermediate files will be saved in: {debug_path}")
        process_dir = debug_path
    else:
        temp_dir_manager = tempfile.TemporaryDirectory(prefix="sar_workflow_")
        process_dir = Path(temp_dir_manager.name)

    try:
        stacked_tif = process_dir / "1_stack_gamma0.tif"
        change_tif = process_dir / "2_change_detection.tif"
        threshold_mask_tif = process_dir / "3_change_mask.tif"
        final_mask_tif = process_dir / "4_burn_mask.tif"
        
        # --- Step 1 ---
        step_start_time = time.monotonic() if args.timer else None
        print("─" * 60)
        print("▶ 1. Pre-processing and stacking master/slave images...")
        aoi_gdf = gpd.read_file(aoi_path)
        aoi_wkt = aoi_gdf.unary_union.wkt
        run_gpt_graph(master_zip, slave_zip, stacked_tif, aoi_wkt)
        duration_str = f" (took {format_duration(time.monotonic() - step_start_time)})" if args.timer else ""
        print(f"✓ Stack saved to: {stacked_tif.name}{duration_str}")
        
        # --- Step 2 ---
        step_start_time = time.monotonic() if args.timer else None
        print("─" * 60)
        print(f"▶ 2. Performing change detection with a {args.median_size}x{args.median_size} median filter...")
        calculate_change_detection(
            input_path=stacked_tif,
            output_path=change_tif,
            filter_type='median',
            filter_params={'size': args.median_size}
        )
        duration_str = f" (took {format_duration(time.monotonic() - step_start_time)})" if args.timer else ""
        print(f"✓ Change map saved to: {change_tif.name}{duration_str}")
        
        # --- Step 3 ---
        step_start_time = time.monotonic() if args.timer else None
        print("─" * 60)
        threshold_raster(change_tif, threshold_mask_tif, args.threshold)
        duration_str = f" (took {format_duration(time.monotonic() - step_start_time)})" if args.timer else ""
        print(f"✓ Threshold mask saved to: {threshold_mask_tif.name}{duration_str}")

        # --- Step 4 ---
        step_start_time = time.monotonic() if args.timer else None
        print("─" * 60)
        sieve_raster(threshold_mask_tif, final_mask_tif, args.sieve_size)
        duration_str = f" (took {format_duration(time.monotonic() - step_start_time)})" if args.timer else ""
        print(f"✓ Final sieved mask saved to: {final_mask_tif.name}{duration_str}")
        
        # --- Step 5 ---
        step_start_time = time.monotonic() if args.timer else None
        print("─" * 60)
        print(f"▶ 5. Polygonizing final mask to GeoJSON...")
        
        # --- MODIFIED: Removed min_area_ha from the call ---
        vectorize_cfg = VectorizeConfig(
            mask_tif=final_mask_tif,
            out_geojson=output_geojson,
            clean=True
        )
        vectorize(vectorize_cfg)
        duration_str = f" (took {format_duration(time.monotonic() - step_start_time)})" if args.timer else ""
        print(f"✓ Vectorizing complete.{duration_str}")

    finally:
        if not args.debug:
            temp_dir_manager.cleanup()
            
    print("─" * 60)
    if workflow_start_time:
        total_duration = format_duration(time.monotonic() - workflow_start_time)
        print(f"⏱️  Total workflow time: {total_duration}")

    if output_geojson.exists():
        print("\n🎉 Workflow complete!")
        print(f"  Final burn scar polygons saved to: {output_geojson}")
    else:
        print("\nℹ️  Workflow finished, but no output file was generated.")
        print("  This usually means no burn scars were found that met the filtering criteria.")
        if args.debug:
            print(f"  Inspect the intermediate files in '{process_dir}' to diagnose the issue.")
        else:
            print("  Try running again with the --debug flag to inspect intermediate files.")


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as e:
        print(f"\n❌ ERROR: Input file not found.\n{e}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"\n❌ An unexpected error occurred: {exc}", file=sys.stderr)
        sys.exit(1)