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
    st.image(
        r"C:\DIN PERSONAL\4. uitm\Lab Dr Eran\Assignment\John_Snow.jpg",
        caption="Dr. John Snow (1813–1858)",
        use_column_width=True
    )

st.markdown("---")


# ============================================================
# SIDEBAR LAYERS
# ============================================================
st.sidebar.header("Map Layers")
show_heatmap = st.sidebar.checkbox("Show Heatmap", value=True)
show_spider = st.sidebar.checkbox("Show Spider Lines (Death → Pump)", value=False)


# ============================================================
# SUMMARY + BAR CHART
# ============================================================
total_deaths = int(deaths[death_col].sum())
max_deaths = int(deaths[death_col].max())
avg_distance = deaths["distance_to_pump_m"].mean()

st.subheader("Summary Statistics")
st.write(f"**Total Recorded Deaths:** {total_deaths}")
st.write(f"**Maximum Death in a Building:** {max_deaths}")
st.write(f"**Average Distance to Nearest Pump:** {avg_distance:.1f} meters")

st.bar_chart(deaths[death_col])

st.markdown("---")


# ============================================================
# INTERACTIVE MAP
# ============================================================
st.subheader("Interactive Map")

center_lat = deaths.geometry.y.mean()
center_lon = deaths.geometry.x.mean()

m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=17,
    tiles="OpenStreetMap"
)

# --- Heatmap ---
if show_heatmap:
    heat_data = [
        [row.geometry.y, row.geometry.x, row[death_col]]
        for _, row in deaths.iterrows()
    ]

    HeatMap(
        heat_data,
        name="Heatmap",
        radius=25,
        blur=15,
        max_zoom=17,
    ).add_to(m)

    add_heatmap_legend(m)


# --- Death Markers ---
fg_deaths = folium.FeatureGroup("Deaths")

for _, row in deaths.iterrows():
    lat = row.geometry.y
    lon = row.geometry.x
    d = row[death_col]

    popup_html = f"""
    <b>Death Record</b><br>
    Deaths: {d}<br>
    Nearest Pump: {row['nearest_pump_id']}<br>
    Distance: {row['distance_to_pump_m']:.1f} m<br>
    """

    folium.CircleMarker(
        [lat, lon],
        radius=4 + d * 0.3,
        color="red",
        fill=True,
        fill_opacity=0.85,
        popup=popup_html
    ).add_to(fg_deaths)

fg_deaths.add_to(m)


# --- Pump Markers ---
fg_pumps = folium.FeatureGroup("Pumps")

for _, row in pumps.iterrows():
    lat = row.geometry.y
    lon = row.geometry.x

    popup_html = f"""
    <b>Water Pump</b><br>
    ID: {row.get("ID", "N/A")}<br>
    """

    folium.Marker(
        [lat, lon],
        icon=folium.Icon(color="blue", icon="tint"),
        popup=popup_html
    ).add_to(fg_pumps)

fg_pumps.add_to(m)


# --- Spider Lines ---
if show_spider:
    fg_spider = folium.FeatureGroup("Spider Lines")

    pump_lookup = {
        str(row.get("ID", "")): (row.geometry.y, row.geometry.x)
        for _, row in pumps.iterrows()
    }

    for _, row in deaths.iterrows():
        nearest_id = str(row.get("nearest_pump_id", ""))

        if nearest_id in pump_lookup:
            pump_lat, pump_lon = pump_lookup[nearest_id]
            death_lat = row.geometry.y
            death_lon = row.geometry.x

            folium.PolyLine(
                locations=[(death_lat, death_lon), (pump_lat, pump_lon)],
                color="black",
                weight=1.5,
                opacity=0.8
            ).add_to(fg_spider)

    fg_spider.add_to(m)


# Render
folium.LayerControl().add_to(m)
st_folium(m, width=1000, height=600)


# ============================================================
# TABLES
# ============================================================
st.markdown("---")
st.subheader("Deaths Table (Nearest Pump + Distance)")
st.dataframe(deaths.drop(columns="geometry"))

st.subheader("Pump Locations Table")
st.dataframe(pumps.drop(columns="geometry"))
