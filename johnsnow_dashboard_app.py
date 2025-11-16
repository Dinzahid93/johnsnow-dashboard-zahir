import os
import numpy as np
import pandas as pd
import geopandas as gpd
import streamlit as st
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium

# ----------------------------------------------------------
# CONFIG
# ----------------------------------------------------------
st.set_page_config(page_title="Cholera Dashboard", layout="wide")
st.title("🗺 John Snow Cholera Dashboard")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEATHS_GJ = os.path.join(BASE_DIR, "data", "deaths_by_bldg.geojson")
PUMPS_GJ  = os.path.join(BASE_DIR, "data", "pumps.geojson")

# ----------------------------------------------------------
# LOAD GEOJSON FOR NORMAL DASHBOARD (NO CSV NEEDED)
# ----------------------------------------------------------
deaths_gdf = gpd.read_file(DEATHS_GJ)
pumps_gdf  = gpd.read_file(PUMPS_GJ)

# Ensure WGS84 for folium
if deaths_gdf.crs is not None:
    deaths_gdf = deaths_gdf.to_crs(epsg=4326)
if pumps_gdf.crs is not None:
    pumps_gdf = pumps_gdf.to_crs(epsg=4326)

# Deaths column detection
death_col = "deaths" if "deaths" in deaths_gdf.columns else \
            "Count"  if "Count" in deaths_gdf.columns else None

if death_col is None:
    st.error("❌ No 'deaths' or 'Count' column found in deaths_by_bldg.geojson")
    st.stop()

# ----------------------------------------------------------
# SIDEBAR
# ----------------------------------------------------------
st.sidebar.header("Display Layers")

show_points   = st.sidebar.checkbox("Show Death Points", True)
show_pumps    = st.sidebar.checkbox("Show Pumps", True)
show_heatmap  = st.sidebar.checkbox("Show Heatmap", True)
show_kde      = st.sidebar.checkbox("Enable KDE (Advanced)", False)

if show_kde:
    st.sidebar.warning("KDE requires CSV files (X/Y coordinates).")
    bandwidth = st.sidebar.slider("KDE Bandwidth", 5, 60, 25)
    grid_res  = st.sidebar.slider("Grid Resolution", 60, 200, 120)

# ----------------------------------------------------------
# MAP INITIALIZATION
# ----------------------------------------------------------
center_lat = deaths_gdf.geometry.y.mean()
center_lon = deaths_gdf.geometry.x.mean()

m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=17,
    tiles="cartodbpositron"
)

layer_heat = folium.FeatureGroup("Heatmap", show=show_heatmap)
layer_points = folium.FeatureGroup("Death Points", show=show_points)
layer_pumps = folium.FeatureGroup("Pumps", show=show_pumps)
layer_kde = folium.FeatureGroup("KDE Surface", show=show_kde)

# ----------------------------------------------------------
# HEATMAP LAYER (ALWAYS WORKS)
# ----------------------------------------------------------
if show_heatmap:
    heat_data = [
        [row.geometry.y, row.geometry.x, row[death_col]]
        for _, row in deaths_gdf.iterrows()
    ]

    HeatMap(
        heat_data,
        radius=30,
        blur=20,
        max_zoom=18,
        gradient={0.1: "blue", 0.4: "lime", 0.7: "yellow", 1.0: "red"}
    ).add_to(layer_heat)

    # heatmap legend
    legend_html = """
    <div style="position: fixed; bottom: 40px; left: 40px; 
                padding: 10px; background: white; border: 2px solid black;">
    <b>Heatmap Intensity</b><br>
    Blue → Low<br>
    Green → Medium<br>
    Yellow → High<br>
    Red → Very High
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

# ----------------------------------------------------------
# DEATH POINTS
# ----------------------------------------------------------
if show_points:
    for _, row in deaths_gdf.iterrows():
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=3 + row[death_col] * 0.5,
            color="red",
            fill=True,
            fill_color="red",
            fill_opacity=0.8,
            popup=f"<b>Deaths:</b> {row[death_col]}"
        ).add_to(layer_points)

# ----------------------------------------------------------
# PUMPS
# ----------------------------------------------------------
if show_pumps:
    for _, row in pumps_gdf.iterrows():
        folium.Marker(
            [row.geometry.y, row.geometry.x],
            icon=folium.Icon(color="blue", icon="tint", prefix="fa"),
            popup=f"<b>Pump:</b> {row['id'] if 'id' in row else ''}"
        ).add_to(layer_pumps)

# ----------------------------------------------------------
# KDE (ADVANCED) – ONLY WHEN ENABLED
# ----------------------------------------------------------
if show_kde:
    deaths_csv_path = os.path.join(BASE_DIR, "data", "deaths_by_bldg.csv")

    if not os.path.exists(deaths_csv_path):
        st.error("❌ KDE requires data/deaths_by_bldg.csv. Add the CSV first.")
    else:
        df = pd.read_csv(deaths_csv_path)

        if not {"X", "Y", death_col}.issubset(df.columns):
            st.error("CSV missing required columns: X, Y, deaths")
        else:
            # Convert to lat/lon for folium
            # Assuming X/Y already approximate lon/lat aligned with your map
            lons = df["X"].values
            lats = df["Y"].values
            weights = df[death_col].values

            lat_lin = np.linspace(lats.min(), lats.max(), grid_res)
            lon_lin = np.linspace(lons.min(), lons.max(), grid_res)
            xx, yy = np.meshgrid(lon_lin, lat_lin)

            kde = np.zeros_like(xx)

            bw_scaled = bandwidth / 10000

            for x, y, w in zip(lons, lats, weights):
                kde += w * np.exp(-((xx - x)**2 + (yy - y)**2) / (2*bw_scaled**2))

            kde = kde / kde.max()

            folium.raster_layers.ImageOverlay(
                image=kde,
                bounds=[[lats.min(), lons.min()], [lats.max(), lons.max()]],
                opacity=0.5,
                colormap=lambda v: (int(255*v), 0, int(255*(1-v)), int(255*v))
            ).add_to(layer_kde)

# ----------------------------------------------------------
# ADD LAYERS
# ----------------------------------------------------------
layer_heat.add_to(m)
layer_points.add_to(m)
layer_pumps.add_to(m)
if show_kde:
    layer_kde.add_to(m)

folium.LayerControl(collapsed=False).add_to(m)

# ----------------------------------------------------------
# RENDER MAP
# ----------------------------------------------------------
st_folium(m, width=1000, height=600)
