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
col1, col2 = st.columns(2)
nb_v1 = (df["hardware_version"] == "ampace_v1").sum()
nb_v2 = (df["hardware_version"] == "ampace_v2").sum()

with col1:
    st.metric("Ampace V1", nb_v1)
with col2:
    st.metric("Ampace V2", nb_v2)

# ================================
# 🧩 Répartition du Global SOH
# ================================
st.subheader("🧩 Répartition du Global SOH (%)")

df["global_soh"] = pd.to_numeric(df["global_soh"], errors="coerce")
df["global_soh_binned"] = pd.cut(df["global_soh"], bins=[0, 60, 70, 80, 90, 100], right=False)
df_soh = df["global_soh_binned"].value_counts().sort_index()
fig_soh = px.pie(
    names=df_soh.index.astype(str),
    values=df_soh.values,
    title="Répartition des batteries par tranche de SOH (%)",
)
st.plotly_chart(fig_soh, use_container_width=True)

# ================================
# 🔁 Histogramme du nb_cycles
# ================================
st.subheader("🔁 Répartition du nombre de cycles (nb_cycles)")

df["nb_cycles"] = pd.to_numeric(df["nb_cycles"], errors="coerce").fillna(0)
fig_cycles = px.histogram(
    df, x="nb_cycles", nbins=20,
    title="Histogramme du nombre de cycles",
    labels={"nb_cycles": "Nombre de cycles"},
)
st.plotly_chart(fig_cycles, use_container_width=True)

# ================================
# 🔋 Répartition du nb_modules
# ================================
st.subheader("🔋 Répartition du nombre de modules")

fig_modules = px.pie(
    names=df["nb_modules"].fillna("Inconnu").astype(str).value_counts().index,
    values=df["nb_modules"].fillna("Inconnu").astype(str).value_counts().values,
    title="Répartition des batteries selon le nombre de modules",
)
st.plotly_chart(fig_modules, use_container_width=True)

# ================================
# ⚙️ Répartition du working_mode_code
# ================================
st.subheader("⚙️ Répartition des modes de fonctionnement (working_mode_code)")

fig_modes = px.pie(
    names=df["working_mode_code"].fillna("Inconnu").astype(str).value_counts().index,
    values=df["working_mode_code"].fillna("Inconnu").astype(str).value_counts().values,
    title="Répartition par code de mode de fonctionnement",
)
st.plotly_chart(fig_modes, use_container_width=True)
