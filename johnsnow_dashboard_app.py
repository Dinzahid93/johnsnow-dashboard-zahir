import streamlit as st
import pandas as pd
import numpy as np
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium

st.set_page_config(page_title="Cholera Heatmap + KDE", layout="wide")
st.title("🗺 John Snow Cholera Dashboard")

# ----------------------------------------------------------
# Load your data automatically (NO upload required)
# ----------------------------------------------------------
deaths = pd.read_csv("data/deaths_by_bldg.csv")
pumps = pd.read_csv("data/pumps.csv")

# Rename X/Y → lon/lat for folium
deaths = deaths.rename(columns={"X": "lon", "Y": "lat"})
pumps = pumps.rename(columns={"X": "lon", "Y": "lat"})

# ----------------------------------------------------------
# SIDEBAR CONTROLS
# ----------------------------------------------------------
show_deaths = st.sidebar.checkbox("Show Death Points", True)
show_pumps = st.sidebar.checkbox("Show Pumps", True)
show_heatmap = st.sidebar.checkbox("Show Death Heatmap", True)

show_kde = st.sidebar.checkbox("Enable KDE (Advanced)", False)

if show_kde:
    bandwidth = st.sidebar.slider("KDE Bandwidth", 5, 80, 25)
    grid_res = st.sidebar.slider("KDE Grid Resolution", 50, 200, 120)

# ----------------------------------------------------------
# Base Map
# ----------------------------------------------------------
center_lat = deaths["lat"].mean()
center_lon = deaths["lon"].mean()

m = folium.Map(location=[center_lat, center_lon], zoom_start=17, tiles="cartodbpositron")

layer_heat = folium.FeatureGroup("Heatmap", show=show_heatmap)
layer_kde = folium.FeatureGroup("KDE Surface", show=show_kde)
layer_deaths = folium.FeatureGroup("Deaths", show=show_deaths)
layer_pumps = folium.FeatureGroup("Pumps", show=show_pumps)

# ----------------------------------------------------------
# 1️⃣ HEATMAP (simple)
# ----------------------------------------------------------
if show_heatmap:
    heat_data = deaths[["lat", "lon", "deaths"]].values.tolist()
    HeatMap(
        heat_data,
        radius=35,
        blur=25,
        max_zoom=18,
        gradient={0.2: "blue", 0.4: "cyan", 0.6: "lime", 0.8: "yellow", 1.0: "red"}
    ).add_to(layer_heat)

# ----------------------------------------------------------
# 2️⃣ KDE (advanced, optional)
# ----------------------------------------------------------
if show_kde:

    lat = deaths["lat"].values
    lon = deaths["lon"].values
    weights = deaths["deaths"].values

    # Create grid
    lat_lin = np.linspace(lat.min(), lat.max(), grid_res)
    lon_lin = np.linspace(lon.min(), lon.max(), grid_res)
    xx, yy = np.meshgrid(lon_lin, lat_lin)
    kde = np.zeros_like(xx)

    # Compute KDE
    for x, y, w in zip(lon, lat, weights):
        kde += w * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * (bandwidth/10000) ** 2))

    kde = kde / kde.max()

    folium.raster_layers.ImageOverlay(
        image=kde,
        bounds=[[lat.min(), lon.min()], [lat.max(), lon.max()]],
        opacity=0.6,
        colormap=lambda v: (int(v*255), int((1-v)*255), 0, int(v*255)),
    ).add_to(layer_kde)

# ----------------------------------------------------------
# 3️⃣ Death Points
# ----------------------------------------------------------
if show_deaths:
    for _, row in deaths.iterrows():
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=3 + row["deaths"] * 0.7,
            color="red", fill=True, fill_color="red", fill_opacity=0.8,
            popup=f"ID: {row['id']}<br>Deaths: {row['deaths']}<br>Pump: {row['pumpID']}"
        ).add_to(layer_deaths)

# ----------------------------------------------------------
# 4️⃣ Pumps
# ----------------------------------------------------------
if show_pumps:
    for _, row in pumps.iterrows():
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=10,
            color="blue", fill=True, fill_color="blue",
            popup=f"Pump ID: {row['id']}<br>Name: {row['name']}"
        ).add_to(layer_pumps)

# ----------------------------------------------------------
# Add layers
# ----------------------------------------------------------
layer_heat.add_to(m)
layer_kde.add_to(m)
layer_deaths.add_to(m)
layer_pumps.add_to(m)
folium.LayerControl(collapsed=False).add_to(m)

# ----------------------------------------------------------
# Show map
# ----------------------------------------------------------
st_folium(m, width=1000, height=600)
