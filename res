anomalies = st.Page(
    "pages/07_Anomalies.py",
    title="Anomalies",
    icon="🌪",
)

nav = st.navigation([
    home,
    targets,
    metrics_explorer,
    incidents,
    collections,
    config_inspector,
    thresholds_page,
    anomalies,          # <-- add here too, or it won't register
])


🚩
