import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Infos Batteries", layout="wide")
st.title("📋 Informations batteries")

@st.cache_data
def load_info():
    return pd.read_csv("battery_actives_infos.csv")

df = load_info()

# ================================
# 🔧 Versions matérielles
# ================================
st.subheader("🔧 Versions matérielles")

nb_v1 = (df["hardware_version"] == "ampace_v1").sum()
nb_v2 = (df["hardware_version"] == "ampace_v2").sum()
col1, col2 = st.columns(2)
with col1:
    st.metric("Ampace V1", nb_v1)
with col2:
    st.metric("Ampace V2", nb_v2)

# ================================
# 🧩 Camembert SOH | Histogramme nb_cycles
# ================================
st.subheader("🧩 État de santé et cycles")

df["global_soh"] = pd.to_numeric(df["global_soh"], errors="coerce")
df["global_soh_binned"] = pd.cut(df["global_soh"], bins=[0, 60, 70, 80, 90, 100], right=False)
df_soh = df["global_soh_binned"].value_counts().sort_index()

df["nb_cycles"] = pd.to_numeric(df["nb_cycles"], errors="coerce").fillna(0)

col3, col4 = st.columns(2)

with col3:
    fig_soh = px.pie(
        names=df_soh.index.astype(str),
        values=df_soh.values,
        title="Répartition du SOH (%)",
    )
    st.plotly_chart(fig_soh, use_container_width=True)

with col4:
    fig_cycles = px.histogram(
        df, x="nb_cycles", nbins=20,
        title="Histogramme du nombre de cycles",
        labels={"nb_cycles": "Nombre de cycles"},
    )
    st.plotly_chart(fig_cycles, use_container_width=True)

# ================================
# 🔋 Camembert nb_modules | Camembert working_mode_code
# ================================
st.subheader("🔋 Modules & Modes de fonctionnement")

col5, col6 = st.columns(2)

with col5:
    fig_modules = px.pie(
        names=df["nb_modules"].fillna("Inconnu").astype(str).value_counts().index,
        values=df["nb_modules"].fillna("Inconnu").astype(str).value_counts().values,
        title="Répartition du nombre de modules",
    )
    st.plotly_chart(fig_modules, use_container_width=True)

with col6:
    fig_modes = px.pie(
        names=df["working_mode_code"].fillna("Inconnu").astype(str).value_counts().index,
        values=df["working_mode_code"].fillna("Inconnu").astype(str).value_counts().values,
        title="Répartition des modes de fonctionnement",
    )
    st.plotly_chart(fig_modes, use_container_width=True)
