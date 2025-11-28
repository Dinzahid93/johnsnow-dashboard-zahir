import os
import pathlib
import geopandas as gpd
import pandas as pd
import streamlit as st
import folium
from shapely.ops import nearest_points
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
# PATH SETUP
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
    pumps  = gpd.read_file(pumps_path)

    if "deaths" in deaths.columns:
        death_col = "deaths"
    elif "Count" in deaths.columns:
        death_col = "Count"
    else:
        st.error("No deaths field found.")
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

    pump_geoms = pumps_proj.geometry
    nearest_ids = []
    nearest_dist = []

    for _, row in deaths_proj.iterrows():
        point = row.geometry
        nearest_geom = nearest_points(point, pump_geoms.unary_union)[1]
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
# STREAMLIT PAGE CONFIG
# ============================================================
st.set_page_config(page_title="John Snow’s 1854 Cholera Map", layout="wide")


# ============================================================
# TITLE + IMAGE + HISTORICAL OVERVIEW
# ============================================================
st.title("John Snow’s 1854 Cholera Map")

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("""
    ### 🏛️ Historical Overview  

    In 1854, a severe cholera outbreak struck the Soho district of London.  
    Physician **Dr. John Snow** conducted a groundbreaking spatial investigation  
    by mapping cholera deaths and identifying proximity to water pumps.

    His work demonstrated that the outbreak was linked to a contaminated  
    pump on Broad Street — marking one of the earliest and most influential  
    cases of **epidemiology and spatial analysis**.

    This dashboard recreates the iconic map using modern GIS techniques.
    """)

with col2:
    st.image("data/John_Snow.jpg", caption="Dr. John Snow (1813–1858)", use_column_width=True)

st.markdown("---")


# ============================================================
# TABS: HEATMAP + SPIDER WEB
# ============================================================
tab1, tab2 = st.tabs(["🔥 Heatmap of Deaths", "🕸 Spider Web Analysis"])

# -----------------------------
# TAB 1 — HEATMAP
# -----------------------------
with tab1:
    st.subheader("Heatmap of Cholera Deaths")
    st.markdown("""
    The heatmap highlights areas with higher concentrations of cholera deaths.  
    **Red zones indicate outbreak hotspots**, which help researchers understand  
    how contaminated water sources contributed to transmission.
    """)

    center_lat = deaths.geometry.y.mean()
    center_lon = deaths.geometry.x.mean()

    m1 = folium.Map(location=[center_lat, center_lon], zoom_start=17, tiles="OpenStreetMap")

    heat_data = [[row.geometry.y, row.geometry.x, row[death_col]] for _, row in deaths.iterrows()]

    HeatMap(heat_data, radius=25, blur=15, max_zoom=17).add_to(m1)
    add_heatmap_legend(m1)

    st_folium(m1, width=1000, height=600)


# -----------------------------
# TAB 2 — SPIDER WEB ANALYSIS
# -----------------------------
with tab2:
    st.subheader("Spider Web Analysis (Death → Nearest Pump)")
    st.markdown("""
    Each line connects a death location to its **nearest water pump**.  
    This visualization helps identify which pumps likely influenced  
    the spread of cholera during the 1854 outbreak.
    """)

    m2 = folium.Map(location=[center_lat, center_lon], zoom_start=17, tiles="OpenStreetMap")

    # Pumps
    for _, row in pumps.iterrows():
        folium.Marker(
            [row.geometry.y, row.geometry.x],
            icon=folium.Icon(color="blue", icon="tint"),
            popup="Pump"
        ).add_to(m2)

    # Deaths + spider lines
    pump_lookup = {str(row.get("ID", "")): (row.geometry.y, row.geometry.x) for _, row in pumps.iterrows()}

    for _, row in deaths.iterrows():
        d_lat = row.geometry.y
        d_lon = row.geometry.x
        nearest_id = str(row.get("nearest_pump_id", ""))

        # draw line only if pump exists
        for _, prow in pumps.iterrows():
            if str(prow.get("ID", "")) == nearest_id:
                p_lat = prow.geometry.y
                p_lon = prow.geometry.x

                folium.PolyLine([(d_lat, d_lon), (p_lat, p_lon)],
                                color="black", weight=1.5, opacity=0.8).add_to(m2)

                break

        folium.CircleMarker([d_lat, d_lon], radius=4, color="red", fill=True).add_to(m2)

    st_folium(m2, width=1000, height=600)
