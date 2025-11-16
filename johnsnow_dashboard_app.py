@st.cache_data(show_spinner=False)
def load_snow_tiff_auto_bounds(deaths_wgs):
    """
    Loads the TIFF even if CRS is missing.
    Auto-generates geographic bounds using deaths layer extent.
    """
    if not (RASTER_OK and snowmap_path):
        return None, None

    try:
        with rasterio.open(snowmap_path) as src:
            img = src.read()
            tif_crs = src.crs
            bounds = src.bounds
    except Exception as e:
        st.sidebar.error(f"TIFF cannot be loaded: {e}")
        return None, None

    # ====== HANDLE TIFF WITH NO CRS ======
    if tif_crs is None:
        st.sidebar.warning("TIFF has no CRS. Using auto-bounds from data.")
        minx, miny, maxx, maxy = deaths_wgs.total_bounds

        # expand bounds a bit (padding)
        pad_x = (maxx - minx) * 0.05
        pad_y = (maxy - miny) * 0.05

        west  = minx - pad_x
        south = miny - pad_y
        east  = maxx + pad_x
        north = maxy + pad_y

        bounds_folium = [[south, west], [north, east]]

    else:
        # ====== TIFF HAS CRS → Reproject to WGS84 ======
        try:
            wgs_bounds = transform_bounds(
                tif_crs, "EPSG:4326",
                bounds.left, bounds.bottom, bounds.right, bounds.top
            )
            bounds_folium = [
                [wgs_bounds[1], wgs_bounds[0]],
                [wgs_bounds[3], wgs_bounds[2]],
            ]
        except Exception as e:
            st.sidebar.error(f"TIFF CRS transform failed: {e}")
            return None, None

    # ====== MAKE RGB IMAGE ======
    if img.shape[0] == 1:
        gray = img[0]
        rgb = np.stack([gray, gray, gray], axis=0)
    else:
        rgb = img[:3]

    rgb = np.transpose(rgb, (1, 2, 0)).astype("float32")
    rgb = 255 * (rgb - rgb.min()) / (rgb.max() - rgb.min())
    rgb = rgb.astype("uint8")

    return rgb, bounds_folium
