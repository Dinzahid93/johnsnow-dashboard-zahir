import streamlit as st
import pandas as pd
import numpy as np
from pyproj import Transformer
import folium
from folium.plugins import HeatMap, HeatMapWithTime
from streamlit_folium import st_folium

st.set_page_config(layout="wide")
st.title("John Snow Cholera Dashboard – Clean Folium Version")

# ---------------------------
# Upload CSV files
# ---------------------------
st.sidebar.header("Upload Data")
deaths_file = st.sidebar.file_uploader("Upload deaths.csv", type=["csv"])
pumps_file = st.sidebar.file_uploader("Upload pumps.csv", type=["csv"])

if not deaths_file or not pumps_file:
    st.warning("Please upload BOTH files to continue.")
    st.stop()

deaths = pd.read_csv(deaths_file)
pumps  = pd.read_csv(pumps_file)

# ---------------------------
# Convert XY → lat/lon
# ---------------------------
transformer = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)

deaths["lon"], deaths["lat"] = transformer.transform(
    deaths["COORD_X"].values, deaths["COORD_Y"].values
)
pumps["lon"], pumps["lat"] = transformer.transform(
    pumps["COORD_X"].values, pumps["COORD_Y"].values
)

center_lat = deaths.lat.mean()
center_lon = deaths.lon.mean()

# ---------------------------
# Create Folium Map
# ---------------------------
m = folium.Map(location=[center_lat, center_lon], zoom_start=16, tiles="CartoDB positron")

# ============================
# Layer 1 – Death Points
# ============================
death_layer = folium.FeatureGroup(name="Deaths (red circles)")

for _, row in deaths.iterrows():
    folium.CircleMarker(
        location=[row["lat"], row["lon"]],
        radius=row["deaths"] * 2,
        fill=True,
        color="red",
        fill_opacity=0.6,
        popup=f"ID: {row['ID']}<br>Deaths: {row['deaths']}<br>Pump ID: {row['pumpID']}"
    ).add_to(death_layer)

death_layer.add_to(m)

# ============================
# Layer 2 – Pumps
# ============================
pump_layer = folium.FeatureGroup(name="Pumps (blue circles)")

for _, row in pumps.iterrows():
    folium.CircleMarker(
        location=[row["lat"], row["lon"]],
        radius=12,
        fill=True,
        color="blue",
        fill_opacity=0.7,
        popup=f"Pump ID: {row['ID']}<br>Name: {row['name']}"
    ).add_to(pump_layer)

pump_layer.add_to(m)

# ============================
# Layer 3 – Heatmap
# ============================
heat_toggle = st.sidebar.checkbox("Show Heatmap", value=True)

if heat_toggle:
    heat_layer = folium.FeatureGroup(name="Cholera Heatmap")

    heat_data = deaths[["lat", "lon", "deaths"]].values.tolist()

    HeatMap(
        heat_data,
        radius=18,
        blur=15,
        max_zoom=18,
    ).add_to(heat_layer)

    heat_layer.add_to(m)

# ============================
# Layer 4 – KDE (NumPy Density)
# ============================
kde_toggle = st.sidebar.checkbox("Show KDE Smooth Surface", value=False)

if kde_toggle:
    kde_layer = folium.FeatureGroup(name="KDE Surface")

    # build grid for KDE
    lat_min, lat_max = deaths.lat.min(), deaths.lat.max()
    lon_min, lon_max = deaths.lon.min(), deaths.lon.max()

    lat_grid = np.linspace(lat_min, lat_max, 60)
    lon_grid = np.linspace(lon_min, lon_max, 60)

    pts = deaths[["lat", "lon"]].values
    kde_points = []

    for la in lat_grid:
        for lo in lon_grid:
            dist2 = np.min((pts[:,0] - la)**2 + (pts[:,1] - lo)**2)
            density = np.exp(-dist2 * 50000)
            kde_points.append([la, lo, float(density)])

    HeatMap(kde_points, radius=20, blur=35, max_zoom=18).add_to(kde_layer)
    kde_layer.add_to(m)

# ============================
# Layer Control
# ============================
folium.LayerControl().add_to(m)

# ============================
# Show Map
# ============================
st_data = st_folium(m, width=900)

# ============================
# Stats
# ============================
st.subheader("Summary Statistics")
col1, col2, col3 = st.columns(3)
col1.metric("Total Deaths", deaths["deaths"].sum())
col2.metric("Max Deaths in a House", deaths["deaths"].max())
col3.metric("Total Pumps", len(pumps))
