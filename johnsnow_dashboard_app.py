import os
import pathlib
import numpy as np
import pandas as pd
import geopandas as gpd
import folium
import streamlit as st
from streamlit_folium import st_folium


# ============================================================
# SAFE PATH HANDLING
# ============================================================

try:
    BASE_DIR = pathlib.Path(__file__).parent
except:
    BASE_DIR = pathlib.Path(os.getcwd())

DATA_DIR = BASE_DIR / "data"

# SnowMap TIFF — detect existence
snowmap_path = None
for name in ["SnowMap.tif", "SnowMap.tiff"]:
    if (DATA_DIR / name).exists():
        snowmap_path = DATA_DIR / name
        break

deaths_path = DATA_DIR / "deaths_by_bldg.geojson"
pumps_path  = DATA_DIR / "pumps.geojson"

# raster library
try:
    import rasterio
    from rasterio.warp import transform_bounds
    RASTER_OK = True
except:
    RASTER_OK = False


# ============================================================
# LOAD VECTOR DATA
# ============================================================

@st.cache_data
def load_vector():
    deaths = gpd.read_file(deaths_path)
    pumps = gpd.read_file(pumps_path)

    # detect death column
    if "deaths" in deaths.columns:
        death_col = "deaths"
    elif "Count" in deaths.columns:
        death_col = "Count"
    else:
        st.error("No deaths column found!")
        return None

    deaths[death_col] = pd.to_numeric(deaths[death_col], errors="coerce").fillna(0).astype(int)

    deaths_wgs = deaths.to_crs(epsg=4326)
    pumps_wgs  = pumps.to_crs(epsg=4326)

    return deaths, pumps, deaths_wgs, pumps_wgs, death_col


# ============================================================
# LOAD SNOWMAP TIFF — NO CACHE
# ============================================================

def load_snowmap(deaths_wgs):

    if not (RASTER_OK and snowmap_path):
        return None, None

    try:
        with rasterio.open(snowmap_path) as src:
            arr = src.read()
            tif_crs = src.crs
            b = src.bounds
    except Exception as e:
        st.error(f"TIFF load error: {e}")
        return None, None

    # If TIFF has NO CRS, auto-fit to data bounds
    if tif_crs is None:
        minx, miny, maxx, maxy = deaths_wgs.total_bounds
        px = 0.05 * (maxx - minx)
        py = 0.05 * (maxy - miny)
        bounds = [[miny - py, minx - px], [maxy + py, maxx + px]]
    else:
        try:
            wb = transform_bounds(
                tif_crs, "EPSG:4326",
                b.left, b.bottom, b.right, b.top
            )
            bounds = [[wb[1], wb[0]], [wb[3], wb[2]]]
        except:
            bounds = [[b.bottom, b.left], [b.top, b.right]]

    # Convert to RGB
    if arr.shape[0] == 1:
        g = arr[0]
        rgb = np.stack([g, g, g], axis=0)
    else:
        rgb = arr[:3]

    rgb = np.transpose(rgb, (1, 2, 0)).astype(float)
    rgb = 255 * (rgb - rgb.min()) / (rgb.max() - rgb.min())
    rgb = rgb.astype(np.uint8)

    return rgb, bounds


# ============================================================
# LOAD DATA
# ============================================================

loaded = load_vector()
if loaded is None:
    st.stop()

deaths, pumps, deaths_wgs, pumps_wgs, death_col = loaded
snow_img, snow_bounds = load_snowmap(deaths_wgs)


# ============================================================
# UI LAYOUT
# ============================================================

st.set_page_config(page_title="John Snow Dashboard", layout="wide")
st.title("John Snow 1854 Cholera – GIS Dashboard")


# TOP METRICS
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Deaths", int(deaths[death_col].sum()))
c2.metric("Buildings", len(deaths))
c3.metric("Max Deaths per Building", int(deaths[death_col].max()))
c4.metric("Average Deaths", f"{deaths[death_col].mean():.2f}")

st.markdown("---")


# MAP SETTINGS EXPANDER
with st.expander("🗺️ Map Settings"):
    basemap_choice = st.selectbox(
        "Basemap Style",
        ["cartodbpositron", "OpenStreetMap", "Stamen Toner"]
    )

    opacity = st.slider("SnowMap Opacity", 0.0, 1.0, 0.75, 0.05)
    scaler = st.slider("Death Marker Scale", 0.2, 1.5, 0.4, 0.1)


# ============================================================
# BUILD MAP
# ============================================================

st.subheader("Interactive Map")

center_lat = deaths_wgs.geometry.y.mean()
center_lon = deaths_wgs.geometry.x.mean()

m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=17,
    tiles=basemap_choice
)

# SnowMap overlay
if snow_img is not None:
    folium.raster_layers.ImageOverlay(
        snow_img,
        snow_bounds,
        name="SnowMap",
        opacity=opacity,
        show=True
    ).add_to(m)

# Death layer
fg_death = folium.FeatureGroup("Deaths")
for _, row in deaths_wgs.iterrows():
    d = int(row[death_col])
    folium.CircleMarker(
        [row.geometry.y, row.geometry.x],
        radius=3 + d * scaler,
        color="red",
        fill=True,
        fill_opacity=0.7,
        popup=f"Deaths: {d}"
    ).add_to(fg_death)
fg_death.add_to(m)

# Pumps
fg_pump = folium.FeatureGroup("Pumps")
for _, row in pumps_wgs.iterrows():
    info = "<b>Water Pump</b><br>" + "<br>".join(
        f"{col}: {row[col]}" for col in pumps.columns if col != "geometry"
    )
    folium.Marker(
        [row.geometry.y, row.geometry.x],
        icon=folium.Icon(color="blue", icon="tint", prefix="fa"),
        popup=info
    ).add_to(fg_pump)
fg_pump.add_to(m)

folium.LayerControl().add_to(m)

# 🟢 FIX: No rerun when moving the map
st_folium(
    m,
    width=1100,
    height=650,
    key="mainmap",
    returned_objects=[]  # prevents rerun on pan/zoom
)


# ============================================================
# TABLES
# ============================================================

st.markdown("---")

st.subheader("Building Attributes")
st.dataframe(deaths_wgs.drop(columns="geometry"))

st.subheader("Pump Attributes")
st.dataframe(pumps_wgs.drop(columns="geometry"))
