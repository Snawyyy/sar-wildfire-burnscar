#!/usr/bin/env python3
"""
SAR Change detection calculation with speckle filtering
Formula: 10*log10(band_3) - 10*log10(band_1)
Includes various filters to reduce SAR speckle and noise
"""

import rasterio
import numpy as np
import argparse
from pathlib import Path
from scipy import ndimage
from scipy.ndimage import median_filter, gaussian_filter, binary_opening, binary_closing
from skimage.filters import rank
from skimage.morphology import disk, square
import warnings
warnings.filterwarnings('ignore')

def apply_filters(data, filter_type='median', **kwargs):
    """
    Apply various filters to reduce SAR speckle and noise
    
    Args:
        data: Input array
        filter_type: Type of filter to apply
        **kwargs: Filter-specific parameters
    """
    
    if filter_type == 'median':
        # Median filter - excellent for SAR speckle
        size = kwargs.get('size', 3)
        return median_filter(data, size=size)
    
    elif filter_type == 'gaussian':
        # Gaussian smoothing
        sigma = kwargs.get('sigma', 1.0)
        return gaussian_filter(data, sigma=sigma)
    
    elif filter_type == 'morphological':
        # Morphological opening/closing to remove small spots
        threshold = kwargs.get('threshold', 0.5)
        structure_size = kwargs.get('structure_size', 3)
        
        # Create binary mask
        binary_mask = np.abs(data) > threshold
        
        # Apply opening (erosion followed by dilation) to remove small spots
        if structure_size > 0:
            structure = np.ones((structure_size, structure_size))
            binary_mask = binary_opening(binary_mask, structure=structure)
            binary_mask = binary_closing(binary_mask, structure=structure)
        
        # Apply mask to original data
        return np.where(binary_mask, data, 0)
    
    elif filter_type == 'minimum_mapping_unit':
        # Remove patches smaller than minimum mapping unit
        threshold = kwargs.get('threshold', 0.5)
        min_pixels = kwargs.get('min_pixels', 9)  # 3x3 pixels minimum
        
        # Create binary mask
        binary_mask = np.abs(data) > threshold
        
        # Label connected components
        labeled, num_features = ndimage.label(binary_mask)
        
        # Remove small components
        for i in range(1, num_features + 1):
            component_mask = labeled == i
            if np.sum(component_mask) < min_pixels:
                binary_mask[component_mask] = False
        
        return np.where(binary_mask, data, 0)
    
    elif filter_type == 'bilateral':
        # Bilateral filter (edge-preserving smoothing)
        # This requires more complex implementation, using gaussian as approximation
        sigma = kwargs.get('sigma', 1.0)
        return gaussian_filter(data, sigma=sigma)
    
    elif filter_type == 'combined':
        # Apply multiple filters in sequence
        filtered = data.copy()
        
        # 1. Median filter for speckle
        filtered = median_filter(filtered, size=kwargs.get('median_size', 3))
        
        # 2. Light gaussian smoothing
        filtered = gaussian_filter(filtered, sigma=kwargs.get('gaussian_sigma', 0.8))
        
        # 3. Morphological filtering to remove small spots
        threshold = kwargs.get('threshold', 0.3)
        structure_size = kwargs.get('structure_size', 2)
        
        binary_mask = np.abs(filtered) > threshold
        if structure_size > 0:
            structure = np.ones((structure_size, structure_size))
            binary_mask = binary_opening(binary_mask, structure=structure)
        
        filtered = np.where(binary_mask, filtered, 0)
        
        return filtered
    
    else:
        return data

def calculate_change_detection(input_path, output_path, band1=1, band3=3, 
                             filter_type='median', filter_params=None):
    """
    Calculate change detection with filtering for SAR data
    
    Args:
        input_path: Path to input multiband raster
        output_path: Path to output change detection raster
        band1: Band number for first band (default: 1)
        band3: Band number for third band (default: 3)
        filter_type: Type of filter to apply
        filter_params: Dictionary of filter parameters
    """
    
    if filter_params is None:
        filter_params = {}
    
    with rasterio.open(input_path) as src:
        # Read the bands
        print(f"📖 Reading band {band1} and band {band3} from {input_path}")
        band_1_data = src.read(band1, masked=True)
        band_3_data = src.read(band3, masked=True)
        
        # Get the profile for output file
        profile = src.profile.copy()
        
    # Ensure we have positive values for log calculation
    epsilon = 1e-10
    band_1_data = np.where(band_1_data <= 0, epsilon, band_1_data)
    band_3_data = np.where(band_3_data <= 0, epsilon, band_3_data)
    
    # Calculate change detection: 10*log10(band_3) - 10*log10(band_1)
    print("🧮 Calculating change detection...")
    with np.errstate(invalid='ignore', divide='ignore'):
        change = 10 * np.log10(band_3_data) - 10 * np.log10(band_1_data)
    
    # Handle any remaining invalid values
    change = np.where(np.isfinite(change), change, 0)
    
    # Apply filtering
    if filter_type != 'none':
        print(f"🔧 Applying {filter_type} filter...")
        change = apply_filters(change, filter_type, **filter_params)
    
    # Update profile for single band output
    profile.update({
        'count': 1,
        'dtype': 'float32',
        'nodata': 0
    })
    
    # Write the result
    print(f"💾 Writing result to {output_path}")
    with rasterio.open(output_path, 'w', **profile) as dst:
        dst.write(change.astype('float32'), 1)
    
    # Print some statistics
    valid_pixels = np.isfinite(change) & (change != 0)
    if np.any(valid_pixels):
        print(f"📊 Change detection statistics:")
        print(f"   Min: {np.min(change[valid_pixels]):.3f}")
        print(f"   Max: {np.max(change[valid_pixels]):.3f}")
        print(f"   Mean: {np.mean(change[valid_pixels]):.3f}")
        print(f"   Std: {np.std(change[valid_pixels]):.3f}")
        print(f"   Valid pixels: {np.sum(valid_pixels):,}")
    
    print("✅ Change detection completed!")

def main():
    parser = argparse.ArgumentParser(description='Calculate filtered change detection from SAR data')
    parser.add_argument('--input', required=True, help='Input multiband raster file')
    parser.add_argument('--output', required=True, help='Output change detection raster file')
    parser.add_argument('--band1', type=int, default=1, help='First band number (default: 1)')
    parser.add_argument('--band3', type=int, default=3, help='Third band number (default: 3)')
    
    # Filter options
    parser.add_argument('--filter', choices=['none', 'median', 'gaussian', 'morphological', 
                                           'minimum_mapping_unit', 'combined'], 
                       default='median', help='Filter type to apply (default: median)')
    
    # Filter parameters
    parser.add_argument('--median-size', type=int, default=3, help='Median filter size (default: 3)')
    parser.add_argument('--gaussian-sigma', type=float, default=1.0, help='Gaussian sigma (default: 1.0)')
    parser.add_argument('--threshold', type=float, default=0.5, help='Threshold for morphological filters')
    parser.add_argument('--structure-size', type=int, default=3, help='Morphological structure size')
    parser.add_argument('--min-pixels', type=int, default=9, help='Minimum pixels for mapping unit filter')
    
    args = parser.parse_args()
    
    # Validate input file exists
    if not Path(args.input).exists():
        raise FileNotFoundError(f"Input file not found: {args.input}")
    
    # Create output directory if needed
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    
    # Prepare filter parameters
    filter_params = {
        'size': args.median_size,
        'sigma': args.gaussian_sigma,
        'threshold': args.threshold,
        'structure_size': args.structure_size,
        'min_pixels': args.min_pixels,
        'median_size': args.median_size,
        'gaussian_sigma': args.gaussian_sigma
    }
    
    calculate_change_detection(args.input, args.output, args.band1, args.band3, 
                             args.filter, filter_params)

if __name__ == "__main__":
    main()