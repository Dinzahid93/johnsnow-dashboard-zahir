import streamlit as st
import pandas as pd
import numpy as np
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium

# ------------------------------------------------------------
# PAGE SETTINGS
# ------------------------------------------------------------
st.set_page_config(page_title="Cholera Heatmap & KDE Dashboard", layout="wide")
st.title("🗺️ John Snow — Cholera Heatmap + KDE Density Dashboard")

st.markdown("""
Upload your **deaths** and **pumps** CSV files to visualize:
- Heatmap (weighted)
- KDE smooth density surface
- Death points
- Pump locations

All layers are toggle-able.
""")

# ------------------------------------------------------------
# FILE UPLOADS
# ------------------------------------------------------------
death_file = st.sidebar.file_uploader("Upload Deaths CSV", type=["csv"])
pump_file = st.sidebar.file_uploader("Upload Pumps CSV", type=["csv"])

if death_file is None or pump_file is None:
    st.warning("📌 Please upload **both files** to continue.")
    st.stop()

# ------------------------------------------------------------
# LOAD CSV DATA
# ------------------------------------------------------------
deaths = pd.read_csv(death_file)
pumps = pd.read_csv(pump_file)

# Ensure column names
for df in [deaths, pumps]:
    df.rename(columns={"X": "lon", "Y": "lat"}, inplace=True, errors="ignore")

# ------------------------------------------------------------
# KDE SIDEBAR SETTINGS
# ------------------------------------------------------------
st.sidebar.header("KDE Settings")

show_heatmap = st.sidebar.checkbox("Show Heatmap", value=True)
show_kde = st.sidebar.checkbox("Show KDE Surface", value=False)
show_deaths = st.sidebar.checkbox("Show Death Points", value=True)
show_pumps = st.sidebar.checkbox("Show Pumps", value=True)

bandwidth = st.sidebar.slider("KDE Bandwidth", 5, 80, 25)
grid_res = st.sidebar.slider("KDE Grid Resolution", 50, 200, 120)

# ------------------------------------------------------------
# BASE MAP
# ------------------------------------------------------------
center_lat = deaths["lat"].mean()
center_lon = deaths["lon"].mean()

m = folium.Map(location=[center_lat, center_lon], zoom_start=17, tiles="cartodbpositron")

heat_layer = folium.FeatureGroup(name="Heatmap", show=show_heatmap)
kde_layer = folium.FeatureGroup(name="KDE Surface", show=show_kde)
death_layer = folium.FeatureGroup(name="Deaths", show=show_deaths)
pump_layer = folium.FeatureGroup(name="Pumps", show=show_pumps)

# ------------------------------------------------------------
# HEATMAP LAYER
# ------------------------------------------------------------
if show_heatmap:
    heat_data = deaths[["lat", "lon", "deaths"]].values.tolist()

    HeatMap(
        heat_data,
        radius=35,
        blur=25,
        max_zoom=18,
        gradient={
            0.2: "blue",
            0.4: "cyan",
            0.6: "lime",
            0.8: "yellow",
            1.0: "red"
        }
    ).add_to(heat_layer)

# ------------------------------------------------------------
# KDE LAYER (Pure NumPy)
# ------------------------------------------------------------
if show_kde:
    lat = deaths["lat"].values
    lon = deaths["lon"].values
    weights = deaths["deaths"].values

    # grid
    lat_lin = np.linspace(lat.min(), lat.max(), grid_res)
    lon_lin = np.linspace(lon.min(), lon.max(), grid_res)
    xx, yy = np.meshgrid(lon_lin, lat_lin)

    kde_grid = np.zeros_like(xx)

    # compute KDE
    for x, y, w in zip(lon, lat, weights):
        kde_grid += w * np.exp(
            -((xx - x) ** 2 + (yy - y) ** 2) / (2 * (bandwidth / 10000) ** 2)
        )

    kde_grid = kde_grid / kde_grid.max()

    # add as overlay
    folium.raster_layers.ImageOverlay(
        kde_grid,
        bounds=[[lat.min(), lon.min()], [lat.max(), lon.max()]],
        colormap=lambda v: (int(v * 255), int((1 - v) * 255), 0, int(v * 0.7 * 255)),
        opacity=0.6,
    ).add_to(kde_layer)

# ------------------------------------------------------------
# DEATH POINTS
# ------------------------------------------------------------
if show_deaths:
    for _, row in deaths.iterrows():
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=4 + row["deaths"] * 0.7,
            color="red", fill=True, fill_color="red",
            fill_opacity=0.7,
            popup=f"ID: {row['id']}<br>Deaths: {row['deaths']}<br>PumpID: {row['pumpID']}"
        ).add_to(death_layer)

# ------------------------------------------------------------
# PUMPS
# ------------------------------------------------------------
if show_pumps:
    for _, row in pumps.iterrows():
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=10,
            color="blue", fill=True, fill_color="blue", fill_opacity=0.8,
            popup=f"Pump ID: {row['id']}<br>Name: {row['name']}"
        ).add_to(pump_layer)

# ------------------------------------------------------------
# ADD LAYERS
# ------------------------------------------------------------
heat_layer.add_to(m)
kde_layer.add_to(m)
death_layer.add_to(m)
pump_layer.add_to(m)

folium.LayerControl(collapsed=False).add_to(m)

# ------------------------------------------------------------
# DISPLAY MAP
# ------------------------------------------------------------
st_folium(m, width=1000, height=600)
