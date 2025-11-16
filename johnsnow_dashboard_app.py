import os
import pathlib
import numpy as np
import pandas as pd
import geopandas as gpd
import streamlit as st
from streamlit_folium import st_folium
import folium
import rasterio

# ============================================================
# PATHS
# ============================================================
try:
    BASE_DIR = pathlib.Path(__file__).parent
except:
    BASE_DIR = pathlib.Path(os.getcwd())

DATA_DIR = BASE_DIR / "data"

deaths_path = DATA_DIR / "deaths_by_bldg.geojson"
pumps_path  = DATA_DIR / "pumps.geojson"

# ============================================================
# LOAD VECTOR DATA
# ============================================================
@st.cache_data
def load_vectors():
    deaths = gpd.read_file(deaths_path)
    pumps   = gpd.read_file(pumps_path)

    if "deaths" in deaths.columns:
        death_col = "deaths"
    elif "Count" in deaths.columns:
        death_col = "Count"
    else:
        st.error("No deaths column found.")
        return None

    deaths[death_col] = pd.to_numeric(deaths[death_col], errors="coerce").fillna(0).astype(int)

    return deaths, pumps, death_col

loaded = load_vectors()
if loaded is None:
    st.stop()

deaths, pumps, death_col = loaded

# ============================================================
# LOAD TIFF (only if uploaded)
# ============================================================
def load_uploaded_tiff(uploaded_file):
    """Load TIFF file from upload."""
    if uploaded_file is None:
        return None, None

    try:
        with rasterio.open(uploaded_file) as src:
            arr = src.read()
            h, w = src.height, src.width

        # Make RGB
        if arr.shape[0] == 1:
            g = arr[0]
            rgb = np.stack([g, g, g], axis=2)
        else:
            rgb = np.transpose(arr[:3], (1, 2, 0))

        rgb = (255 * (rgb - rgb.min()) / (rgb.max() - rgb.min())).astype("uint8")

        bounds = [[0, 0], [h, w]]  # Pixel coordinates (Simple CRS)

        return rgb, bounds

    except Exception as e:
        st.error(f"TIFF read error: {e}")
        return None, None

# ============================================================
# STREAMLIT UI
# ============================================================
st.set_page_config(page_title="John Snow Dashboard", layout="wide")
st.title("John Snow Cholera Map (TIFF optional upload)")

# --- Upload box for TIFF ---
uploaded_tiff = st.sidebar.file_uploader(
    "Optional: Upload SnowMap.tif",
    type=["tif", "tiff"]
)

snow_img, snow_bounds = load_uploaded_tiff(uploaded_tiff)

# ============================================================
# SUMMARY METRICS
# ============================================================
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Deaths", int(deaths[death_col].sum()))
c2.metric("Buildings", len(deaths))
c3.metric("Max Deaths", int(deaths[death_col].max()))
c4.metric("Avg Deaths", f"{deaths[death_col].mean():.1f}")

st.markdown("---")

# ============================================================
# BUILD MAP
# ============================================================
st.subheader("Interactive Map")

# Default center (from deaths layer)
center_lat = deaths.geometry.y.mean()
center_lon = deaths.geometry.x.mean()

m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=17,
    tiles="CartoDB Positron"
)

# --- If uploaded TIFF exists → use Simple CRS ---
if snow_img is not None and snow_bounds is not None:
    m = folium.Map(location=[snow_bounds[1][0]/2, snow_bounds[1][1]/2],
                   zoom_start=1, crs="Simple")

    folium.raster_layers.ImageOverlay(
        snow_img,
        bounds=snow_bounds,
        opacity=0.8,
        name="SnowMap"
    ).add_to(m)

# --- Death markers ---
deaths_fg = folium.FeatureGroup("Deaths")
for _, row in deaths.iterrows():
    x = row.geometry.x
    y = row.geometry.y
    d = row[death_col]
    folium.CircleMarker(
        [y, x],
        radius=4 + d * 0.3,
        color="red",
        fill=True,
        fill_opacity=0.9,
        popup=f"Deaths: {d}"
    ).add_to(deaths_fg)
deaths_fg.add_to(m)

# --- Pump markers ---
pumps_fg = folium.FeatureGroup("Pumps")
for _, row in pumps.iterrows():
    x = row.geometry.x
    y = row.geometry.y
    folium.Marker(
        [y, x],
        icon=folium.Icon(color="blue", icon="tint"),
        popup="Water Pump"
    ).add_to(pumps_fg)
pumps_fg.add_to(m)

folium.LayerControl().add_to(m)

st_folium(m, width=1000, height=600)

# ============================================================
# ATTRIBUTE TABLES
# ============================================================
st.markdown("---")
st.subheader("Deaths Table")
st.dataframe(deaths.drop(columns="geometry"))

st.subheader("Pumps Table")
st.dataframe(pumps.drop(columns="geometry"))
