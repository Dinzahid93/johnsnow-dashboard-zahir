# ============================================================
# johnsnow_dashboard_app.py  (with optional SnowMap.tif basemap)
# ============================================================

import os
import numpy as np
import pandas as pd
import geopandas as gpd
import folium
import streamlit as st
from streamlit_folium import st_folium

# Try to import rasterio for TIFF overlay
try:
    import rasterio
    from rasterio.warp import transform_bounds
    RASTER_OK = True
except ImportError:
    RASTER_OK = False

# -----------------------------
# PATHS – RELATIVE TO REPO ROOT
# -----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

deaths_path = os.path.join(DATA_DIR, "deaths_by_bldg.geojson")
pumps_path  = os.path.join(DATA_DIR, "pumps.geojson")
snowmap_path = os.path.join(DATA_DIR, "SnowMap.tif")  # optional

# -----------------------------
# LOAD VECTOR DATA (CACHED)
# -----------------------------
@st.cache_data
def load_vector_data():
    deaths = gpd.read_file(deaths_path)
    pumps  = gpd.read_file(pumps_path)

    # Decide death column
    if "deaths" in deaths.columns:
        death_col = "deaths"
    elif "Count" in deaths.columns:
        death_col = "Count"
    else:
        raise ValueError("No 'deaths' or 'Count' column in deaths_by_bldg.geojson")

    deaths[death_col] = pd.to_numeric(deaths[death_col], errors="coerce").fillna(0).astype(int)

    # Reproject to WGS84 if needed
    if deaths.crs is not None and deaths.crs.to_epsg() != 4326:
        deaths_wgs = deaths.to_crs(epsg=4326)
    else:
        deaths_wgs = deaths

    if pumps.crs is not None and pumps.crs.to_epsg() != 4326:
        pumps_wgs = pumps.to_crs(epsg=4326)
    else:
        pumps_wgs = pumps

    return deaths, pumps, deaths_wgs, pumps_wgs, death_col

# -----------------------------
# LOAD RASTER DATA (CACHED)
# -----------------------------
@st.cache_data
def load_snowmap_tiff():
    """Return (img_rgb, [[south, west],[north, east]]) or (None, None)."""
    if not (RASTER_OK and os.path.exists(snowmap_path)):
        return None, None

    with rasterio.open(snowmap_path) as src:
        img = src.read()          # (bands, H, W)
        bounds = src.bounds
        tif_crs = src.crs

        # Transform bounds to WGS84 for Folium
        wgs_bounds = transform_bounds(
            tif_crs, "EPSG:4326",
            bounds.left, bounds.bottom,
            bounds.right, bounds.top
        )  # (west, south, east, north)

    # Make RGB
    if img.shape[0] == 1:
        gray = img[0]
        img_rgb = np.stack([gray, gray, gray], axis=0)
    elif img.shape[0] >= 3:
        img_rgb = img[:3]
    else:
        return None, None

    # (bands, H, W) -> (H, W, bands)
    img_rgb = np.transpose(img_rgb, (1, 2, 0))

    # Normalize 0–255 as uint8
    img_rgb = img_rgb.astype("float32")
    img_rgb = 255 * (img_rgb - img_rgb.min()) / (img_rgb.max() - img_rgb.min())
    img_rgb = img_rgb.astype("uint8")

    # Bounds for Folium: [[south, west], [north, east]]
    bounds_folium = [
        [wgs_bounds[1], wgs_bounds[0]],
        [wgs_bounds[3], wgs_bounds[2]],
    ]

    return img_rgb, bounds_folium

# Load data
deaths, pumps, deaths_wgs, pumps_wgs, death_col = load_vector_data()
snow_img, snow_bounds = load_snowmap_tiff()

# ============================================================
# STREAMLIT LAYOUT
# ============================================================

st.set_page_config(
    page_title="John Snow 1854 Cholera Dashboard",
    layout="wide"
)

st.title("John Snow 1854 Cholera – Interactive Dashboard")

st.markdown(
    """
Data used:

- **deaths_by_bldg** – deaths aggregated to buildings  
- **pumps** – water pump locations  
- **SnowMap.tif** – historical John Snow basemap (optional overlay)

Use the sidebar to filter by number of deaths and to toggle the SnowMap basemap.
"""
)

# -----------------------------
# SUMMARY METRICS
# -----------------------------
total_deaths    = int(deaths[death_col].sum())
num_buildings   = int(len(deaths))
max_deaths_bldg = int(deaths[death_col].max())
avg_deaths_bldg = float(deaths[death_col].mean())

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total deaths (all buildings)", f"{total_deaths}")
c2.metric("Number of buildings", f"{num_buildings}")
c3.metric("Max deaths in a building", f"{max_deaths_bldg}")
c4.metric("Avg deaths per building", f"{avg_deaths_bldg:.2f}")

st.markdown("---")

# -----------------------------
# SIDEBAR FILTERS
# -----------------------------
st.sidebar.header("Filters")

min_d = int(deaths[death_col].min())
max_d = int(deaths[death_col].max())

filter_mode = st.sidebar.radio(
    "Filter mode",
    options=["Range", "Exact value"],
    index=0
)

if filter_mode == "Range":
    death_range = st.sidebar.slider(
        "Select deaths range",
        min_value=min_d,
        max_value=max_d,
        value=(min_d, max_d),
        step=1
    )
    st.sidebar.write(
        f"Showing buildings with **{death_col} between {death_range[0]} and {death_range[1]}**."
    )
    filtered = deaths_wgs[
        (deaths_wgs[death_col] >= death_range[0]) &
        (deaths_wgs[death_col] <= death_range[1])
    ]
else:
    death_value = st.sidebar.slider(
        "Show only buildings with deaths =",
        min_value=min_d,
        max_value=max_d,
        value=min_d,
        step=1
    )
    st.sidebar.write(
        f"Showing buildings with **{death_col} = {death_value}** only."
    )
    filtered = deaths_wgs[deaths_wgs[death_col] == death_value]

# Checkbox to toggle SnowMap basemap if available
show_snowmap = False
if snow_img is not None and snow_bounds is not None:
    show_snowmap = st.sidebar.checkbox(
        "Show SnowMap basemap (TIFF)",
        value=True
    )
else:
    st.sidebar.info("SnowMap.tif not found or rasterio not available – using only web basemap.")

# -----------------------------
# BUILD MAP
# -----------------------------
st.subheader("Interactive Map")

if not filtered.empty:
    center_lat = filtered.geometry.y.mean()
    center_lon = filtered.geometry.x.mean()
else:
    center_lat = deaths_wgs.geometry.y.mean()
    center_lon = deaths_wgs.geometry.x.mean()

m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=17,
    tiles="CartoDB Positron"
)

# --- Optional SnowMap overlay ---
if snow_img is not None and snow_bounds is not None:
    folium.raster_layers.ImageOverlay(
        image=snow_img,
        bounds=snow_bounds,
        opacity=0.8,
        name="SnowMap basemap (TIFF)",
        show=show_snowmap
    ).add_to(m)

# --- Deaths layer (filtered) ---
death_layer = folium.FeatureGroup(name="Deaths by Building (filtered)")

for _, row in filtered.iterrows():
    lat, lon = row.geometry.y, row.geometry.x
    d = int(row[death_col])

    popup_html = "<b>DEATH LOCATION</b><br><br>"
    for col in deaths.columns:
        if col != "geometry":
            val = row.get(col, "")
            popup_html += f"{col}: {val}<br>"

    size = 3 + 0.4 * d

    folium.CircleMarker(
        location=[lat, lon],
        radius=size,
        color="red",
        fill=True,
        fill_color="red",
        fill_opacity=0.7,
        popup=folium.Popup(popup_html, max_width=300),
    ).add_to(death_layer)

death_layer.add_to(m)

# --- Pumps layer ---
pumps_layer = folium.FeatureGroup(name="Water Pumps")

for _, row in pumps_wgs.iterrows():
    lat, lon = row.geometry.y, row.geometry.x

    popup_html = "<b>WATER PUMP</b><br><br>"
    for col in pumps.columns:
        if col != "geometry":
            popup_html += f"{col}: {row[col]}<br>"

    folium.Marker(
        location=[lat, lon],
        icon=folium.Icon(color="blue", icon="tint", prefix="fa"),
        popup=folium.Popup(popup_html, max_width=300)
    ).add_to(pumps_layer)

pumps_layer.add_to(m)

folium.LayerControl().add_to(m)
st_folium(m, width=900, height=600)

# -----------------------------
# TABLE SECTION
# -----------------------------
st.subheader("Filtered Buildings – Attribute Table")

if not filtered.empty:
    table_df = pd.DataFrame(filtered.drop(columns="geometry"))
else:
    table_df = pd.DataFrame(columns=[c for c in deaths.columns if c != "geometry"])

st.dataframe(table_df)

if filter_mode == "Range":
    st.markdown(
        f"Showing **{len(filtered)}** buildings with {death_col} between "
        f"**{death_range[0]}** and **{death_range[1]}**."
    )
else:
    st.markdown(
        f"Showing **{len(filtered)}** buildings with {death_col} = **{death_value}**."
    )
