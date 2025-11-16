import os
import pathlib
import numpy as np
import pandas as pd
import geopandas as gpd
import folium
import streamlit as st
from streamlit_folium import st_folium

import rasterio

# ============================================================
# PATHS
# ============================================================

try:
    BASE_DIR = pathlib.Path(__file__).parent
except:
    BASE_DIR = pathlib.Path(os.getcwd())

DATA_DIR = BASE_DIR / "data"

snowmap_path = DATA_DIR / "SnowMap.tif"
deaths_path = DATA_DIR / "deaths_by_bldg.geojson"
pumps_path  = DATA_DIR / "pumps.geojson"

# ============================================================
# LOAD VECTOR DATA (NO CRS TRANSFORMATION)
# ============================================================

@st.cache_data
def load_vector():
    deaths = gpd.read_file(deaths_path)
    pumps = gpd.read_file(pumps_path)

    # detect column
    if "deaths" in deaths.columns:
        dc = "deaths"
    elif "Count" in deaths.columns:
        dc = "Count"
    else:
        st.error("No deaths column found.")
        return None

    deaths[dc] = pd.to_numeric(deaths[dc], errors="coerce").fillna(0).astype(int)

    # DO NOT convert CRS
    return deaths, pumps, dc


# ============================================================
# LOAD TIFF + GET PIXEL BOUNDS
# ============================================================

def load_tiff_bounds():

    if not snowmap_path.exists():
        return None, None

    with rasterio.open(snowmap_path) as src:
        arr = src.read()
        h = src.height
        w = src.width

    # Convert to RGB
    if arr.shape[0] == 1:
        g = arr[0]
        rgb = np.stack([g, g, g], axis=2)
    else:
        rgb = np.transpose(arr[:3], (1, 2, 0))

    # normalize 0–255
    rgb = rgb.astype("float32")
    rgb = 255 * (rgb - rgb.min()) / (rgb.max() - rgb.min())
    rgb = rgb.astype("uint8")

    # bounds in pixel CRS (top-left = 0,0)
    # folium simple CRS uses [y,x] structure
    bounds = [[0, 0], [h, w]]

    return rgb, bounds


# ============================================================
# LOAD DATA
# ============================================================

loaded = load_vector()
if loaded is None:
    st.stop()

deaths, pumps, death_col = loaded
snow_img, snow_bounds = load_tiff_bounds()


# ============================================================
# UI HEADER
# ============================================================

st.set_page_config(page_title="John Snow (Simple CRS)", layout="wide")
st.title("John Snow Cholera Map (Simple CRS Mode)")


# METRICS
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Deaths", int(deaths[death_col].sum()))
c2.metric("Buildings", len(deaths))
c3.metric("Max Deaths", int(deaths[death_col].max()))
c4.metric("Avg Deaths", f"{deaths[death_col].mean():.2f}")

st.markdown("---")

# Marker size control
scale_factor = st.slider("Death marker scale", 0.2, 1.5, 0.4)


# ============================================================
# MAP — SIMPLE CRS (PIXEL COORDINATES)
# ============================================================

st.subheader("Interactive Map (Simple CRS)")

m = folium.Map(
    location=[snow_bounds[1][0] / 2, snow_bounds[1][1] / 2],  # center of image
    zoom_start=1,
    crs="Simple"   # <---- THIS FIXES EVERYTHING
)

# add TIFF as pixel overlay
if snow_img is not None:
    folium.raster_layers.ImageOverlay(
        snow_img,
        bounds=snow_bounds,
        opacity=0.9,
        name="SnowMap"
    ).add_to(m)

# deaths layer (pixel coordinates)
fg_d = folium.FeatureGroup("Deaths")
for _, row in deaths.iterrows():
    x = row.geometry.x
    y = row.geometry.y
    d = row[death_col]

    folium.CircleMarker(
        [y, x],             # pixel CRS
        radius=3 + d * scale_factor,
        color="red",
        fill=True,
        fill_opacity=0.8,
        popup=f"Deaths: {d}"
    ).add_to(fg_d)
fg_d.add_to(m)

# pumps layer
fg_p = folium.FeatureGroup("Pumps")
for _, row in pumps.iterrows():
    x = row.geometry.x
    y = row.geometry.y

    folium.Marker(
        [y, x],
        icon=folium.Icon(color="blue", icon="tint"),
        popup="Water Pump"
    ).add_to(fg_p)
fg_p.add_to(m)

folium.LayerControl().add_to(m)

# no rerun on pan
st_folium(m, width=1100, height=650, key="mainmap", returned_objects=[])


# ============================================================
# TABLES
# ============================================================

st.markdown("---")
st.subheader("Building Attributes")
st.dataframe(deaths.drop(columns="geometry"))

st.subheader("Pump Attributes")
st.dataframe(pumps.drop(columns="geometry"))
