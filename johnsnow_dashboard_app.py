import os
import pathlib
import geopandas as gpd
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

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
    pumps   = gpd.read_file(pumps_path)

    # Identify deaths column
    if "deaths" in deaths.columns:
        death_col = "deaths"
    elif "Count" in deaths.columns:
        death_col = "Count"
    else:
        st.error("No deaths column found.")
        return None

    deaths[death_col] = pd.to_numeric(
        deaths[death_col], errors="coerce"
    ).fillna(0).astype(int)

    # Convert CRS → WGS84
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
# STREAMLIT PAGE
# ============================================================
st.set_page_config(page_title="John Snow Dashboard", layout="wide")
st.title("John Snow Cholera Map")

# ============================================================
# SUMMARY METRICS
# ============================================================
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Deaths", int(deaths[death_col].sum()))
c2.metric("Buildings", len(deaths))
c3.metric("Max Deaths", int(deaths[death_col].max()))
c4.metric("Avg Deaths", f"{deaths[death_col].mean():.1f}")

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
    tiles="CartoDB Positron"
)

# ============================================================
# DEATH MARKERS (ID + PumpID)
# ============================================================
fg_deaths = folium.FeatureGroup("Deaths")

for _, row in deaths.iterrows():
    lat = row.geometry.y
    lon = row.geometry.x

    # Extract fields safely
    death_id  = row.get("ID", "N/A")
    pump_id   = row.get("PumpID", row.get("pumpID", "N/A"))
    deaths_n  = row[death_col]

    popup_html = f"""
    <b>Death Record</b><br>
    ID: {death_id}<br>
    PumpID: {pump_id}<br>
    Deaths: {deaths_n}<br>
    """

    folium.CircleMarker(
        [lat, lon],
        radius=4 + deaths_n * 0.3,
        color="red",
        fill=True,
        fill_opacity=0.85,
        popup=popup_html
    ).add_to(fg_deaths)

fg_deaths.add_to(m)

# ============================================================
# PUMP MARKERS (ID + Name)
# ============================================================
fg_pumps = folium.FeatureGroup("Pumps")

for _, row in pumps.iterrows():
    lat = row.geometry.y
    lon = row.geometry.x

    pump_id = row.get("ID", "N/A")
    pump_name = row.get("name", row.get("Name", row.get("PUMP", "Unknown")))

    popup_html = f"""
    <b>Water Pump</b><br>
    ID: {pump_id}<br>
    Name: {pump_name}<br>
    """

    folium.Marker(
        [lat, lon],
        icon=folium.Icon(color="blue", icon="tint"),
        popup=popup_html
    ).add_to(fg_pumps)

fg_pumps.add_to(m)

# Add layer control
folium.LayerControl().add_to(m)

# Show map
st_folium(m, width=1000, height=600)

# ============================================================
# ATTRIBUTE TABLES
# ============================================================
st.markdown("---")
st.subheader("Deaths Table")
st.dataframe(deaths.drop(columns="geometry"))

st.subheader("Pumps Table")
st.dataframe(pumps.drop(columns="geometry"))
