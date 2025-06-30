#!/usr/bin/env python
"""
CLI wrapper for the SAR wildfire workflow.
Usage:
    python -m src.workflow --master ... --slave ... --aoi ... --out ...
"""
import argparse
from src.processing import preproc, change_detection, vectorize

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--master", required=True)
    ap.add_argument("--slave", required=True)
    ap.add_argument("--aoi", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    coreg = preproc.coregister(args.master, args.slave, args.aoi)
    diff  = change_detection.log_ratio(coreg)
    vectorize.mask_to_shp(diff, args.out)

if __name__ == "__main__":
    main()
