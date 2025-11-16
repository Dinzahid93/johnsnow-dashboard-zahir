import os
import pathlib
import numpy as np
import pandas as pd
import geopandas as gpd
import folium
import streamlit as st
from streamlit_folium import st_folium


# ============================================================
# SAFE PATHS
# ============================================================

try:
    BASE_DIR = pathlib.Path(__file__).parent
except:
    BASE_DIR = pathlib.Path(os.getcwd())

DATA_DIR = BASE_DIR / "data"

# detect TIFF
snowmap_path = None
for tifname in ["SnowMap.tif", "SnowMap.tiff"]:
    if (DATA_DIR / tifname).exists():
        snowmap_path = DATA_DIR / tifname
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

    if "deaths" in deaths.columns:
        dc = "deaths"
    elif "Count" in deaths.columns:
        dc = "Count"
    else:
        st.error("No deaths column found.")
        return None

    deaths[dc] = pd.to_numeric(deaths[dc], errors="coerce").fillna(0).astype(int)

    deaths_wgs = deaths.to_crs(epsg=4326)
    pumps_wgs  = pumps.to_crs(epsg=4326)

    return deaths, pumps, deaths_wgs, pumps_wgs, dc


# ============================================================
# TIFF LOAD — NO CACHE
# ============================================================

def load_snowmap_tif(deaths_wgs):

    if not (RASTER_OK and snowmap_path):
        return None, None

    try:
        with rasterio.open(snowmap_path) as src:
            arr = src.read()
            tif_crs = src.crs
            b = src.bounds
    except Exception as e:
        st.error(f"TIFF error: {e}")
        return None, None

    # If no CRS → auto-fit
    if tif_crs is None:
        minx, miny, maxx, maxy = deaths_wgs.total_bounds
        px = (maxx - minx) * 0.05
        py = (maxy - miny) * 0.05
        bounds = [[miny - py, minx - px], [maxy + py, maxx + px]]
    else:
        try:
            wb = transform_bounds(tif_crs, "EPSG:4326",
                                  b.left, b.bottom, b.right, b.top)
            bounds = [[wb[1], wb[0]], [wb[3], wb[2]]]
        except:
            bounds = [[b.bottom, b.left], [b.top, b.right]]

    # convert to RGB
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
snow_img, snow_bounds = load_snowmap_tif(deaths_wgs)


# ============================================================
# UI HEADER
# ============================================================

st.set_page_config(page_title="John Snow Cholera Dashboard", layout="wide")
st.title("John Snow 1854 Cholera – GIS Dashboard")


# METRIC BAR
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Deaths", int(deaths[death_col].sum()))
c2.metric("Buildings", len(deaths))
c3.metric("Max Deaths", int(deaths[death_col].max()))
c4.metric("Avg Deaths", f"{deaths[death_col].mean():.2f}")

st.markdown("---")


# ============================================================
# MAP SETTINGS
# ============================================================

with st.expander("🗺️ Basemap & Marker Settings"):
    basemap_choice = st.selectbox(
        "Basemap",
        ["cartodbpositron", "OpenStreetMap", "Stamen Toner"]
    )
    opacity = st.slider("SnowMap Opacity", 0.0, 1.0, 0.75, 0.05)
    scale_factor = st.slider("Death Marker Scale", 0.2, 1.5, 0.4, 0.1)


# ============================================================
# ALIGNMENT TOOLS
# ============================================================

with st.expander("📐 SnowMap Alignment Tools (Shift / Scale / Rotate)"):
    shift_x = st.slider("Shift East/West", -0.003, 0.003, 0.0, 0.0001)
    shift_y = st.slider("Shift North/South", -0.003, 0.003, 0.0, 0.0001)
    scale_adj = st.slider("Scale (Zoom in/out)", 0.90, 1.10, 1.00, 0.005)
    rotation_deg = st.slider("Rotation (degrees)", -10.0, 10.0, 0.0, 0.1)


# ============================================================
# MAP
# ============================================================

st.subheader("Interactive Map")

center_lat = deaths_wgs.geometry.y.mean()
center_lon = deaths_wgs.geometry.x.mean()

m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=17,
    tiles=basemap_choice
)

# Apply alignment to bounds
if snow_img is not None and snow_bounds is not None:

    (south, west), (north, east) = snow_bounds

    # Center for scale/rotation
    cx = (west + east) / 2
    cy = (south + north) / 2

    # SCALE
    west = cx + (west - cx) * scale_adj
    east = cx + (east - cx) * scale_adj
    south = cy + (south - cy) * scale_adj
    north = cy + (north - cy) * scale_adj

    # SHIFT
    west += shift_x
    east += shift_x
    south += shift_y
    north += shift_y

    # ROTATION
    # Convert bounds to 4 corner points
    pts = np.array([
        [west, south],
        [west, north],
        [east, north],
        [east, south]
    ])

    theta = np.radians(rotation_deg)
    rot = np.array([[np.cos(theta), -np.sin(theta)],
                    [np.sin(theta),  np.cos(theta)]])

    pts_rot = (pts - [cx, cy]) @ rot + [cx, cy]

    # recompute bounding box
    west_new, south_new = pts_rot.min(axis=0)
    east_new, north_new = pts_rot.max(axis=0)

    aligned_bounds = [[south_new, west_new], [north_new, east_new]]

    folium.raster_layers.ImageOverlay(
        snow_img,
        aligned_bounds,
        opacity=opacity,
        name="SnowMap (Aligned)",
        show=True
    ).add_to(m)


# Deaths
fg_d = folium.FeatureGroup("Deaths")
for _, row in deaths_wgs.iterrows():
    d = int(row[death_col])
    folium.CircleMarker(
        [row.geometry.y, row.geometry.x],
        radius=3 + d * scale_factor,
        color="red",
        fill=True,
        fill_opacity=0.7,
        popup=f"Deaths: {d}"
    ).add_to(fg_d)
fg_d.add_to(m)

# Pumps
fg_p = folium.FeatureGroup("Pumps")
for _, row in pumps_wgs.iterrows():
    txt = "<b>Water Pump</b><br>" + "<br>".join(
        f"{c}: {row[c]}" for c in pumps.columns if c != "geometry"
    )
    folium.Marker(
        [row.geometry.y, row.geometry.x],
        icon=folium.Icon(color="blue", icon="tint"),
        popup=txt
    ).add_to(fg_p)
fg_p.add_to(m)

folium.LayerControl().add_to(m)


# 🟢 do not allow rerun on map drag
st_folium(
    m,
    width=1100,
    height=650,
    key="mainmap",
    returned_objects=[]
)


# ============================================================
# TABLES
# ============================================================

st.markdown("---")
st.subheader("Building Attributes")
st.dataframe(deaths_wgs.drop(columns="geometry"))

st.subheader("Pump Attributes")
st.dataframe(pumps_wgs.drop(columns="geometry"))
