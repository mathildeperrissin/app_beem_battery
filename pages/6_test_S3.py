import streamlit as st
from google.cloud import storage
import os
import json
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt

# Configuration GCP
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\floch\OneDrive\Documents\GCP_key\streamlit_app\beem-data-warehouse-14a923c674a0.json"
BUCKET_NAME = "beem-backend-battery-warranty"

# --- Chargement des fichiers JSON depuis GCS ---
@st.cache_data
def load_json_data(serial_number, date_start, date_end, hour_start, hour_end):
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)

    # Charger l’index depuis le fichier local
    index_file = f"{serial_number}_index.json"
    if not os.path.exists(index_file):
        st.error(f"Index introuvable : {index_file}")
        return []

    with open(index_file, "r") as f:
        index = json.load(f)

    # Filtrer les fichiers par date et heure
    filtered_files = []
    for entry in index:
        try:
            dt = datetime.strptime(entry["date"], "%Y-%m-%d %H:%M:%S")
            if date_start <= dt.date() <= date_end and hour_start <= dt.hour <= hour_end:
                filtered_files.append((dt, entry["path"]))
        except Exception as e:
            print(f"Erreur parsing date dans {entry['path']} : {e}")

    # Télécharger les fichiers sélectionnés
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
st.title("Suivi de données batterie (GCS)")

serial_number = st.selectbox("Numéro de série", [
    "021LOLF080004M",
    "021LOLF080008M",
    "021LOLK080001M"
])

col1, col2 = st.columns(2)
with col1:
    date_start = st.date_input("Date début", datetime(2025, 4, 1).date())
with col2:
    date_end = st.date_input("Date fin", datetime(2025, 7, 1).date())

st.markdown("### Filtre horaire")
hour_start, hour_end = st.slider(
    "Heure de la journée (intervalle)",
    min_value=0, max_value=23,
    value=(0, 23)
)

if st.button("Charger les données"):
    with st.spinner("Chargement..."):
        records = load_json_data(serial_number, date_start, date_end, hour_start, hour_end)
        df = records_to_dataframe(records)

    if df.empty:
        st.warning("Aucune donnée trouvée pour cette période et plage horaire.")
    else:
        st.success(f"{len(df)} fichiers chargés.")
        st.write("Aperçu des données :")
        st.dataframe(df.head())

        # Choix des index à visualiser
        st.markdown("### Sélection des index à visualiser")
        num_cols = df.shape[1] - 1
        selected_indices = st.multiselect(
            f"Colonnes disponibles (0 à {num_cols - 1})",
            options=list(range(num_cols)),
            default=[0, 1]
        )

        # Affichage des courbes
        for idx in selected_indices:
            plt.figure()
            plt.plot(df['date'], df[idx])
            plt.title(f"Évolution dans le temps - Index {idx}")
            plt.xlabel("Date")
            plt.ylabel("Valeur")
            plt.grid(True)
            st.pyplot(plt)
