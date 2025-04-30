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
# 🔧 Versions hardware
# ================================
st.subheader("🔧 Versions hardware")

nb_v1 = (df["hardware_version"] == "ampace_v1").sum()
nb_v2 = (df["hardware_version"] == "ampace_v2").sum()
col1, col2 = st.columns(2)
with col1:
    st.metric("Ampace V1", nb_v1)
with col2:
    st.metric("Ampace V2", nb_v2)

# ================================
# 🔁 Histogramme SOH | Histogramme nb_cycles
# ================================
st.subheader("🧩 État de santé et nombre de cycles")

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
        df, x="nb_cycles", nbins=20,
        title="Histogramme du nombre de cycles",
        labels={"nb_cycles": "Nombre de cycles"},
    )
    st.plotly_chart(fig_cycles, use_container_width=True)

# ================================
# 🔋 Camembert nb_modules
# ================================
st.subheader("🔋 Répartition du nombre de modules")

fig_modules = px.pie(
    names=df["nb_modules"].fillna("Inconnu").astype(str).value_counts().index,
    values=df["nb_modules"].fillna("Inconnu").astype(str).value_counts().values,
    title="Répartition du nombre de modules",
)
st.plotly_chart(fig_modules, use_container_width=True)

# ================================
# ⚙️ Working mode : par version
# ================================
st.subheader("⚙️ Répartition des modes de fonctionnement par version")

# Nettoyer les codes pour retirer le préfixe ampace_v1_ / ampace_v2_
df["clean_mode"] = df["working_mode_code"].fillna("inconnu").astype(str)
df["clean_mode"] = df["clean_mode"].str.replace(r"^ampace_v[12]_", "", regex=True)

# Camemberts par version
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
