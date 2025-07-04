# SAR Wildfire Burn‑Scar Mapping – Evia 2021

> **One‑week sprint deliverables**
> Automated Sentinel‑1 SAR processing pipeline, burn‑scar map product, reproducible code, and documentation.

---

## Repository structure

```text
.
├── README.md              ← you are here
├── LICENSE                ← MIT
├── environment.yml        ← Conda environment (snap, pyroSAR, gdal, etc.)
├── requirements.txt       ← pip alternative
├── .gitignore
├── data/
│   ├── raw/               ← zipped SAFE/SLC scenes
│   ├── external/          ← DEM, coastline shapefiles
│   └── processed/         ← outputs (GeoTIFFs, vectors)
├── src/
│   ├── workflow.py        ← CLI wrapper that chains processing steps
│   └── processing/
│       ├── preproc.py
│       ├── change_detection.py
│       └── vectorize.py
├── notebooks/
│   └── 01_workflow_demo.ipynb
├── figures/
│   └── evia_burnscar_map.png
└── docs/
    ├── usage.md
    └── methodology.md
```
---

## Quick‑start

```bash
# 1. Clone & initialise submodules (if any)
git clone https://github.com/<user>/sar-wildfire-burnscar.git
cd sar-wildfire-burnscar

# 2. Create environment
conda env create -f environment.yml
conda activate sar-fire

# 3. Pull large assets tracked with LFS
git lfs pull

# 4. Run the example pipeline
python src/workflow.py \
    --master data/raw/S1A_Evia_20210731.zip \
    --slave  data/raw/S1A_Evia_20210812.zip \
    --aoi    config/evia.geojson \
    --out    data/processed/evia_burnscar.tif
```

---

## Processing chain

| Step | Operator                         | Notes                          |
| ---- | -------------------------------- | ------------------------------ |
| 1    | Apply‑Orbit‑File                 | Precise orbit state vectors    |
| 2    | Radiometric Calibration          | β⁰                             |
| 3    | Range‑Doppler Terrain Correction | γ⁰, 10 m SRTM                  |
| 4    | Refined Lee Speckle Filter       | Window 7 × 7                   |
| 5    | Coregistration                   | Bitemporal stack               |
| 6    | Log‑ratio Change Detection       | 10·log10(post) − 10·log10(pre) |
| 7    | Thresholding                     | −1.5 dB (Otsu tested)          |
| 8    | Morphological Opening/Closing    | 3‑px kernel                    |
| 9    | Raster‑to‑Vector                 | Erosion‑front polygons         |

The chain is implemented with **PyroSAR + SNAP** (via *snappy*) and **GDAL** CLI utilities for post‑processing. All steps are reproduced in `src/processing/`.

---

## Map product

The final burn‑scar mask rendered over Sentinel‑2 true‑colour is stored in `figures/evia_burnscar_map.png`:

![Evia 2021 Burn Scar](figures/Evia Wildfire Burn Scar – July–August 2021.png)

---

## Re‑using for new events

1. Replace master/slave scenes in `data/raw/`.
2. Supply a new `--aoi` GeoJSON.
3. Adjust threshold (`--thr`) parameter if scene noise differs.

---

## Development notes

* **Code style**: PEP 8 + *black* (pre‑commit hook included).
* **Testing**: `pytest` covers core functions.
* **CI/CD**: GitHub Actions – flake8, pytest, docs build.
* **Large files**: Track GeoTIFFs and zipped SAFE files with **Git LFS**.
* **Project board**: Issues flow through *Icebox → Backlog → Sprint*.

---

## .gitignore (excerpt)

```gitignore
# data
data/*
!data/README.md

# figures
figures/*
!figures/README.md

# environments
.venv/
.env

# notebooks
**/*.ipynb_checkpoints

# python artefacts
__pycache__/
*.egg-info/

# OS
.DS_Store
```

---

## Environment (minimal)

<details>
<summary>Click to show <code>environment.yml</code></summary>

```yaml
name: sar-fire
channels:
  - conda-forge
  - defaults
dependencies:
  - python=3.12
  - gdal
  - geopandas
  - numpy
  - rasterio
  - pyroSAR
  - snap
  # - snapista  # uncomment if binary wheels available for your OS
  - scikit-image
  - jupyterlab
  - matplotlib
  - pip
  - pip:
      - git+https://github.com/senbox-org/snapista.git  # fallback if needed
```

</details>

---

## License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.

---

## Citation

If you use this code or figures, please cite:

```text
Katayev, E. (2025). SAR Wildfire Burn‑Scar Mapping – Evia 2021 (Version 1.0). GitHub repository. https://github.com/Snawyyy/sar-wildfire-burnscar
```

---

## Contact

Eitan Katayev – [Etanss9911@gmail.com](mailto:Etanss9911@gmail.com)
