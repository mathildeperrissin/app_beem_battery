import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title="Infos Batteries", layout="wide")
st.title("📋 Informations batteries")

@st.cache_data
def load_info():
    return pd.read_csv("battery_actives_infos.csv")

df = load_info()

# ================================
# 🔹 1. Compter les hardware_version
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
# 🔸 2. Camembert : Répartition du global_soh
# ================================
st.subheader("🧩 Répartition du Global SOH (%)")

fig1, ax1 = plt.subplots()
df["global_soh"] = df["global_soh"].fillna("inconnu")
df["global_soh_binned"] = pd.cut(df["global_soh"], bins=[0, 60, 70, 80, 90, 100], right=False)
df["global_soh_binned"] = df["global_soh_binned"].astype(str)
df_soh = df["global_soh_binned"].value_counts()
ax1.pie(df_soh, labels=df_soh.index, autopct='%1.1f%%')
ax1.axis('equal')
st.pyplot(fig1)

# ================================
# 🔸 3. Histogramme du nb_cycles
# ================================
st.subheader("🔁 Répartition des cycles (nb_cycles)")

fig2, ax2 = plt.subplots()
df["nb_cycles"] = df["nb_cycles"].fillna(0)
ax2.hist(df["nb_cycles"], bins=20, color='skyblue', edgecolor='black')
ax2.set_xlabel("Nombre de cycles")
ax2.set_ylabel("Nombre de batteries")
st.pyplot(fig2)

# ================================
# 🔸 4. Camembert nb_modules
# ================================
st.subheader("🔋 Répartition du nombre de modules")

fig3, ax3 = plt.subplots()
df["nb_modules"] = df["nb_modules"].fillna("inconnu")
df_modules = df["nb_modules"].value_counts()
ax3.pie(df_modules, labels=df_modules.index, autopct='%1.1f%%')
ax3.axis('equal')
st.pyplot(fig3)

# ================================
# 🔸 5. Camembert du working_mode_code
# ================================
st.subheader("⚙️ Répartition des working_mode_code")

fig4, ax4 = plt.subplots()
df["working_mode_code"] = df["working_mode_code"].fillna("inconnu")
df_working = df["working_mode_code"].value_counts()
ax4.pie(df_working, labels=df_working.index, autopct='%1.1f%%')
ax4.axis('equal')
st.pyplot(fig4)
