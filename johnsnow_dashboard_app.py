# ============================================================
# johnsnow_dashboard_app.py
#
# Simple interactive dashboard for John Snow cholera data
# - Uses deaths_by_bldg.shp and pumps.shp from ./data folder
# - Summary stats
# - Range / exact filter by number of deaths
# - Interactive Folium map (deaths + pumps)
# - Attribute table of filtered buildings
#
# This version is GitHub + Streamlit Cloud friendly.
# ============================================================

import os
import numpy as np
import pandas as pd
import geopandas as gpd
import folium
import streamlit as st
from streamlit_folium import st_folium

# -----------------------------
# PATHS – RELATIVE (NO C:\...)
# -----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

deaths_path = os.path.join(DATA_DIR, "deaths_by_bldg.shp")
pumps_path  = os.path.join(DATA_DIR, "pumps.shp")

# -----------------------------
# LOAD DATA (CACHED)
# -----------------------------
@st.cache_data
def load_data():
    deaths = gpd.read_file(deaths_path)
    pumps  = gpd.read_file(pumps_path)

    # Decide which column is death count
    if "deaths" in deaths.columns:
        death_col = "deaths"
    elif "Count" in deaths.columns:
        death_col = "Count"
    else:
        raise ValueError("No 'deaths' or 'Count' column in deaths_by_bldg.shp")

    # Ensure death column is integer
    deaths[death_col] = pd.to_numeric(deaths[death_col], errors="coerce").fillna(0).astype(int)

    # Geo for web (lat/lon)
    deaths_wgs = deaths.to_crs(epsg=4326)
    pumps_wgs  = pumps.to_crs(epsg=4326)

    return deaths, pumps, deaths_wgs, pumps_wgs, death_col

deaths, pumps, deaths_wgs, pumps_wgs, death_col = load_data()

# ============================================================
# STREAMLIT LAYOUT
# ============================================================

st.set_page_config(
    page_title="John Snow Cholera Dashboard",
    layout="wide"
)

st.title("John Snow 1854 Cholera – Interactive Dashboard")

st.markdown(
    """
This dashboard uses **deaths_by_bldg** (deaths aggregated to buildings)  
and **pumps** from the John Snow cholera study area.

You can filter buildings by number of deaths and explore the map and attribute table.
"""
)

# -----------------------------
# SUMMARY METRICS
# -----------------------------
total_deaths    = int(deaths[death_col].sum())
num_buildings   = int(len(deaths))
max_deaths_bldg = int(deaths[death_col].max())
avg_deaths_bldg = float(deaths[death_col].mean())

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total deaths (all buildings)", f"{total_deaths}")
c2.metric("Number of buildings", f"{num_buildings}")
c3.metric("Max deaths in a building", f"{max_deaths_bldg}")
c4.metric("Avg deaths per building", f"{avg_deaths_bldg:.2f}")

st.markdown("---")

# -----------------------------
# SIDEBAR FILTER
# -----------------------------
st.sidebar.header("Filters")

min_d = int(deaths[death_col].min())
max_d = int(deaths[death_col].max())

filter_mode = st.sidebar.radio(
    "Filter mode",
    options=["Range", "Exact value"],
    index=0
)

if filter_mode == "Range":
    death_range = st.sidebar.slider(
        "Select deaths range",
        min_value=min_d,
        max_value=max_d,
        value=(min_d, max_d),
        step=1
    )

    st.sidebar.write(
        f"Showing buildings with **{death_col} between {death_range[0]} and {death_range[1]}**."
    )

    # Apply range filter
    filtered = deaths_wgs[
        (deaths_wgs[death_col] >= death_range[0]) &
        (deaths_wgs[death_col] <= death_range[1])
    ]

else:  # Exact value
    death_value = st.sidebar.slider(
        "Show only buildings with deaths =",
        min_value=min_d,
        max_value=max_d,
        value=min_d,
        step=1
    )

    st.sidebar.write(
        f"Showing buildings with **{death_col} = {death_value}** only."
    )

    filtered = deaths_wgs[deaths_wgs[death_col] == death_value]

# -----------------------------
# MAP SECTION
# -----------------------------
st.subheader("Interactive Map (Folium)")

if not filtered.empty:
    center_lat = filtered.geometry.y.mean()
    center_lon = filtered.geometry.x.mean()
else:
    center_lat = deaths_wgs.geometry.y.mean()
    center_lon = deaths_wgs.geometry.x.mean()

m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=17,
    tiles="CartoDB Positron"
)

# --- Deaths layer (filtered) ---
death_layer = folium.FeatureGroup(name="Deaths by Building (filtered)")

for _, row in filtered.iterrows():
    lat, lon = row.geometry.y, row.geometry.x
    d = int(row[death_col])

    popup_html = "<b>DEATH LOCATION</b><br><br>"
    for col in deaths.columns:
        if col != "geometry":
            try:
                val = row[col]
            except KeyError:
                val = ""
            popup_html += f"{col}: {val}<br>"

    size = 3 + 0.4 * d

    folium.CircleMarker(
        location=[lat, lon],
        radius=size,
        color="red",
        fill=True,
        fill_color="red",
        fill_opacity=0.7,
        popup=folium.Popup(popup_html, max_width=300),
    ).add_to(death_layer)

death_layer.add_to(m)

# --- Pumps layer ---
pumps_layer = folium.FeatureGroup(name="Water Pumps")

for _, row in pumps_wgs.iterrows():
    lat, lon = row.geometry.y, row.geometry.x

    popup_html = "<b>WATER PUMP</b><br><br>"
    for col in pumps.columns:
        if col != "geometry":
            popup_html += f"{col}: {row[col]}<br>"

    folium.Marker(
        location=[lat, lon],
        icon=folium.Icon(color="blue", icon="tint", prefix="fa"),
        popup=folium.Popup(popup_html, max_width=300)
    ).add_to(pumps_layer)

pumps_layer.add_to(m)

folium.LayerControl().add_to(m)

# Render Folium map inside Streamlit
st_folium(m, width=900, height=600)

# -----------------------------
# TABLE SECTION
# -----------------------------
st.subheader("Filtered Buildings – Attribute Table")

if not filtered.empty:
    table_df = pd.DataFrame(filtered.drop(columns="geometry"))
else:
    table_df = pd.DataFrame(columns=[c for c in deaths.columns if c != "geometry"])

st.dataframe(table_df)

if filter_mode == "Range":
    st.markdown(
        f"Showing **{len(filtered)}** buildings with {death_col} between "
        f"**{death_range[0]}** and **{death_range[1]}**."
    )
else:
    st.markdown(
        f"Showing **{len(filtered)}** buildings with {death_col} = **{death_value}**."
    )
