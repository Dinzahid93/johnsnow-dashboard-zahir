import os
import pathlib
import geopandas as gpd
import pandas as pd
import streamlit as st
import folium
from shapely.ops import nearest_points
from shapely.geometry import LineString
from streamlit_folium import st_folium
from folium.plugins import HeatMap

# ============================================================
# HEATMAP LEGEND
# ============================================================
def add_heatmap_legend(m):
    legend_html = """
    <div style="
        position: fixed;
        bottom: 30px;
        left: 30px;
        z-index: 9999;
        background: white;
        padding: 10px;
        border-radius: 6px;
        font-size: 14px;
        box-shadow: 0 0 8px rgba(0,0,0,0.3);
        ">
        <b>Heatmap Intensity</b><br>
        <div style="width: 140px; height: 14px;
            background: linear-gradient(to right,
                rgba(0,0,255,0.9),
                rgba(0,255,255,0.9),
                rgba(0,255,0,0.9),
                rgba(255,255,0,0.9),
                rgba(255,0,0,0.9)
            );
            margin-top:5px;
            border:1px solid #999;">
        </div>
        <div style="font-size:11px;">
            Low&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;High
        </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

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
# LOAD DATA
# ============================================================
@st.cache_data
def load_vectors():
    deaths = gpd.read_file(deaths_path)
    pumps  = gpd.read_file(pumps_path)

    if "deaths" in deaths.columns:
        death_col = "deaths"
    elif "Count" in deaths.columns:
        death_col = "Count"
    else:
        st.error("No deaths column found.")
        return None

    deaths[death_col] = pd.to_numeric(deaths[death_col], errors="coerce").fillna(0).astype(int)

    if deaths.crs and deaths.crs.to_epsg() != 4326:
        deaths = deaths.to_crs(4326)
    if pumps.crs and pumps.crs.to_epsg() != 4326:
        pumps = pumps.to_crs(4326)

    return deaths, pumps, death_col

loaded = load_vectors()
if loaded is None:
    st.stop()

deaths, pumps, death_col = loaded

# ============================================================
# NEAREST PUMP ANALYSIS
# ============================================================
def add_nearest_pump_analysis(deaths, pumps):
    deaths_proj = deaths.to_crs(3857)
    pumps_proj  = pumps.to_crs(3857)

    nearest_ids = []
    nearest_dist = []

    for _, row in deaths_proj.iterrows():
        point = row.geometry
        nearest_geom = nearest_points(point, pumps_proj.unary_union)[1]

        pump_row = pumps_proj[pumps_proj.geometry == nearest_geom]
        pump_id = pump_row.iloc[0].get("ID", "N/A") if not pump_row.empty else "N/A"

        distance = point.distance(nearest_geom)

        nearest_ids.append(pump_id)
        nearest_dist.append(distance)

    deaths["nearest_pump_id"] = nearest_ids
    deaths["distance_to_pump_m"] = nearest_dist

    return deaths

deaths = add_nearest_pump_analysis(deaths, pumps)

# ============================================================
# STREAMLIT UI
# ============================================================
st.set_page_config(page_title="John Snow Dashboard", layout="wide")
st.title("John Snow Cholera Map – Heatmap + Distance Lines")

st.sidebar.header("Map Layers")
show_heatmap     = st.sidebar.checkbox("Show Heatmap", value=True)
show_distance_ln = st.sidebar.checkbox("Show Distance Lines", value=True)

# ============================================================
# METRICS
# ============================================================
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Deaths", int(deaths[death_col].sum()))
c2.metric("Buildings", len(deaths))
c3.metric("Max Deaths", int(deaths[death_col].max()))
c4.metric("Avg Distance to Pump (m)", f"{deaths['distance_to_pump_m'].mean():.1f}")

st.markdown("---")

# ============================================================
# MAP
# ============================================================
center_lat = deaths.geometry.y.mean()
center_lon = deaths.geometry.x.mean()

m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=17,
    tiles="CartoDB Positron"
)

# ============================================
