import streamlit as st
from google.cloud import bigquery
import pandas as pd
from datetime import datetime

# Authentification Google (si en local)
# export GOOGLE_APPLICATION_CREDENTIALS="chemin/vers/ta-cle.json"

client = bigquery.Client()

st.title("Suivi de l'énergie par device")

# 📅 Sélection plage de dates
start_date = st.date_input("Date de début", datetime(2025, 4, 1))
end_date = st.date_input("Date de fin", datetime(2025, 4, 30))

# 🕐 Sélection d'heures
start_time = st.time_input("Heure de début", datetime.min.time())
end_time = st.time_input("Heure de fin", datetime.max.time())

# ⏱️ Combiner date + heure
start_datetime = datetime.combine(start_date, start_time)
end_datetime = datetime.combine(end_date, end_time)

# 📦 Récupération des devices disponibles
@st.cache_data
def get_device_ids():
    query = """
        SELECT DISTINCT device_id
        FROM `beem-data-warehouse.mongo_beem.battery_active_energy_measure`
        ORDER BY device_id
    """
    return client.query(query).to_dataframe()

devices = get_device_ids()
device_choices = st.multiselect("Sélectionner un ou plusieurs devices", devices["device_id"].tolist(), default=[41])

# 🔍 Charger les données selon filtres
@st.cache_data
def load_data(device_ids, start_dt, end_dt):
    # Convertir liste de devices en string SQL
    ids_str = ", ".join(str(d) for d in device_ids)
    
    query = f"""
        SELECT date, device_id, value
        FROM `beem-data-warehouse.mongo_beem.battery_active_energy_measure`
        WHERE device_id IN ({ids_str})
          AND date BETWEEN TIMESTAMP('{start_dt}') AND TIMESTAMP('{end_dt}')
        ORDER BY date
    """
    return client.query(query).to_dataframe()

if device_choices:
    df = load_data(device_choices, start_datetime.isoformat(), end_datetime.isoformat())
    
    if not df.empty:
        # 📈 Afficher la courbe
        st.line_chart(df.pivot(index='date', columns='device_id', values='value'))
    else:
        st.warning("Aucune donnée pour la sélection.")
else:
    st.info("Sélectionne au moins un device.")

