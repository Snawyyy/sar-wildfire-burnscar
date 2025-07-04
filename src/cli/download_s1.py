import asf_search as asf
import os
from getpass import getpass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR     = PROJECT_ROOT / "data" / "raw" / "s1_data"

def authenticate():
    while True:
        try:
            username = os.environ['EARTHDATA_USERNAME']
            password = os.environ['EARTHDATA_PASSWORD']
            print("Using Earthdata credentials from environment variables.")
        except KeyError:
            print("Please enter your Earthdata Login credentials.")
            username = getpass('Username: ')
            password = getpass('Password: ')

        try:
            session = asf.ASFSession().auth_with_creds(username, password)
            print("Successfully authenticated with Earthdata Login.")
            return session 
        except Exception as e:
            print(f"Authentication failed: {e}")
            if 'EARTHDATA_USERNAME' in os.environ:
                del os.environ['EARTHDATA_USERNAME']
                del os.environ['EARTHDATA_PASSWORD']
            print("Please try again.\n")

def search_area(bbox, start_date, end_date):

    wkt_aoi = convect_bbox_to_wkt(bbox)

    # Create a directory to store our data if it doesn't exist
    create_storage_dir()

    print("\nSearching for Sentinel-1 scenes...")

    results = asf.geo_search(
        platform=[asf.PLATFORM.SENTINEL1],
        intersectsWith=wkt_aoi,
        start=start_date,
        end=end_date,
        processingLevel=[asf.PRODUCT_TYPE.GRD_HD],
        beamMode=[asf.BEAMMODE.IW],
        flightDirection=asf.FLIGHT_DIRECTION.DESCENDING,
    )

    print(f"Found {len(results)} scenes.")

    print("\nInspecting found scenes:")
    for i, product in enumerate(results, 1):
        print(f"{i}. {product.properties['sceneName']}")

    return results

def create_storage_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Using download directory: {DATA_DIR}")

def convect_bbox_to_wkt(bbox):
    wkt_aoi = f"POLYGON (({bbox[0]} {bbox[1]}, {bbox[2]} {bbox[1]}, {bbox[2]} {bbox[3]}, {bbox[0]} {bbox[3]}, {bbox[0]} {bbox[1]}))"
    return wkt_aoi

def download_selected_scenes(results, session):
    if not results:
        print("\nNo scenes found to download.")
        return

    print("\nEnter the scene numbers you want to download (e.g. 1, 2, 5):")
    selected_input = input("Scene numbers: ")

    try:
        selected_indices = [int(i.strip()) - 1 for i in selected_input.split(',')]
    except ValueError:
        print("Invalid input. Please enter comma-separated numbers.")
        return

    selected_scenes = []
    for i in selected_indices:
        if 0 <= i < len(results):
            selected_scenes.append(results[i])
        else:
            print(f"Skipping invalid scene number: {i + 1}")

    if selected_scenes:
        print("\nStarting download...")
        results.download(path=DATA_DIR, session=session)
        print("Download complete.")
    else:
        print("No valid scenes selected for download.")

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Search and download Sentinel-1 scenes using ASF API.")
    parser.add_argument('--start', type=str, default="2021-07-29", help="Start date (YYYY-MM-DD)")
    parser.add_argument('--end', type=str, default="2021-08-22", help="End date (YYYY-MM-DD)")
    parser.add_argument('--bbox', type=float, nargs=4, metavar=('minLon', 'minLat', 'maxLon', 'maxLat'),
                        default=[22.92550833727161, 38.7509441550928, 23.563700414775237, 39.08766821216534],
                        help="Bounding box as minLon minLat maxLon maxLat")
    args = parser.parse_args()

    session = authenticate()
    results = search_area(args.bbox, args.start, args.end)

    if results:
        download_selected_scenes(results, session)
    else:
        print("No scenes available for the specified parameters.")

if __name__ == "__main__":
    main()
