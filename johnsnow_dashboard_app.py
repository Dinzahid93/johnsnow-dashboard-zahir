# ============================================================
# TAB 3 — 3D DEATH STACKING
# ============================================================
with tab3:
    st.subheader("3D Stacked Visualization of Cholera Deaths")
    st.markdown("""
    This 3D visualization shows how many cholera deaths occurred at each building.  
    Each vertical bar represents one building location, and the **height of the bar**  
    corresponds to the number of deaths recorded there.
    """)

    import plotly.graph_objects as go

    # Prepare data
    df3d = pd.DataFrame({
        "lat": deaths.geometry.y,
        "lon": deaths.geometry.x,
        "deaths": deaths[death_col],
        "nearest_pump": deaths["nearest_pump_id"],
        "dist": deaths["distance_to_pump_m"]
    })

    # Normalize bar width
    bar_size = 0.00015  # small offset for lon/lat bar width

    fig = go.Figure()

    # Add 3D bars
    for _, row in df3d.iterrows():
        fig.add_trace(go.Scatter3d(
            x=[row["lon"]],
            y=[row["lat"]],
            z=[row["deaths"]],
            mode="markers",
            marker=dict(size=6, color="red"),
            hovertemplate=(
                f"<b>Deaths:</b> {row['deaths']}<br>"
                f"<b>Nearest Pump:</b> {row['nearest_pump']}<br>"
                f"<b>Distance:</b> {row['dist']:.1f} m<br>"
                f"<b>Lat:</b> {row['lat']:.5f}<br>"
                f"<b>Lon:</b> {row['lon']:.5f}<br>"
            )
        ))

        # Fake 3D bar by drawing a vertical line
        fig.add_trace(go.Scatter3d(
            x=[row["lon"], row["lon"]],
            y=[row["lat"], row["lat"]],
            z=[0, row["deaths"]],
            mode="lines",
            line=dict(color="red", width=6),
            showlegend=False
        ))

    # Layout settings
    fig.update_layout(
        height=650,
        scene=dict(
            xaxis_title="Longitude",
            yaxis_title="Latitude",
            zaxis_title="Deaths Count",
            aspectmode="data",
            camera=dict(eye=dict(x=1.3, y=1.3, z=1)),
        ),
        margin=dict(r=10, l=10, b=10, t=10)
    )

    st.plotly_chart(fig, use_container_width=True)
