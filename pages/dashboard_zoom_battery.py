import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px

st.set_page_config(page_title="Zoom Battery", layout="wide")
st.title("🔍 Dashboard Zoom sur une batterie")

# ========== 📦 Charger infos batteries ==========
@st.cache_data
def load_infos():
    return pd.read_csv("battery_actives_infos.csv")

infos_df = load_infos().dropna(subset=["device_id"])

# ========== 🎛️ Filtres liés : lastname / serial_number / device_id ==========
st.subheader("🎛️ Filtrage batterie (lié par nom / n° série / device)")

lastnames = sorted(infos_df["lastname"].dropna().unique().tolist())
serials = sorted(infos_df["serial_number"].dropna().unique().tolist())

col1, col2 = st.columns(2)
with col1:
    selected_name = st.selectbox("👤 Nom (lastname)", [""] + lastnames)
with col2:
    selected_serial = st.selectbox("🔢 Numéro de série", [""] + serials)

filtered_df = infos_df.copy()
if selected_name:
    filtered_df = filtered_df[filtered_df["lastname"] == selected_name]
if selected_serial:
    filtered_df = filtered_df[filtered_df["serial_number"] == selected_serial]

available_devices = sorted(filtered_df["device_id"].dropna().unique().tolist())

if not available_devices:
    st.warning("Aucune correspondance pour cette combinaison.")
    st.stop()

selected_device = st.selectbox("🔌 Choisir un device_id", available_devices)

# Affichage infos liées
ligne = infos_df[infos_df["device_id"] == selected_device].iloc[0]
st.info(
    f"👤 Utilisateur associé : **{ligne['lastname']}**\n\n"
    f"🔢 Numéro de série : **{ligne['serial_number']}**\n\n"
    f"🔌 device_id sélectionné : **{selected_device}**"
)

# ========== 🧾 Informations techniques ==========
device_info = infos_df[infos_df["device_id"] == selected_device]

st.subheader("🔧 Informations techniques")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Version hardware", device_info["hardware_version"].values[0])
with col2:
    st.metric("Nombre de cycles", int(device_info["nb_cycles"].values[0]))
with col3:
    st.metric("SOH (%)", round(device_info["global_soh"].values[0], 1))

col4, col5 = st.columns(2)
with col4:
    st.metric("Nb modules", int(device_info["nb_modules"].values[0]))
with col5:
    mode_clean = device_info["working_mode_code"].astype(str).values[0]
    mode_clean = mode_clean.replace("ampace_v1_", "").replace("ampace_v2_", "")
    st.metric("Mode de fonctionnement", mode_clean)

# ========== 🗺️ Carte ==========
st.subheader("📍 Localisation de la batterie")

device_info["point_size"] = 20

fig_map = px.scatter_mapbox(
    device_info,
    lat="latitude",
    lon="longitude",
    size="point_size",
    size_max=30,
    zoom=5,
    height=400,
    hover_name="lastname"
)
fig_map.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":0,"l":0,"b":0})
st.plotly_chart(fig_map, use_container_width=True)

# ========== 📊 Comparaison Objectif vs Mesuré ==========
st.subheader("📊 Comparaison production (objective vs mesurée)")

@st.cache_data
def load_monthly_data():
    df_obj = pd.read_csv("objective_battery.csv")
    df_prod = pd.read_csv("monthly_production_battery.csv")

    if "month" not in df_prod.columns:
        df_prod["date"] = pd.to_datetime(df_prod["date"])
        df_prod["month"] = df_prod["date"].dt.month

    df_obj = df_obj[df_obj["battery_id"] == selected_device]
    df_prod = df_prod[df_prod["battery_id"] == selected_device]

    agg_obj = df_obj.groupby("month")["value"].sum().reset_index()
    agg_obj.rename(columns={"value": "objective"}, inplace=True)

    agg_prod = df_prod.groupby("month")["watt_hours"].sum().reset_index()
    agg_prod.rename(columns={"watt_hours": "measured"}, inplace=True)

    df_merge = pd.merge(agg_obj, agg_prod, on="month", how="outer").sort_values("month").fillna(0)
    df_melted = df_merge.melt(id_vars="month", var_name="Source", value_name="Wh")

    return df_melted, df_merge

df_comparaison, df_pivot = load_monthly_data()

fig_comp = px.bar(
    df_comparaison,
    x="month",
    y="Wh",
    color="Source",
    barmode="group",
    title="Comparaison mensuelle : Objectif vs Production réelle",
    labels={"month": "Mois", "Wh": "Énergie (Wh)"}
)
st.plotly_chart(fig_comp, use_container_width=True)

# ========== 📋 Taux de réalisation (%)
st.subheader("📋 Taux de réalisation par mois (%)")

df_pivot["Taux de réalisation (%)"] = (
    (df_pivot["measured"] / df_pivot["objective"]) * 100
).round(1).replace([float("inf"), -float("inf")], 0).fillna(0)

st.dataframe(
    df_pivot[["month", "objective", "measured", "Taux de réalisation (%)"]],
    use_container_width=True,
    height=400
)

# ========== 📅 Filtres temporels ==========
st.subheader("⏱️ Plage de temps pour les courbes")

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Date de début", datetime(2025, 4, 1))
with col2:
    end_date = st.date_input("Date de fin", datetime(2025, 4, 30))

col3, col4 = st.columns(2)
with col3:
    start_time = st.time_input("Heure de début", datetime.min.time())
with col4:
    end_time = st.time_input("Heure de fin", datetime.max.time())

start_datetime = datetime.combine(start_date, start_time)
end_datetime = datetime.combine(end_date, end_time)

# ========== 📈 Courbes multi-sources ==========
sources = {
    "battery_active_energy_measure.csv": {
        "title": "Consommation infra-journalière",
        "y_label": "Wh par batterie",
        "agg": False,
    },
    "battery_active_returned_energy_meter_measure.csv": {
        "title": "Ré-injection infra-journalière",
        "y_label": "Wh par batterie",
        "agg": False,
    },
    "battery_active_returned_energy_measure.csv": {
        "title": "Production solaire (somme MPPT)",
        "y_label": "Wh total",
        "agg": True,
    },
    "battery_energy_charged_measure.csv": {
        "title": "Énergie stockée (batterie)",
        "y_label": "Wh",
        "agg": False,
    },
    "battery_energy_discharged_measure.csv": {
        "title": "Énergie déstockée (batterie)",
        "y_label": "Wh",
        "agg": False,
    },
}

@st.cache_data
def load_data(filename):
    df = pd.read_csv(filename)
    df["date"] = pd.to_datetime(df["date"])
    return df

for file, meta in sources.items():
    df = load_data(file)
    df = df[df["device_id"] == selected_device]
    df = df[(df["date"].dt.tz_localize(None) >= start_datetime) & (df["date"].dt.tz_localize(None) <= end_datetime)]

    if df.empty:
        st.warning(f"Aucune donnée pour : {meta['title']}")
        continue

    if meta["agg"] and "device_sub_id" in df.columns:
        df = df.groupby(["date", "device_id"], as_index=False)["value"].sum()

    df_chart = df.pivot(index="date", columns="device_id", values="value")

    st.subheader(meta["title"])
    st.line_chart(df_chart, use_container_width=True)
    st.caption(f"Axe Y : {meta['y_label']}")
