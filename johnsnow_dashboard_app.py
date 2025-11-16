# ============================================================
# John Snow 1854 Cholera Dashboard – FINAL WORKING VERSION
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
# SAFE PATH HANDLING (NO __file__ ISSUES)
# ============================================================

try:
    BASE_DIR = pathlib.Path(__file__).parent
except:
    BASE_DIR = pathlib.Path(os.getcwd())

DATA_DIR = BASE_DIR / "data"

# detect SnowMap.tif or SnowMap.tiff
snowmap_path = None
for n in ["SnowMap.tif", "SnowMap.tiff"]:
    if (DATA_DIR / n).exists():
        snowmap_path = DATA_DIR / n
        break

deaths_path = DATA_DIR / "deaths_by_bldg.geojson"
pumps_path  = DATA_DIR / "pumps.geojson"

# rasterio import
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
        pumps  = gpd.read_file(pumps_path)
    except Exception as e:
        st.error(f"Vector data error: {e}")
        return None

    # detect deaths column
    if "deaths" in deaths.columns:
        death_col = "deaths"
    elif "Count" in deaths.columns:
        death_col = "Count"
    else:
        st.error("No 'deaths' or 'Count' column found in deaths_by_bldg.geojson")
        return None

    deaths[death_col] = pd.to_numeric(deaths[death_col], errors="coerce").fillna(0).astype(int)

    # reproject if needed
    if deaths.crs:
        deaths_wgs = deaths.to_crs(epsg=4326)
    else:
        deaths_wgs = deaths

    if pumps.crs:
        pumps_wgs = pumps.to_crs(epsg=4326)
    else:
        pumps_wgs = pumps

    return deaths, pumps, deaths_wgs, pumps_wgs, death_col


# ============================================================
# LOAD TIFF (EVEN IF CRS IS MISSING)
# ============================================================

@st.cache_data(show_spinner=False)
def load_snowmap(deaths_wgs):
    """
    Load TIFF even if CRS is missing.
    Auto-generates geographic bounds from data.
    """

    if not (RASTER_OK and snowmap_path):
        return None, None

    try:
        with rasterio.open(snowmap_path) as src:
            img = src.read()
            tif_crs = src.crs
            b = src.bounds
    except Exception as e:
        st.sidebar.error(f"TIFF cannot be loaded: {e}")
        return None, None

    # NO CRS → auto-bounds using deaths data extent
    if tif_crs is None:
        st.sidebar.warning("TIFF has no CRS — using auto-fit bounds.")

        minx, miny, maxx, maxy = deaths_wgs.total_bounds

        pad_x = (maxx - minx) * 0.05
        pad_y = (maxy - miny) * 0.05

        west  = minx - pad_x
        south = miny - pad_y
        east  = maxx + pad_x
        north = maxy + pad_y

        bounds_folium = [[south, west], [north, east]]

    else:
        # normal case → convert to WGS84
        try:
            wb = transform_bounds(
                tif_crs, "EPSG:4326",
                b.left, b.bottom, b.right, b.top
            )
            bounds_folium = [
                [wb[1], wb[0]],
                [wb[3], wb[2]]
            ]
        except:
            st.sidebar.error("TIFF CRS transform failed.")
            return None, None

    # convert bands → RGB
    if img.shape[0] == 1:
        g = img[0]
        rgb = np.stack([g, g, g], axis=0)
    else:
        rgb = img[:3]

    rgb = np.transpose(rgb, (1, 2, 0)).astype("float32")
    rgb = 255 * (rgb - rgb.min()) / (rgb.max() - rgb.min())
    rgb = rgb.astype("uint8")

    return rgb, bounds_folium


# ============================================================
# LOAD DATA
# ============================================================

loaded = load_vector_data()
if loaded is None:
    st.stop()

deaths, pumps, deaths_wgs, pumps_wgs, death_col = loaded
snow_img, snow_bounds = load_snowmap(deaths_wgs)


# ============================================================
# STREAMLIT UI
# ============================================================

st.set_page_config(layout="wide", page_title="John Snow 1854 Dashboard")

st.title("John Snow 1854 Cholera – Interactive Dashboard")

# Summary
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Deaths", int(deaths[death_col].sum()))
c2.metric("Buildings", len(deaths))
c3.metric("Max Deaths in a Building", int(deaths[death_col].max()))
c4.metric("Average Deaths", f"{float(deaths[death_col].mean()):.2f}")

st.markdown("---")


# ============================================================
# SIDEBAR FILTERS
# ============================================================

st.sidebar.header("Filter Buildings")

min_d = int(deaths[death_col].min())
max_d = int(deaths[death_col].max())

mode = st.sidebar.radio("Filter by:", ["Range", "Exact"])

if mode == "Range":
    dmin, dmax = st.sidebar.slider("Deaths range", min_d, max_d, (min_d, max_d))
    filtered = deaths_wgs[(deaths_wgs[death_col] >= dmin) & (deaths_wgs[death_col] <= dmax)]
else:
    dv = st.sidebar.slider("Deaths =", min_d, max_d, min_d)
    filtered = deaths_wgs[deaths_wgs[death_col] == dv]

if snow_img is not None:
    show_snow = st.sidebar.checkbox("Show SnowMap Basemap", True)
else:
    st.sidebar.info("No TIFF found or rasterio not installed.")


# ============================================================
# MAP
# ============================================================

st.subheader("Cholera Map")

center_lat = deaths_wgs.geometry.y.mean()
center_lon = deaths_wgs.geometry.x.mean()

m = folium.Map(location=[center_lat, center_lon], zoom_start=17, tiles="CartoDB Positron")

# TIFF overlay
if snow_img is not None and snow_bounds is not None:
    folium.raster_layers.ImageOverlay(
        snow_img,
        bounds=snow_bounds,
        name="SnowMap",
        opacity=0.75,
        show=show_snow
    ).add_to(m)

# deaths layer
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
        popup=f"Deaths: {d}"
    ).add_to(death_layer)
death_layer.add_to(m)

# pumps layer
pump_layer = folium.FeatureGroup("Water Pumps")
for _, row in pumps_wgs.iterrows():
    folium.Marker(
        [row.geometry.y, row.geometry.x],
        icon=folium.Icon(color="blue", icon="tint", prefix="fa"),
        popup="<b>Water Pump</b><br>" + "<br>".join(
            f"{col}: {row[col]}" for col in pumps.columns if col != "geometry"
        )
    ).add_to(pump_layer)
pump_layer.add_to(m)

folium.LayerControl().add_to(m)

st_folium(m, width=900, height=600)

# ============================================================
# TABLES
# ============================================================

st.subheader("Filtered Buildings – Attribute Table")
st.dataframe(filtered.drop(columns="geometry"))

st.subheader("Water Pumps – Attribute Table")
st.dataframe(pumps_wgs.drop(columns="geometry"))
