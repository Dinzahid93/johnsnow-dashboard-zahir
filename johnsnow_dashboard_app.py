import os
import pathlib
import geopandas as gpd
import pandas as pd
import streamlit as st
import folium
from shapely.ops import nearest_points
from streamlit_folium import st_folium
from folium.plugins import HeatMap
import pydeck as pdk


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
# STREAMLIT CONFIG
# ============================================================
st.set_page_config(page_title="John Snow’s 1854 Cholera Map", layout="wide")
st.title("John Snow’s 1854 Cholera Map")


# ============================================================
# TITLE + IMAGE
# ============================================================
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
    st.image("data/John_Snow.jpg", width=300, caption="Dr. John Snow (1813–1858)")

st.markdown("---")


# ============================================================
# TABS
# ============================================================
tab1, tab2, tab3 = st.tabs([
    "🔥 Heatmap of Deaths",
    "🕸 Spider Web Analysis",
    "🏢 3D Extruded Deaths"
])


# ============================================================
# TAB 1 — HEATMAP
# ============================================================
with tab1:
    st.subheader("Heatmap of Cholera Deaths")
    st.markdown("""
    This heatmap visualizes the **intensity of cholera fatalities** across the Soho district.  
    Warmer colors (yellow–red) highlight concentrated clusters of deaths,  
    revealing key outbreak hotspots that shaped John Snow’s landmark findings.
    """)

    center_lat = deaths.geometry.y.mean()
    center_lon = deaths.geometry.x.mean()

    m1 = folium.Map(location=[center_lat, center_lon], zoom_start=17, tiles="OpenStreetMap")

    fg_heatmap = folium.FeatureGroup("Heatmap")
    fg_deaths = folium.FeatureGroup("Death Locations")
    fg_pumps = folium.FeatureGroup("Water Pumps")

    heat_data = [[row.geometry.y, row.geometry.x, row[death_col]] for _, row in deaths.iterrows()]
    HeatMap(heat_data, radius=25, blur=15).add_to(fg_heatmap)

    for _, row in deaths.iterrows():
        popup = f"""
        <b>Deaths at location:</b> {row[death_col]}<br>
        <b>Nearest Pump:</b> {row['nearest_pump_id']}<br>
        <b>Distance:</b> {row['distance_to_pump_m']:.1f} m
        """
        folium.CircleMarker([row.geometry.y, row.geometry.x],
                            radius=4 + row[death_col] * 0.3,
                            color="red", fill=True, popup=popup).add_to(fg_deaths)

    for _, row in pumps.iterrows():
        name = row.get("name", row.get("Name", f"Pump {row.get('ID', 'N/A')}"))
        popup = f"<b>{name}</b><br>ID: {row.get('ID', 'N/A')}"
        folium.Marker([row.geometry.y, row.geometry.x],
                      icon=folium.Icon(color='blue', icon='tint'),
                      popup=popup).add_to(fg_pumps)

    fg_heatmap.add_to(m1)
    fg_deaths.add_to(m1)
    fg_pumps.add_to(m1)

    folium.LayerControl().add_to(m1)
    add_heatmap_legend(m1)

    st_folium(m1, width=1000, height=600)


# ============================================================
# TAB 2 — SPIDER WEB
# ============================================================
with tab2:
    st.subheader("Spider Web Analysis (Death → Nearest Pump)")
    st.markdown("""
    This analysis illustrates the **closest water pump for every recorded cholera death**.  
    The connecting lines form a “spider web” pattern, revealing how  
    contaminated water sources shaped the outbreak’s progression.
    """)

    m2 = folium.Map(location=[center_lat, center_lon], zoom_start=17, tiles="OpenStreetMap")

    fg_spider = folium.FeatureGroup("Spider Lines")
    fg_deaths = folium.FeatureGroup("Death Locations")
    fg_pumps = folium.FeatureGroup("Water Pumps")

    pump_lookup = {str(row.get("ID", "")): (row.geometry.y, row.geometry.x)
                    for _, row in pumps.iterrows()}

    for _, row in pumps.iterrows():
        name = row.get("name", row.get("Name", f"Pump {row.get('ID', 'N/A')}"))
        popup = f"<b>{name}</b><br>ID: {row.get('ID', 'N/A')}"
        folium.Marker([row.geometry.y, row.geometry.x],
                      icon=folium.Icon(color='blue', icon='tint'),
                      popup=popup).add_to(fg_pumps)

    for _, row in deaths.iterrows():
        d_lat = row.geometry.y
        d_lon = row.geometry.x
        nearest_id = str(row["nearest_pump_id"])

        popup = f"""
        <b>Deaths at location:</b> {row[death_col]}<br>
        <b>Nearest Pump:</b> {nearest_id}<br>
        <b>Distance:</b> {row['distance_to_pump_m']:.1f} m
        """
        folium.CircleMarker([d_lat, d_lon], radius=4, color="red", fill=True,
                            popup=popup).add_to(fg_deaths)

        if nearest_id in pump_lookup:
            p_lat, p_lon = pump_lookup[nearest_id]
            folium.PolyLine([(d_lat, d_lon), (p_lat, p_lon)],
                            color="black", weight=1.5).add_to(fg_spider)

    fg_deaths.add_to(m2)
    fg_spider.add_to(m2)
    fg_pumps.add_to(m2)

    folium.LayerControl().add_to(m2)
    st_folium(m2, width=1000, height=600)


# ============================================================
# TAB 3 — 3D EXTRUDED DEATHS + PUMP MARKERS
# ============================================================
with tab3:
    st.subheader("3D Extruded Visualization of Cholera Deaths")
    st.markdown("""
    This 3D visualization displays **vertically extruded bars** whose heights  
    correspond to the number of cholera deaths at each building.  
    Blue markers represent **water pumps**, enabling quick comparison between  
    pump locations and mortality intensity.
    """)

    # Prepare death data
    deaths_3d = deaths.copy()
    deaths_3d["lat"] = deaths_3d.geometry.y
    deaths_3d["lon"] = deaths_3d.geometry.x
    deaths_3d["height"] = deaths_3d[death_col] * 8

    # Prepare pump data
    pumps_3d = pumps.copy()
    pumps_3d["lat"] = pumps_3d.geometry.y
    pumps_3d["lon"] = pumps_3d.geometry.x
    pumps_3d["pump_name"] = pumps_3d.apply(
        lambda r: r.get("name", r.get("Name", f"Pump {r.get('ID', 'N/A')}")), axis=1
    )
    pumps_3d["pump_id"] = pumps_3d.get("ID", None)

    # Death bars layer
    column_layer = pdk.Layer(
        "ColumnLayer",
        data=deaths_3d,
        get_position=["lon", "lat"],
        get_elevation="height",
        elevation_scale=5,
        radius=3,
        get_fill_color=[255, 0, 0],
        pickable=True,
        auto_highlight=True,
    )

    # Pump scatter layer
    pump_layer = pdk.Layer(
        "ScatterplotLayer",
        data=pumps_3d,
        get_position=["lon", "lat"],
        get_color=[0, 120, 255],
        get_radius=12,
        pickable=True,
    )

    # Tooltip logic
    tooltip = {
        "html": """
        {% if deaths is defined %}
            <b>Deaths:</b> {{deaths}}<br>
            <b>Nearest Pump:</b> {{nearest_pump_id}}<br>
            <b>Distance:</b> {{distance_to_pump_m}} m
        {% else %}
            <b>Water Pump</b><br>
            <b>Name:</b> {{pump_name}}<br>
            <b>ID:</b> {{pump_id}}
        {% endif %}
        """,
        "style": {"backgroundColor": "black", "color": "white"},
    }

    # Camera view
    view_state = pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=16.5,
        pitch=55,
        bearing=20,
    )

    deck = pdk.Deck(
        layers=[column_layer, pump_layer],
        initial_view_state=view_state,
        map_style="light",
        tooltip=tooltip,
    )

    st.pydeck_chart(deck)
