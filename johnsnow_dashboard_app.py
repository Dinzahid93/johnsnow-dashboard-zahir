# ============================================================
# John Snow Cholera Dashboard – FINAL STABLE VERSION
# ============================================================

import os
import pathlib
import numpy as np
import pandas as pd
import geopandas as gpd
import folium
import streamlit as st
from streamlit_folium import st_folium

# ============================================================
# SAFE DIRECTORY HANDLING (IMPORTANT: NO __file__)
# ============================================================

try:
    BASE_DIR = pathlib.Path(__file__).parent
except:
    # Streamlit Cloud workaround (no __file__ available)
    BASE_DIR = pathlib.Path(os.getcwd())

DATA_DIR = BASE_DIR / "data"

# Detect TIFF file
snowmap_path = None
for name in ["SnowMap.tif", "SnowMap.tiff"]:
    if (DATA_DIR / name).exists():
        snowmap_path = DATA_DIR / name
        break

deaths_path = DATA_DIR / "deaths_by_bldg.geojson"
pumps_path  = DATA_DIR / "pumps.geojson"

# Try rasterio
try:
    import rasterio
    from rasterio.warp import transform_bounds
    RASTER_OK = True
except:
    RASTER_OK = False

# ============================================================
# LOAD VECTOR DATA
# ============================================================

@st.cache_data(show_spinner=False)
def load_vector_data():
    try:
        deaths = gpd.read_file(deaths_path)
        pumps = gpd.read_file(pumps_path)
    except Exception as e:
        st.error(f"Error loading vector data: {e}")
        return None

    # pick death column
    if "deaths" in deaths.columns:
        death_col = "deaths"
    elif "Count" in deaths.columns:
        death_col = "Count"
    else:
        st.error("No 'deaths' or 'Count' column found in deaths_by_bldg.geojson")
        return None

    deaths[death_col] = pd.to_numeric(deaths[death_col], errors="coerce").fillna(0).astype(int)

    # project to WGS84
    try:
        deaths_wgs = deaths.to_crs(epsg=4326) if deaths.crs else deaths
        pumps_wgs = pumps.to_crs(epsg=4326) if pumps.crs else pumps
    except Exception as e:
        st.error(f"Projection error: {e}")
        return None

    return deaths, pumps, deaths_wgs, pumps_wgs, death_col


# ============================================================
# LOAD RASTER TIFF
# ============================================================

@st.cache_data(show_spinner=False)
def load_snow_tiff():
    if not (RASTER_OK and snowmap_path):
        return None, None

    try:
        with rasterio.open(snowmap_path) as src:
            img = src.read()
            bounds = src.bounds

            # Reproject to WGS84
            wgs_bounds = transform_bounds(
                src.crs, "EPSG:4326",
                bounds.left, bounds.bottom, bounds.right, bounds.top
            )
    except Exception as e:
        st.sidebar.error(f"TIFF cannot be loaded: {e}")
        return None, None

    # Make RGB
    if img.shape[0] == 1:
        gray = img[0]
        rgb = np.stack([gray, gray, gray], axis=0)
    else:
        rgb = img[:3]

    # Convert to (H, W, 3)
    rgb = np.transpose(rgb, (1, 2, 0)).astype("float32")
    rgb = 255 * (rgb - np.min(rgb)) / (np.max(rgb) - np.min(rgb))
    rgb = rgb.astype("uint8")

    bounds_folium = [
        [wgs_bounds[1], wgs_bounds[0]],  # south, west
        [wgs_bounds[3], wgs_bounds[2]],  # north, east
    ]

    return rgb, bounds_folium


# ============================================================
# LOAD DATA
# ============================================================

loaded = load_vector_data()
if loaded is None:
    st.stop()

deaths, pumps, deaths_wgs, pumps_wgs, death_col = loaded
snow_img, snow_bounds = load_snow_tiff()

# ============================================================
# STREAMLIT UI
# ============================================================

st.set_page_config(page_title="John Snow 1854 Dashboard", layout="wide")
st.title("John Snow 1854 Cholera – Interactive Map Dashboard")

# Summary
total_deaths = int(deaths[death_col].sum())
num_buildings = len(deaths)
max_deaths_bldg = int(deaths[death_col].max())
avg_deaths = float(deaths[death_col].mean())

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Deaths", total_deaths)
c2.metric("Buildings", num_buildings)
c3.metric("Max Deaths in a Building", max_deaths_bldg)
c4.metric("Avg Deaths", f"{avg_deaths:.2f}")

st.markdown("---")

# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header("Filters")

min_d = int(deaths[death_col].min())
max_d = int(deaths[death_col].max())

mode = st.sidebar.radio("Filter by:", ["Range", "Exact"])

if mode == "Range":
    dmin, dmax = st.sidebar.slider("Deaths range:", min_d, max_d, (min_d, max_d))
    filtered = deaths_wgs[(deaths_wgs[death_col] >= dmin) &
                          (deaths_wgs[death_col] <= dmax)]
else:
    dv = st.sidebar.slider("Deaths =", min_d, max_d, min_d)
    filtered = deaths_wgs[deaths_wgs[death_col] == dv]

# SnowMap toggle
if snow_img is not None:
    show_snow = st.sidebar.checkbox("Show SnowMap Basemap", value=True)
else:
    st.sidebar.info("No TIFF found or rasterio missing.")

# ============================================================
# MAP
# ============================================================

st.subheader("Interactive Map")

if filtered.empty:
    st.warning("No buildings match your filter.")
    center_lat = deaths_wgs.geometry.y.mean()
    center_lon = deaths_wgs.geometry.x.mean()
else:
    center_lat = filtered.geometry.y.mean()
    center_lon = filtered.geometry.x.mean()

m = folium.Map(location=[center_lat, center_lon], zoom_start=17,
               tiles="CartoDB Positron")

# Base TIFF layer
if snow_img is not None and snow_bounds is not None:
    folium.raster_layers.ImageOverlay(
        snow_img,
        bounds=snow_bounds,
        opacity=0.75,
        name="John Snow Historic Basemap",
        show=show_snow
    ).add_to(m)

# Deaths
death_layer = folium.FeatureGroup("Cholera Deaths")
for _, row in filtered.iterrows():
    d = int(row[death_col])
    folium.CircleMarker(
        [row.geometry.y, row.geometry.x],
        radius=3 + d * 0.4,
        color="red",
        fill=True,
        fill_color="red",
        fill_opacity=0.7,
        popup=f"Deaths: {d}",
    ).add_to(death_layer)
death_layer.add_to(m)

# Pumps
pump_layer = folium.FeatureGroup("Water Pumps")
for _, row in pumps_wgs.iterrows():
    folium.Marker(
        [row.geometry.y, row.geometry.x],
        icon=folium.Icon(color="blue", icon="tint", prefix="fa"),
        popup="Water Pump"
    ).add_to(pump_layer)
pump_layer.add_to(m)

folium.LayerControl().add_to(m)

st_folium(m, width=900, height=600)

# ============================================================
# TABLE
# ============================================================

st.subheader("Filtered Buildings – Attribute Table")
if not filtered.empty:
    st.dataframe(filtered.drop(columns="geometry"))
else:
    st.info("No data to display.")
