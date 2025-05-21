import streamlit as st
import pandas as pd
import plotly.express as px
import os
from google.cloud import bigquery

# Authentification GCP
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\floch\OneDrive\Documents\GCP_key\streamlit_app\beem-data-warehouse-14a923c674a0.json"

# Configuration de la page
st.set_page_config(page_title="Infos Batteries", layout="wide")
st.title("📋 Informations batteries")

# Chargement des données depuis BigQuery
@st.cache_data
def load_info():
    client = bigquery.Client()
    query = """
        SELECT *
        FROM `beem-data-warehouse.test_Mathilde.battery_actives_infos`
    """
    return client.query(query).to_dataframe()

df = load_info()

# =================================
# Sélection d'une période (ajoutée ici avec clé explicite)
# =================================
st.subheader("📅 Filtrer par date (optionnel)")
date_range_summary = st.date_input("Période à afficher", key="date_range_summary_input")

# =================================
# 🗺️ Carte interactive
# =================================
st.subheader("🗺️ Carte des batteries par mode de fonctionnement")

df["clean_mode"] = df["working_mode_code"].fillna("Inconnu").astype(str)
df["clean_mode"] = df["clean_mode"].str.replace(r"^ampace_v[12]_", "", regex=True)
df["point_size"] = 7  

fig_map = px.scatter_mapbox(
    df,
    lat="latitude",
    lon="longitude",
    color="clean_mode",
    hover_name="lastname",
    size="point_size",
    hover_data=["id", "hardware_version", "nb_cycles"],
    zoom=5,
    height=600
)

fig_map.update_layout(mapbox_style="open-street-map")
fig_map.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
st.plotly_chart(fig_map, use_container_width=True)

# =================================
# 🔧 Versions matérielles
# =================================
st.subheader("🔧 Versions matérielles")
nb_v1 = (df["hardware_version"] == "ampace_v1").sum()
nb_v2 = (df["hardware_version"] == "ampace_v2").sum()

col1, col2 = st.columns(2)
with col1:
    st.metric("Ampace V1", nb_v1)
with col2:
    st.metric("Ampace V2", nb_v2)

# =================================
# 🧩 État de santé et cycles
# =================================
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

# =================================
# 🔋 Répartition du nombre de modules
# =================================
st.subheader("🔋 Répartition du nombre de modules")

fig_modules = px.pie(
    names=df["nb_modules"].fillna("Inconnu").astype(str).value_counts().index,
    values=df["nb_modules"].fillna("Inconnu").astype(str).value_counts().values,
    title="Répartition du nombre de modules",
)
st.plotly_chart(fig_modules, use_container_width=True)

# =================================
# ⚙️ Répartition des modes de fonctionnement par version
# =================================
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
