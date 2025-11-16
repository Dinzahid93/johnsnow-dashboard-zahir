import streamlit as st
import pydeck as pdk
import numpy as np
import pandas as pd
from sklearn.neighbors import KernelDensity

st.set_page_config(layout="wide")

st.title("John Snow Cholera Dashboard – With KDE Surface")

# =======================================================
# LOAD DATA (replace with your paths)
# =======================================================
deaths = pd.read_csv("deaths.csv")   # must contain: lat, lon, deaths
pumps  = pd.read_csv("pumps.csv")    # must contain: lat, lon, name/id

# If your data uses geometry fields, convert:
# deaths["lat"] = deaths.geometry.y
# deaths["lon"] = deaths.geometry.x

# =======================================================
# KDE COMPUTATION
# =======================================================
kde_toggle = st.sidebar.checkbox("Show KDE Risk Surface", value=False)

# KDE grid resolution (higher = smoother but slower)
GRID_SIZE = 200

if kde_toggle:

    # Build grid bounds
    min_lat, max_lat = deaths.lat.min(), deaths.lat.max()
    min_lon, max_lon = deaths.lon.min(), deaths.lon.max()

    lat_space = np.linspace(min_lat, max_lat, GRID_SIZE)
    lon_space = np.linspace(min_lon, max_lon, GRID_SIZE)
    lon_grid, lat_grid = np.meshgrid(lon_space, lat_space)

    grid_points = np.vstack([lat_grid.ravel(), lon_grid.ravel()]).T

    # KDE model
    kde_model = KernelDensity(
        bandwidth=0.0008,       # adjust for smoothness
        kernel="gaussian"
    )

    kde_model.fit(deaths[["lat", "lon"]])

    z = np.exp(kde_model.score_samples(grid_points))
    z_norm = (z - z.min()) / (z.max() - z.min())

    kde_df = pd.DataFrame({
        "lat": grid_points[:, 0],
        "lon": grid_points[:, 1],
        "density": z_norm
    })

else:
    kde_df = pd.DataFrame(columns=["lat", "lon", "density"])

# =======================================================
# MAP VIEW
# =======================================================
VIEW = pdk.ViewState(
    latitude=deaths.lat.mean(),
    longitude=deaths.lon.mean(),
    zoom=16,
    pitch=45,
    bearing=0
)

# =======================================================
# LAYERS
# =======================================================

layers = []

# ----------------------------------
# Death markers
# ----------------------------------
death_layer = pdk.Layer(
    "ScatterplotLayer",
    data=deaths,
    get_position='[lon, lat]',
    get_radius='deaths * 4',
    get_fill_color='[255, 0, 0, 180]',
    pickable=True,
    auto_highlight=True
)
layers.append(death_layer)

# ----------------------------------
# Pump markers
# ----------------------------------
pump_layer = pdk.Layer(
    "ScatterplotLayer",
    data=pumps,
    get_position='[lon, lat]',
    get_radius=25,
    get_fill_color='[0, 0, 255, 180]',
    pickable=True
)
layers.append(pump_layer)

# ----------------------------------
# KDE Surface (optional)
# ----------------------------------
if kde_toggle and len(kde_df) > 0:
    kde_layer = pdk.Layer(
        "ColumnLayer",
        data=kde_df,
        get_position='[lon, lat]',
        get_elevation='density * 200',   # height of columns
        elevation_scale=50,
        radius=3,
        get_fill_color='[255 * density, 150 * density, 0, 180]',
        pickable=False,
        auto_highlight=False
    )
    layers.append(kde_layer)

# =======================================================
# RENDER MAP
# =======================================================

r = pdk.Deck(
    layers=layers,
    initial_view_state=VIEW,
    map_style="mapbox://styles/mapbox/light-v10",
    tooltip={"text": "Lat: {lat}\nLon: {lon}"}
)

st.pydeck_chart(r)

# =======================================================
# LEGEND (only when KDE is ON)
# =======================================================
if kde_toggle:
    st.markdown("""
    ### KDE Legend
    - **Red/Orange** = High disease intensity  
    - **Yellow** = Medium risk  
    - **Light Yellow** = Low risk  
    """)

# =======================================================
# DATA TABLES
# =======================================================
st.subheader("Death Records")
st.dataframe(deaths)

st.subheader("Pumps")
st.dataframe(pumps)
