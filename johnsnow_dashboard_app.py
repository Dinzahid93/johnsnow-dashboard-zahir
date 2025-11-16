import streamlit as st
import pydeck as pdk
import numpy as np
import pandas as pd

st.set_page_config(layout="wide")

st.title("John Snow Cholera Dashboard – KDE (Pure NumPy Version)")

# =======================================================
# LOAD YOUR DATA
# =======================================================
# Make sure these CSV have columns: lat, lon, deaths
deaths = pd.read_csv("deaths.csv")
pumps  = pd.read_csv("pumps.csv")

# =======================================================
# KDE Toggle
# =======================================================
kde_toggle = st.sidebar.checkbox("Show KDE Risk Surface", value=False)

GRID_SIZE = 200    # Higher = smoother (but slower)
BANDWIDTH = 0.0009 # Change this to adjust smoothness

if kde_toggle:

    # -----------------------------------------------
    # BUILD GRID AROUND DATA
    # -----------------------------------------------
    min_lat, max_lat = deaths.lat.min(), deaths.lat.max()
    min_lon, max_lon = deaths.lon.min(), deaths.lon.max()

    lat_space = np.linspace(min_lat, max_lat, GRID_SIZE)
    lon_space = np.linspace(min_lon, max_lon, GRID_SIZE)

    lon_grid, lat_grid = np.meshgrid(lon_space, lat_space)

    # Flatten grid
    grid_flat = np.vstack([lat_grid.ravel(), lon_grid.ravel()])

    pts = deaths[["lat", "lon"]].values

    # -----------------------------------------------
    # PURE NUMPY KDE
    # -----------------------------------------------
    z = np.zeros(grid_flat.shape[1])

    for p in pts:
        d2 = (grid_flat[0] - p[0])**2 + (grid_flat[1] - p[1])**2
        z += np.exp(-d2 / (2 * BANDWIDTH * BANDWIDTH))

    # Normalize 0–1
    z_norm = (z - z.min()) / (z.max() - z.min())

    kde_df = pd.DataFrame({
        "lat": grid_flat[0],
        "lon": grid_flat[1],
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
    pitch=45
)

layers = []

# -------------------------------------------------------
# DEATH POINTS
# -------------------------------------------------------
layers.append(
    pdk.Layer(
        "ScatterplotLayer",
        data=deaths,
        get_position='[lon, lat]',
        get_radius='deaths * 4',
        get_fill_color='[255, 0, 0, 180]',
        pickable=True
    )
)

# -------------------------------------------------------
# PUMPS
# -------------------------------------------------------
layers.append(
    pdk.Layer(
        "ScatterplotLayer",
        data=pumps,
        get_position='[lon, lat]',
        get_radius=25,
        get_fill_color='[0, 0, 255, 180]',
        pickable=True
    )
)

# -------------------------------------------------------
# KDE SURFACE (3D Column Layer)
# -------------------------------------------------------
if kde_toggle and len(kde_df) > 0:
    layers.append(
        pdk.Layer(
            "ColumnLayer",
            data=kde_df,
            get_position='[lon, lat]',
            get_elevation='density * 200',
            radius=3,
            get_fill_color='[255 * density, 160 * density, 0, 180]',
            elevation_scale=40,
            pickable=False
        )
    )

# -------------------------------------------------------
# RENDER MAP
# -------------------------------------------------------
r = pdk.Deck(
    layers=layers,
    initial_view_state=VIEW,
    map_style="mapbox://styles/mapbox/light-v10"
)

st.pydeck_chart(r)

# -------------------------------------------------------
# LEGEND
# -------------------------------------------------------
if kde_toggle:
    st.markdown("""
    ### KDE Legend  
    - **Red/Orange** = High Cholera Intensity  
    - **Yellow** = Medium  
    - **Light Yellow** = Low  
    """)

# -------------------------------------------------------
# DATA TABLES
# -------------------------------------------------------
st.subheader("Deaths Data")
st.dataframe(deaths)

st.subheader("Pumps Data")
st.dataframe(pumps)
