#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
import argparse
import subprocess
import sys
import shutil
# --- NEW: Import geopandas to handle vector data ---
import geopandas as gpd

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[2]
GRAPH = REPO_ROOT / "config" / "graphs" / "preproc_full.xml"
GPT_EXECUTABLE = shutil.which("gpt") or "/opt/snap/bin/gpt"

# ── GPT Wrapper ───────────────────────────────────────────────────────────────

# --- MODIFIED: Function now accepts a WKT string for the AOI ---
def run_gpt_graph(master_zip: Path, slave_zip: Path, output_tif: Path, aoi_wkt: str | None = None) -> None:
    """
    Executes a single SNAP graph that processes a master/slave pair.
    The graph must be designed to accept 'master', 'slave', 'output', and 'aoi' as variables.
    """
    if not GRAPH.exists():
        sys.exit(f"❌ SNAP graph not found: {GRAPH}")
    if not Path(GPT_EXECUTABLE).exists():
        sys.exit(f"❌ SNAP gpt executable not found at: {GPT_EXECUTABLE}")

    cmd = [
        GPT_EXECUTABLE,
        str(GRAPH),
        f"-Pmaster={master_zip}",
        f"-Pslave={slave_zip}",
        f"-Poutput={output_tif}",
    ]
    
    # --- MODIFIED: Appends the WKT string directly ---
    if aoi_wkt:
        cmd.append(f"-Paoi={aoi_wkt}")
    
    print(f"▶ Processing pair with graph: {GRAPH.name}")
    # Be cautious printing the full command if the WKT string is very long
    print(f"  gpt {GRAPH.name} -Pmaster=... -Pslave=... -Poutput=... -Paoi='POLYGON((...))'")
    
    subprocess.run(cmd, check=True)

# ── CLI Entrypoint ────────────────────────────────────────────────────────────

def main() -> None:
    """Main function to parse arguments and run the processing graph."""
    parser = argparse.ArgumentParser(
        description="Process a pre/post SAR file pair using a single SNAP GPT graph."
    )
    parser.add_argument("--master", required=True, type=Path, help="Path to the pre-event (master) SAFE .zip file.")
    parser.add_argument("--slave", required=True, type=Path, help="Path to the post-event (slave) SAFE .zip file.")
    parser.add_argument("--aoi", type=Path, help="Optional: Path to an AOI file (e.g., GeoJSON) for subsetting.")
    parser.add_argument("--out", required=True, type=Path, help="Path for the final output GeoTIFF file.")
    
    args = parser.parse_args()
    
    master_file = args.master.resolve()
    slave_file = args.slave.resolve()
    output_file = args.out.resolve()
    aoi_file = args.aoi.resolve() if args.aoi else None
    
    # --- NEW: Convert AOI file to WKT string ---
    aoi_wkt_string = None
    if aoi_file:
        if not aoi_file.exists():
            sys.exit(f"❌ AOI file not found: {aoi_file}")
        print(f"i Reading AOI from: {aoi_file}")
        # Read the file and dissolve all features into a single geometry
        gdf = gpd.read_file(aoi_file)
        unified_geometry = gdf.unary_union
        # Convert the unified geometry to a WKT string
        aoi_wkt_string = unified_geometry.wkt
        
    for f in (master_file, slave_file):
        if not f.exists():
            sys.exit(f"❌ Input file not found: {f}")
        
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    print("🛰️  Processing file pair...")
    # --- MODIFIED: Pass the WKT string to the run function ---
    run_gpt_graph(master_file, slave_file, output_file, aoi_wkt_string)
    
    print(f"✓ Processing complete. Output saved to → {output_file}")

if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        sys.exit(f"\n❌ GPT processing failed with exit code {e.returncode}.")
    except Exception as e:
        sys.exit(f"\n❌ An unexpected error occurred: {e}")