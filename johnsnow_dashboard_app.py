# ============================================================
# CHOLERA MAP WITH LAYERS BY DEATH COUNT (ALL + 1..15)
#
# Data folder: For Folium
#   - deaths_by_bldg.shp
#   - pumps.shp
#
# Output:
#   C:\DIN PERSONAL\4. uitm\Lab Dr Eran\Assignment\cholera_map.html
# ============================================================

import os
import geopandas as gpd
import folium

# -----------------------------
# PATHS  (CHANGE ONLY IF NEEDED)
# -----------------------------
data_folder = r"C:\DIN PERSONAL\4. uitm\Lab Dr Eran\Assignment\For Folium"
save_path   = r"C:\DIN PERSONAL\4. uitm\Lab Dr Eran\Assignment\cholera_map.html"

deaths_path = os.path.join(data_folder, "deaths_by_bldg.shp")
pumps_path  = os.path.join(data_folder, "pumps.shp")

print("Loading data from:")
print("  deaths:", deaths_path)
print("  pumps :", pumps_path)

# -----------------------------
# LOAD DATA
# -----------------------------
deaths = gpd.read_file(deaths_path)
pumps  = gpd.read_file(pumps_path)

# Decide which column is the death count
if "deaths" in deaths.columns:
    death_col = "deaths"
elif "Count" in deaths.columns:
    death_col = "Count"
else:
    raise ValueError("No 'deaths' or 'Count' column in deaths_by_bldg.shp")

# Convert to WGS84 for Folium
deaths_wgs = deaths.to_crs(epsg=4326)
pumps_wgs  = pumps.to_crs(epsg=4326)

# Center on all deaths
center_lat = deaths_wgs.geometry.y.mean()
center_lon = deaths_wgs.geometry.x.mean()

# -----------------------------
# CREATE BASE MAP
# -----------------------------
m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=17,
    tiles="CartoDB Positron"
)

# ------------------------------------------------
# LAYER 1: ALL DEATHS (DEFAULT VISIBLE)
# ------------------------------------------------
all_deaths_layer = folium.FeatureGroup(name="All deaths", show=True)

for _, row in deaths_wgs.iterrows():
    lat, lon = row.geometry.y, row.geometry.x
    d = int(row[death_col])

    # Popup with all attributes
    popup_html = "<b>DEATH LOCATION</b><br><br>"
    for col in deaths.columns:
        if col != "geometry":
            popup_html += f"{col}: {row[col]}<br>"

    # Marker size scaled by deaths
    size = 3 + 0.4 * d

    folium.CircleMarker(
        location=[lat, lon],
        radius=size,
        color="red",
        fill=True,
        fill_color="red",
        fill_opacity=0.7,
        popup=folium.Popup(popup_html, max_width=300),
    ).add_to(all_deaths_layer)

all_deaths_layer.add_to(m)

# ------------------------------------------------
# LAYERS 2..N: ONE LAYER FOR EACH DEATH COUNT
# ------------------------------------------------
unique_counts = sorted(deaths_wgs[death_col].unique())
print("Unique death counts:", unique_counts)

for dval in unique_counts:
    layer_name = f"Deaths = {dval}"
    fg = folium.FeatureGroup(name=layer_name, show=False)  # off by default

    subset = deaths_wgs[deaths_wgs[death_col] == dval]

    for _, row in subset.iterrows():
        lat, lon = row.geometry.y, row.geometry.x

        popup_html = f"<b>DEATH LOCATION (deaths = {dval})</b><br><br>"
        for col in deaths.columns:
            if col != "geometry":
                popup_html += f"{col}: {row[col]}<br>"

        size = 3 + 0.4 * dval

        folium.CircleMarker(
            location=[lat, lon],
            radius=size,
            color="red",
            fill=True,
            fill_color="red",
            fill_opacity=0.7,
            popup=folium.Popup(popup_html, max_width=300),
        ).add_to(fg)

    fg.add_to(m)

# ------------------------------------------------
# PUMPS LAYER (ALWAYS AVAILABLE)
# ------------------------------------------------
pumps_layer = folium.FeatureGroup(name="Water Pumps", show=True)

for _, row in pumps_wgs.iterrows():
    lat, lon = row.geometry.y, row.geometry.x

    popup_html = "<b>WATER PUMP</b><br><br>"
    for col in pumps.columns:
        if col != "geometry":
            popup_html += f"{col}: {row[col]}<br>"

    folium.Marker(
        location=[lat, lon],
        icon=folium.Icon(color="blue", icon="tint", prefix="fa"),
        popup=folium.Popup(popup_html, max_width=300),
    ).add_to(pumps_layer)

pumps_layer.add_to(m)

# -----------------------------
# LAYER CONTROL & SAVE
# -----------------------------
folium.LayerControl().add_to(m)

m.save(save_path)

print("\n=====================================")
print("  ✔ Cholera map with multiple layers created")
print("  ✔ Saved as:")
print(" ", save_path)
print("=====================================")
