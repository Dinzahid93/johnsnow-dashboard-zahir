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

snowmap_path = DATA_DIR / "SnowMap.tif"
deaths_path = DATA_DIR / "deaths_by_bldg.geojson"
pumps_path  = DATA_DIR / "pumps.geojson"


# ============================================================
# LOAD VECTOR DATA (no CRS transform)
# ============================================================
@st.cache_data
def load_vectors():
    deaths = gpd.read_file(deaths_path)
    pumps = gpd.read_file(pumps_path)

    # identify deaths column
    if "deaths" in deaths.columns:
        death_col = "deaths"
    elif "Count" in deaths.columns:
        death_col = "Count"
    else:
        st.error("Could not find a 'deaths' column.")
        return None

    deaths[death_col] = pd.to_numeric(deaths[death_col], errors="coerce").fillna(0).astype(int)

    return deaths, pumps, death_col


# ============================================================
# LOAD TIFF (Simple CRS → pixel coordinates)
# ============================================================
def load_tiff_simple():
    if not snowmap_path.exists():
        st.warning("SnowMap.tif not found.")
        return None, None

    try:
        with rasterio.open(snowmap_path) as src:
            arr = src.read()
            h = src.height
            w = src.width

        # Create RGB fallback
        if arr.shape[0] == 1:
            g = arr[0]
            rgb = np.stack([g, g, g], axis=2)
        else:
            rgb = np.transpose(arr[:3], (1, 2, 0))

        # Normalize to 0–255
        rgb = rgb.astype("float32")
        rgb = 255 * (rgb - rgb.min()) / (rgb.max() - rgb.min())
        rgb = rgb.astype("uint8")

        bounds = [[0, 0], [h, w]]  # pixel CRS

        return rgb, bounds

    except Exception as e:
        st.error(f"Failed to load TIFF: {e}")
        return None, None


# ============================================================
# LOAD DATA
# ============================================================
loaded = load_vectors()
if loaded is None:
    st.stop()

deaths, pumps, death_col = loaded
snow_img, snow_bounds = load_tiff_simple()


# ============================================================
# STREAMLIT PAGE
# ============================================================
st.set_page_config(page_title="John Snow Map", layout="wide")
st.title("John Snow Cholera Map (Simple CRS – Pixel Coordinates)")

# Metrics
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Deaths", int(deaths[death_col].sum()))
c2.metric("Buildings", len(deaths))
c3.metric("Max Deaths", int(deaths[death_col].max()))
c4.metric("Avg Deaths", f"{deaths[death_col].mean():.1f}")

st.markdown("---")


# ============================================================
# MAP (Simple CRS - no slider)
# ============================================================
st.subheader("Interactive Map")

if snow_bounds is None:
    st.error("Cannot display map: SnowMap.tif failed to load.")
    st.stop()

# center map on raster center
center_y = snow_bounds[1][0] / 2
center_x = snow_bounds[1][1] / 2

m = folium.Map(
    location=[center_y, center_x],
    zoom_start=1,
    crs="Simple"  # IMPORTANT!
)

# add TIFF overlay
folium.raster_layers.ImageOverlay(
    snow_img,
    bounds=snow_bounds,
    opacity=0.9,
    name="SnowMap"
).add_to(m)

# Death markers (fixed size)
fg_d = folium.FeatureGroup("Deaths")
for _, row in deaths.iterrows():
    x = row.geometry.x
    y = row.geometry.y
    d = row[death_col]

    folium.CircleMarker(
        [y, x],
        radius=4 + (d * 0.3),  # fixed scale (no slider)
        color="red",
        fill=True,
        fill_opacity=0.85,
        popup=f"Deaths: {d}"
    ).add_to(fg_d)
fg_d.add_to(m)

# Pumps
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

st_folium(m, width=1100, height=650, key="map")


# ============================================================
# ATTRIBUTE TABLES
# ============================================================
st.markdown("---")
st.subheader("Building Attributes")
st.dataframe(deaths.drop(columns="geometry"))

st.subheader("Pump Attributes")
st.dataframe(pumps.drop(columns="geometry"))
