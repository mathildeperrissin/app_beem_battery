import streamlit as st
import pandas as pd
from datetime import datetime

st.title("Suivi de l'énergie par device (CSV)")

# 📂 Charger le fichier CSV
@st.cache_data
def load_csv():
    df = pd.read_csv("battery_active_energy_measure.csv")
    df["date"] = pd.to_datetime(df["date"])
    return df

df = load_csv()

# 📅 Sélection plage de dates
start_date = st.date_input("Date de début", datetime(2025, 4, 1))
end_date = st.date_input("Date de fin", datetime(2025, 4, 30))

# 🕐 Sélection d'heures
start_time = st.time_input("Heure de début", datetime.min.time())
end_time = st.time_input("Heure de fin", datetime.max.time())

# ⏱️ Combiner date + heure
start_datetime = datetime.combine(start_date, start_time)
end_datetime = datetime.combine(end_date, end_time)

# 📦 Liste des devices
device_ids = df["device_id"].unique().tolist()
device_choices = st.multiselect("Sélectionner un ou plusieurs devices", device_ids, default=device_ids[:1])

# 🔍 Filtrer les données
filtered_df = df[
    (df["device_id"].isin(device_choices)) &
    (df["date"] >= start_datetime) &
    (df["date"] <= end_datetime)
]

# 📈 Afficher le graphique
if not filtered_df.empty:
    st.line_chart(filtered_df.pivot(index="date", columns="device_id", values="value"))
else:
    st.warning("Aucune donnée à afficher pour ces critères.")
