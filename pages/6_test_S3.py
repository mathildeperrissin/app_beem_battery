import streamlit as st
from google.cloud import storage
import os
import json
from datetime import datetime, time
import pandas as pd
import plotly.express as px

# Configuration GCP
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\floch\OneDrive\Documents\GCP_key\streamlit_app\beem-data-warehouse-14a923c674a0.json"
BUCKET_NAME = "beem-backend-battery-warranty"

# --- Chargement des fichiers JSON depuis GCS ---
@st.cache_data
def load_json_data(serial_number, selected_date, start_time, end_time):
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)

    index_file = f"{serial_number}_index.json"
    if not os.path.exists(index_file):
        st.error(f"Index introuvable : {index_file}")
        return []

    with open(index_file, "r") as f:
        index = json.load(f)

    filtered_files = []
    for entry in index:
        try:
            dt = datetime.strptime(entry["date"], "%Y-%m-%d %H:%M:%S")
            if dt.date() == selected_date and start_time <= dt.time() <= end_time:
                filtered_files.append((dt, entry["path"]))
        except Exception as e:
            print(f"Erreur parsing date dans {entry['path']} : {e}")

    records = []
    for dt, path in filtered_files:
        try:
            blob = bucket.blob(path)
            content = blob.download_as_text()
            parsed = json.loads(content)
            records.append({
                "date": dt,
                "values": parsed["data"]
            })
        except Exception as e:
            print(f"❌ Erreur de lecture {path} : {e}")

    return records

# --- Création du DataFrame ---
def records_to_dataframe(records):
    if not records:
        return pd.DataFrame()
    
    df = pd.DataFrame(records)
    values_expanded = pd.DataFrame(df['values'].to_list())
    df = pd.concat([df['date'], values_expanded], axis=1)
    return df

# --- Interface utilisateur ---
st.title("📈 Suivi de données batterie (GCS)")

serial_number = st.selectbox("Numéro de série", [
    "021LOLF080004M",
    "021LOLF080008M",
    "021LOLK080001M"
])

selected_date = st.date_input("📅 Date à analyser", datetime(2025, 6, 1).date())

col1, col2 = st.columns(2)
with col1:
    start_time = st.time_input("🕒 Heure de début", time(0, 0))
with col2:
    end_time = st.time_input("🕒 Heure de fin", time(23, 59))

if st.button("Charger les données"):
    with st.spinner("Chargement..."):
        records = load_json_data(serial_number, selected_date, start_time, end_time)
        df = records_to_dataframe(records)

    if df.empty:
        st.warning("Aucune donnée trouvée pour cette date et cette plage horaire.")
    else:
        st.success(f"{len(df)} fichiers chargés.")
        st.write("🧾 Aperçu des données :")
        st.dataframe(df.head())

        # Choix des index à visualiser
        st.markdown("### 🎯 Sélection des index à afficher")
        num_cols = df.shape[1] - 1
        selected_indices = st.multiselect(
            f"Colonnes disponibles (0 à {num_cols - 1})",
            options=list(range(num_cols)),
            default=[0, 1]
        )

        # Affichage interactif avec Plotly
        for idx in selected_indices:
            fig = px.line(
                df,
                x="date",
                y=idx,
                title=f"Évolution dans le temps - Index {idx}",
                labels={"date": "Heure", str(idx): "Valeur"}
            )
            st.plotly_chart(fig, use_container_width=True)
