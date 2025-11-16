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

# Find SnowMap TIFF
snowmap_path = None
for fn in ["SnowMap.tif", "SnowMap.tiff"]:
    if (DATA_DIR / fn).exists():
        snowmap_path = DATA_DIR / fn
        break

deaths_path = DATA_DIR / "deaths_by_bldg.geojson"
pumps_path  = DATA_DIR / "pumps.geojson"

# Raster import
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

    # detect column
    if "deaths" in deaths.columns:
        dc = "deaths"
    elif "Count" in deaths.columns:
        dc = "Count"
    else:
        st.error("No deaths column found.")
        return None

    deaths[dc] = pd.to_numeric(deaths[dc], errors="coerce").fillna(0).astype(int)

    # reproject
    deaths_wgs = deaths.to_crs(epsg=4326) if deaths.crs else deaths
    pumps_wgs  = pumps.to_crs(epsg=4326) if pumps.crs else pumps

    return deaths, pumps, deaths_wgs, pumps_wgs, dc


# ============================================================
# LOAD SNOWMAP TIFF (NO CACHE)
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
        st.sidebar.error(f"TIFF load error: {e}")
        return None, None

    # No CRS → auto-fit to data bounds
    if tif_crs is None:
        minx, miny, maxx, maxy = deaths_wgs.total_bounds
        pad_x = (maxx - minx) * 0.05
        pad_y = (maxy - miny) * 0.05
        bounds = [
            [miny - pad_y, minx - pad_x], 
            [maxy + pad_y, maxx + pad_x]
        ]
    else:
        try:
            wb = transform_bounds(
                tif_crs, "EPSG:4326",
                b.left, b.bottom, b.right, b.top
            )
            bounds = [[wb[1], wb[0]], [wb[3], wb[2]]]
        except:
            st.sidebar.error("CRS transform failed.")
            return None, None

    # Convert bands to RGB
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
# LOAD ALL DATA
# ============================================================

loaded = load_vector_data()
if loaded is None:
    st.stop()

deaths, pumps, deaths_wgs, pumps_wgs, death_col = loaded
snow_img, snow_bounds = load_snowmap(deaths_wgs)


# ============================================================
# UI HEADER
# ============================================================

st.set_page_config(page_title="John Snow Dashboard", layout="wide")
st.title("John Snow 1854 Cholera – Interactive Dashboard")

# Summary
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Deaths", int(deaths[death_col].sum()))
c2.metric("Buildings", len(deaths))
c3.metric("Max Deaths in a Building", int(deaths[death_col].max()))
c4.metric("Average Deaths", f"{deaths[death_col].mean():.2f}")

st.markdown("---")


# ============================================================
# SIDEBAR FILTERS
# ============================================================

st.sidebar.header("Filters")

mind = int(deaths[death_col].min())
maxd = int(deaths[death_col].max())

mode = st.sidebar.radio("Filter by:", ["Range", "Exact"])

if mode == "Range":
    dmin, dmax = st.sidebar.slider("Deaths range", mind, maxd, (mind, maxd))
    filtered = deaths_wgs[
        (deaths_wgs[death_col] >= dmin) &
        (deaths_wgs[death_col] <= dmax)
    ]
else:
    dv = st.sidebar.slider("Deaths =", mind, maxd, mind)
    filtered = deaths_wgs[deaths_wgs[death_col] == dv]

# Basemap toggle
if snow_img is not None:
    show_snow = st.sidebar.checkbox("Show SnowMap Basemap", True)
else:
    st.sidebar.info("SnowMap basemap unavailable.")


# ============================================================
# MAP
# ============================================================

st.subheader("Interactive Map")

center_lat = deaths_wgs.geometry.y.mean()
center_lon = deaths_wgs.geometry.x.mean()

m = folium.Map(location=[center_lat, center_lon], zoom_start=17,
               tiles="CartoDB Positron")

# TIFF overlay
if snow_img is not None and snow_bounds is not None:
    folium.raster_layers.ImageOverlay(
        snow_img,
        snow_bounds,
        name="SnowMap",
        opacity=0.75,
        show=show_snow
    ).add_to(m)

# Deaths
fg_death = folium.FeatureGroup("Deaths")
for _, row in filtered.iterrows():
    d = int(row[death_col])
    folium.CircleMarker(
        [row.geometry.y, row.geometry.x],
        radius=3 + 0.4 * d,
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

st_folium(m, width=900, height=600)


# ============================================================
# ATTRIBUTE TABLES
# ============================================================

st.subheader("Filtered Buildings – Attributes")
st.dataframe(filtered.drop(columns="geometry"))

st.subheader("Water Pumps – Attributes")
st.dataframe(pumps_wgs.drop(columns="geometry"))
