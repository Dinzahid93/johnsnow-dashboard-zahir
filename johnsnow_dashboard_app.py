# ============================================================
# John Snow Cholera Dashboard – FIXED VERSION
# ============================================================

import os
import numpy as np
import pandas as pd
import geopandas as gpd
import folium
import pathlib
import streamlit as st
from streamlit_folium import st_folium

# -------------------------------------------------------------
# TRY TO IMPORT RASTERIO
# -------------------------------------------------------------
try:
    import rasterio
    from rasterio.warp import transform_bounds
    RASTER_OK = True
except ImportError:
    RASTER_OK = False

# -------------------------------------------------------------
# SAFE PATH HANDLING (IMPORTANT FIX)
# -------------------------------------------------------------
BASE_DIR = pathlib.Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

# Accept .tif OR .tiff
tif_candidates = ["SnowMap.tif", "SnowMap.tiff"]
snowmap_path = None
for f in tif_candidates:
    if (DATA_DIR / f).exists():
        snowmap_path = DATA_DIR / f
        break

deaths_path = DATA_DIR / "deaths_by_bldg.geojson"
pumps_path  = DATA_DIR / "pumps.geojson"

# -------------------------------------------------------------
# LOAD VECTOR DATA
# -------------------------------------------------------------
@st.cache_data
def load_vector_data():
    deaths = gpd.read_file(deaths_path)
    pumps  = gpd.read_file(pumps_path)

    # Detect death column
    if "deaths" in deaths.columns:
        death_col = "deaths"
    elif "Count" in deaths.columns:
        death_col = "Count"
    else:
        raise ValueError("No 'deaths' or 'Count' column in deaths_by_bldg")

    deaths[death_col] = pd.to_numeric(deaths[death_col], errors="coerce").fillna(0).astype(int)

    # Reproject if needed
    deaths_wgs = deaths.to_crs(epsg=4326) if deaths.crs and deaths.crs.to_epsg() != 4326 else deaths
    pumps_wgs  = pumps.to_crs(epsg=4326)  if pumps.crs and pumps.crs.to_epsg() != 4326 else pumps

    return deaths, pumps, deaths_wgs, pumps_wgs, death_col

# -------------------------------------------------------------
# LOAD RASTER TIFF (Snow Map)
# -------------------------------------------------------------
@st.cache_data
def load_snow_tiff():
    if not (RASTER_OK and snowmap_path and snowmap_path.exists()):
        return None, None

    with rasterio.open(snowmap_path) as src:
        img = src.read()
        bounds = src.bounds
        tif_crs = src.crs

        wgs_bounds = transform_bounds(
            tif_crs, "EPSG:4326",
            bounds.left, bounds.bottom, bounds.right, bounds.top
        )

    # Convert image
    if img.shape[0] == 1:
        gray = img[0]
        img_rgb = np.stack([gray, gray, gray], axis=0)
    else:
        img_rgb = img[:3]

    img_rgb = np.transpose(img_rgb, (1, 2, 0))
    img_rgb = 255 * (img_rgb - img_rgb.min()) / (img_rgb.max() - img_rgb.min())
    img_rgb = img_rgb.astype("uint8")

    bounds_foli_
