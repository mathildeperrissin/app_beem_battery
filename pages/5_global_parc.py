import streamlit as st
import pandas as pd
import plotly.express as px
import os
from google.cloud import bigquery

# Authentification GCP
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\floch\OneDrive\Documents\GCP_key\streamlit_app\beem-data-warehouse-14a923c674a0.json"

# Configuration de la page
st.set_page_config(page_title="BART - global parc", layout="wide")
st.title("📋 Informations parc batteries")

# ============================
# 🔢 Chargement des métriques globales
# ============================
@st.cache_data
def load_global_metrics():
    client = bigquery.Client()
    query = """
        SELECT 
            SUM(deployed_storage) * 1000 AS deployed_storage_wh,
            SUM(deployed_battery_power) * 1000 AS deployed_power_w
        FROM (
            SELECT 
                SUM(nb_modules) * 3.3 AS deployed_storage,
                COUNT(nb_modules) * 6 AS deployed_battery_power
            FROM `beem-data-warehouse.airbyte_postgresql.battery_device` d
            LEFT JOIN `beem-data-warehouse.airbyte_postgresql.battery_live_data` ld 
                ON ld.battery_id = d.id
            WHERE d.deleted_at IS NULL
              AND d.replaced_by_id IS NULL
        ) AS virtual_table
    """
    return client.query(query).to_dataframe().iloc[0]

metrics = load_global_metrics()

col_a, col_b = st.columns(2)
with col_a:
    st.metric("Deployed storage", f"{metrics['deployed_storage_wh'] / 1e6:.2f}M", "Wh")
with col_b:
    st.metric("Deployed flex power", f"{metrics['deployed_power_w'] / 1e6:.2f}M", "W")

# ============================
# 📦 Chargement des données complètes
# ============================
@st.cache_data
def load_info():
    client = bigquery.Client()
    query = """
        SELECT 
    d.id,
    d.serial_number,
    d.hardware_version,
    ld.working_mode_code,
    ld.nb_modules,
    ld.nb_cycles,
    ld.global_soh,
    h.latitude,
    h.longitude
FROM `beem-data-warehouse.airbyte_postgresql.battery_device` AS d
LEFT JOIN `beem-data-warehouse.airbyte_postgresql.battery_live_data` AS ld 
    ON ld.battery_id = d.id
LEFT JOIN `beem-data-warehouse.airbyte_postgresql.house` AS h 
    ON d.house_id = h.id
WHERE d.deleted_at IS NULL
  AND d.replaced_by_id IS NULL
  AND d.warranty_status = 'activated'
  AND d.serial_number NOT IN ('021LOLL190154M', '021LOLF080008M')
    """
    return client.query(query).to_dataframe()

df = load_info()

# ============================
# 🗺️ Cartes interactives séparées par version
# ============================
st.subheader("🗺️ Cartes des batteries par mode de fonctionnement")

df["clean_mode"] = df["working_mode_code"].fillna("Inconnu").astype(str)
df["clean_mode"] = df["clean_mode"].str.replace(r"^ampace_", "", regex=True)
df["point_size"] = 0.5

df_v1 = df[df["hardware_version"] == "ampace_v1"]
df_v2 = df[df["hardware_version"] == "ampace_v2"]

col_map1, col_map2 = st.columns(2)

with col_map1:
    st.markdown("**Ampace V1**")
    fig_map_v1 = px.scatter_mapbox(
    df_v1,
    lat="latitude",
    lon="longitude",
    color="clean_mode",
    hover_name="serial_number",
    size="point_size",
    hover_data={
        "id": True,
        "hardware_version": True,
        "working_mode_code": True,
        "nb_modules": True,
        "nb_cycles": True,
        "global_soh": True,
        "latitude": False,
        "longitude": False,
        "clean_mode": False,
        "point_size": False
    },
    zoom=5,
    height=600
)
    fig_map_v1.update_layout(mapbox_style="open-street-map")
    fig_map_v1.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig_map_v1, use_container_width=True)

with col_map2:
    st.markdown("**Ampace V2**")
    fig_map_v2 = px.scatter_mapbox(
    df_v2,
    lat="latitude",
    lon="longitude",
    color="clean_mode",
    hover_name="serial_number",
    size="point_size",
    hover_data={
        "id": True,
        "hardware_version": True,
        "working_mode_code": True,
        "nb_modules": True,
        "nb_cycles": True,
        "global_soh": True,
        "latitude": False,
        "longitude": False,
        "clean_mode": False,
        "point_size": False
    },
    zoom=5,
    height=600
)

    fig_map_v2.update_layout(mapbox_style="open-street-map")
    fig_map_v2.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig_map_v2, use_container_width=True)


# ============================
# 🔧 Versions matérielles
# ============================
st.subheader("🔧 Versions matérielles")
nb_v1 = (df["hardware_version"] == "ampace_v1").sum()
nb_v2 = (df["hardware_version"] == "ampace_v2").sum()

col1, col2 = st.columns(2)
with col1:
    st.metric("Ampace V1", nb_v1)
with col2:
    st.metric("Ampace V2", nb_v2)

# ============================
# ⚙️ Modes de fonctionnement par version
# ============================
st.subheader("⚙️ Modes de fonctionnement par version")

df_v1 = df[df["hardware_version"] == "ampace_v1"]
df_v2 = df[df["hardware_version"] == "ampace_v2"]

col5, col6 = st.columns(2)
with col5:
    fig_mode_v1 = px.pie(
        names=df_v1["clean_mode"].value_counts().index,
        values=df_v1["clean_mode"].value_counts().values,
        title="Modes de fonctionnement (Ampace V1)",
    )
    st.plotly_chart(fig_mode_v1, use_container_width=True)

with col6:
    fig_mode_v2 = px.pie(
        names=df_v2["clean_mode"].value_counts().index,
        values=df_v2["clean_mode"].value_counts().values,
        title="Modes de fonctionnement (Ampace V2)",
    )
    st.plotly_chart(fig_mode_v2, use_container_width=True)
    
# ============================
# 🧩 État de santé et cycles
# ============================
st.subheader("🧩 État de santé et cycles")

df["global_soh"] = pd.to_numeric(df["global_soh"], errors="coerce")
df["nb_cycles"] = pd.to_numeric(df["nb_cycles"], errors="coerce").fillna(0)

col3, col4 = st.columns(2)
with col3:
    fig_soh = px.histogram(
        df,
        x="global_soh",
        nbins=20,
        title="Histogramme de l'état de santé (SOH %)",
        labels={"global_soh": "SOH (%)"},
    )
    st.plotly_chart(fig_soh, use_container_width=True)

with col4:
    fig_cycles = px.histogram(
        df,
        x="nb_cycles",
        nbins=20,
        title="Histogramme du nombre de cycles",
        labels={"nb_cycles": "Nombre de cycles"},
    )
    st.plotly_chart(fig_cycles, use_container_width=True)

# ============================
# 🔋 Répartition du nombre de modules + control_mode
# ============================
st.subheader("🔋 Répartition du nombre de modules et des control_mode")

# Chargement du graphe control_mode
@st.cache_data
def load_control_mode_data():
    client = bigquery.Client()
    query = """
        WITH virtual_table AS (
            SELECT *
            FROM `beem-data-warehouse.airbyte_postgresql.battery_control_parameters` p
            JOIN `beem-data-warehouse.airbyte_postgresql.battery_device` d
              ON d.id = p.battery_id
            WHERE d.deleted_at IS NULL
              AND d.replaced_by_id IS NULL
              AND d.hardware_version LIKE 'ampace_v1'
        )
        SELECT 
            control_mode,
            COUNT(enable_feature) AS count_enable_feature
        FROM virtual_table
        WHERE enable_feature = TRUE
        GROUP BY control_mode
    """
    return client.query(query).to_dataframe()

df_control_mode = load_control_mode_data()

# Graphes côte à côte
col7, col8 = st.columns(2)

with col7:
    fig_modules = px.pie(
        names=df["nb_modules"].fillna("Inconnu").astype(str).value_counts().index,
        values=df["nb_modules"].fillna("Inconnu").astype(str).value_counts().values,
        title="Répartition du nombre de modules",
    )
    st.plotly_chart(fig_modules, use_container_width=True)

with col8:
    fig_control_mode = px.pie(
        df_control_mode,
        names="control_mode",
        values="count_enable_feature",
        title="Répartition des control_mode (Ampace V1)",
    )
    st.plotly_chart(fig_control_mode, use_container_width=True)


