import streamlit as st
import pydeck as pdk
import numpy as np
import pandas as pd
from pyproj import Transformer

st.set_page_config(layout="wide")

st.title("John Snow Cholera Dashboard – KDE (Pure NumPy Version)")

# =======================================================
# FILE UPLOAD
# =======================================================
st.sidebar.header("Upload Data")

deaths_file = st.sidebar.file_uploader("Upload deaths.csv", type=["csv"])
pumps_file  = st.sidebar.file_uploader("Upload pumps.csv", type=["csv"])

if deaths_file is None or pumps_file is None:
    st.warning("Please upload both deaths.csv and pumps.csv to continue.")
    st.stop()

# Read uploaded files
deaths = pd.read_csv(deaths_file)
pumps  = pd.read_csv(pumps_file)

# =======================================================
# CONVERT COORD_X / COORD_Y → LAT / LON
# =======================================================
transformer = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)

deaths["lon"], deaths["lat"] = transformer.transform(
    deaths["COORD_X"].values, deaths["COORD_Y"].values
)

pumps["lon"], pumps["lat"] = transformer.transform(
    pumps["COORD_X"].values, pumps["COORD_Y"].values
)

# =======================================================
# KDE Toggle
# =======================================================
kde_toggle = st.sidebar.checkbox("Show KDE Risk Surface", value=False)

GRID_SIZE = 200
BANDWIDTH = 0.0009

if kde_toggle:

    min_lat, max_lat = deaths.lat.min(), deaths.lat.max()
    min_lon, max_lon = deaths.lon.min(), deaths.lon.max()

    lat_space = np.linspace(min_lat, max_lat, GRID_SIZE)
    lon_space = np.linspace(min_lon, max_lon, GRID_SIZE)

    lon_grid, lat_grid = np.meshgrid(lon_space, lat_space)

    grid_flat = np.vstack([lat_grid.ravel(), lon_grid.ravel()])

    pts = deaths[["lat", "lon"]].values

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

# Death points
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

# Pumps
layers.append(
    pdk.Layer(
        "ScatterplotLayer",
        data=pumps,
        get_position='[lon, lat]',
        get_radius=30,
        get_fill_color='[0, 0, 255, 180]',
        pickable=True
    )
)

# KDE column layer
if kde_toggle and len(kde_df) > 0:
    layers.append(
        pdk.Layer(
            "ColumnLayer",
            data=kde_df,
            get_position='[lon, lat]',
            get_elevation='density * 200',
            radius=3,
            get_fill_color='[255 * density, 160 * density, 0, 180]',
            elevation_scale=40
        )
    )

# Render map
r = pdk.Deck(
    layers=layers,
    initial_view_state=VIEW,
    map_style="mapbox://styles/mapbox/light-v10"
)

st.pydeck_chart(r)

# KDE Legend
if kde_toggle:
    st.markdown("""
    ### KDE Legend  
    🟥 **High Cholera Intensity**  
    🟧 **Moderate**  
    🟨 **Low**
    """)

# Tables
st.subheader("Deaths Table")
st.dataframe(deaths)

st.subheader("Pumps Table")
st.dataframe(pumps)
