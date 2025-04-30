import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Graphiques multi-sources", layout="wide")
st.title("📈 Données énergétiques détaillées")

# Filtres
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("📅 Date de début", datetime(2025, 4, 1))
with col2:
    end_date = st.date_input("📅 Date de fin", datetime(2025, 4, 30))

col3, col4 = st.columns(2)
with col3:
    start_time = st.time_input("🕐 Heure de début", datetime.min.time())
with col4:
    end_time = st.time_input("🕐 Heure de fin", datetime.max.time())

start_datetime = datetime.combine(start_date, start_time)
end_datetime = datetime.combine(end_date, end_time)

# Device list (à partir du premier fichier)
@st.cache_data
def get_all_device_ids():
    df = pd.read_csv("battery_active_energy_measure.csv")
    return sorted(df["device_id"].unique().tolist())

device_choices = st.multiselect("🔌 Choisir un ou plusieurs devices", get_all_device_ids(), default=[41])

# Définition des sources
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

    df = df[df["device_id"].isin(device_choices)]
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
