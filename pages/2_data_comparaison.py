# Page Streamlit pour comparer deux batteries 

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone, date
from google.cloud import bigquery
import os
from google.cloud import bigquery

# Authentification
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\floch\OneDrive\Documents\GCP_key\streamlit_app\beem-data-warehouse-14a923c674a0.json"
client = bigquery.Client()

st.set_page_config(page_title="BART - data comparaison", layout="wide")
st.title("🔋 Comparaison de deux batteries")

# ========== 📦 Charger infos batteries ==========
@st.cache_data
def load_infos():
    query = """
        WITH device_user_data AS (
         SELECT *
          FROM `beem-data-warehouse.airbyte_postgresql.battery_device` AS d
          LEFT JOIN `beem-data-warehouse.airbyte_postgresql.battery_live_data` AS ld ON ld.battery_id = d.id
          LEFT JOIN `beem-data-warehouse.airbyte_postgresql.house_user` AS hu ON d.house_id = hu.house_id 
          LEFT JOIN `beem-data-warehouse.airbyte_postgresql.user` AS u ON hu.user_id = u.id
          LEFT JOIN `beem-data-warehouse.airbyte_postgresql.house` AS h ON h.id = hu.house_id
          WHERE d.deleted_at IS NULL
            AND d.replaced_by_id IS NULL
            AND d.warranty_status = 'activated'
            AND d.serial_number NOT IN ('021LOLL190154M','021LOLF080008M')
        ),
        serial_counts AS (
          SELECT serial_number, COUNT(*) AS nb
          FROM device_user_data
          GROUP BY serial_number
        ),
        final AS (
          SELECT dud.*
          FROM device_user_data dud
          JOIN serial_counts sc ON dud.serial_number = sc.serial_number
          WHERE 
            sc.nb = 1 OR (
            sc.nb > 1 AND dud.email NOT LIKE '%@beemenergy.com' AND dud.email NOT LIKE '%@beemenergy.fr')
        )
        SELECT * FROM final;
    """
    df = client.query(query).to_dataframe()
    df.rename(columns={"id": "device_id"}, inplace=True)
    return df.dropna(subset=["device_id"])

infos_df = load_infos()
serials = sorted(infos_df["serial_number"].dropna().unique().tolist())

# ========== Sélection des deux batteries ==========
st.subheader("🎛️ Sélectionne deux batteries à comparer")
col1, col2 = st.columns(2)

with col1:
    serial_1 = st.selectbox("🔋 Batterie 1 - Numéro de série", serials, key="serial1")
    dev_1 = infos_df[infos_df["serial_number"] == serial_1]["device_id"].iloc[0]

with col2:
    serial_2 = st.selectbox("🔋 Batterie 2 - Numéro de série", [s for s in serials if s != serial_1], key="serial2")
    dev_2 = infos_df[infos_df["serial_number"] == serial_2]["device_id"].iloc[0]

# ========== 🔧 Infos techniques ==========
st.subheader("🔧 Informations techniques des batteries")
col1, col2 = st.columns(2)

for idx, (device_id, col) in enumerate(zip([dev_1, dev_2], [col1, col2]), 1):
    device_info = infos_df[infos_df["device_id"] == device_id].iloc[0]
    with col:
        st.markdown(f"#### Batterie {idx}")
        st.metric("Version HW", device_info["hardware_version"])
        created = pd.to_datetime(device_info["created_at"]) if pd.notnull(device_info["created_at"]) else None
        created_str = created.strftime("%d/%m/%Y") if created else "Inconnue"
        st.metric("Mise en service", created_str)
        st.metric("Cycles", int(device_info["nb_cycles"]))
        st.metric("Modules", int(device_info["nb_modules"]))
        st.metric("SOH (%)", round(device_info["global_soh"], 1))
        mode_clean = str(device_info["working_mode_code"]).replace("ampace_v1_", "").replace("ampace_v2_", "")
        st.metric("Mode", mode_clean)

# ========== Filtres temporels communs ==========
st.subheader("🗓️ Plage temporelle commune")
col1, col2 = st.columns(2)

# Dates par défaut dynamiques
default_end = date.today()
default_start = default_end - timedelta(days=2)

with col1:
    start_date = st.date_input("Date de début", default_start)
with col2:
    end_date = st.date_input("Date de fin", default_end)

start_str = datetime.combine(start_date, datetime.min.time()).isoformat()
end_str = datetime.combine(end_date, datetime.max.time()).isoformat()

# ========== 📏 Réglage axe Y ==========
st.subheader("📏 Réglage de l'échelle Y")
max_y = st.slider(
    "Valeur maximale de l'axe Y (Wh)", 
    min_value=0, 
    max_value=15000, 
    value=2000, 
    step=200
)

# ========== 📊 Données à comparer ==========
sources = {
    "battery_active_energy_measure": "Conso infra-journalière",
    "battery_active_returned_energy_measure": "Production solaire",
    "battery_energy_charged_measure": "Énergie stockée",
    "battery_energy_discharged_measure": "Énergie déstockée",
}

selected_sources = st.multiselect("Mesures à afficher", options=list(sources.keys()), format_func=lambda x: sources[x], default=list(sources.keys()))

@st.cache_data
def load_data(table, device_id, start, end):
    query = f"""
        SELECT date, value
        FROM `beem-data-warehouse.mongodb.{table}`
        WHERE deviceId = {device_id}
          AND DATETIME(date) BETWEEN DATETIME('{start}') AND DATETIME('{end}')
    """
    df = client.query(query).to_dataframe()
    df["date"] = pd.to_datetime(df["date"])
    return df

# ========== 📈 Affichage comparé ==========
st.subheader("📈 Comparaison des courbes")
fig = go.Figure()

for device_id, label in [(dev_1, "Batterie 1"), (dev_2, "Batterie 2")]:
    for table in selected_sources:
        df = load_data(table, device_id, start_str, end_str)
        if df.empty:
            continue
        df = df.sort_values("date")
        fig.add_trace(go.Scatter(
            x=df["date"],
            y=df["value"],
            mode="lines",
            name=f"{sources[table]} - {label}"
        ))

fig.update_layout(
    title="Comparaison des mesures batteries",
    xaxis_title="Date",
    yaxis_title="Wh",
    height=600,
    yaxis=dict(range=[0, max_y])
)

st.plotly_chart(fig, use_container_width=True)
