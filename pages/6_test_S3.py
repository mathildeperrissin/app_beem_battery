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
def load_json_data(serial_number, date_start, date_end):
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blobs = bucket.list_blobs(prefix=f"{serial_number}/")

    records = []

    for blob in blobs:
        try:
            filename = blob.name.split('/')[-1]
            file_date_str = filename.split('_')[1].split('T')[0]
            file_date = datetime.strptime(file_date_str, "%Y-%m-%d").date()

            if date_start <= file_date <= date_end:
                content = blob.download_as_text()
                parsed = json.loads(content)
                date = datetime.strptime(parsed["date"], "%Y-%m-%d %H:%M:%S")
                records.append({"date": date, "values": parsed["data"]})
        except Exception as e:
            print(f"Erreur dans le fichier {blob.name} : {e}")
            continue

    return records

# --- Création du DataFrame ---
def records_to_dataframe(records):
    if not records:
        return pd.DataFrame()
    
    df = pd.DataFrame(records)
    # on transforme les listes de "values" en colonnes
    values_expanded = pd.DataFrame(df['values'].to_list())
    df = pd.concat([df['date'], values_expanded], axis=1)
    return df

# --- Interface utilisateur ---
st.title("Suivi de données batterie (GCS)")

serial_number = st.selectbox("Numéro de série", [
    "021LOLFO80004M", "021LOLFO80008M", "021LOLK080001M", "021LOLK080002M"  # à adapter selon tes dossiers
])

col1, col2 = st.columns(2)
with col1:
    date_start = st.date_input("Date début", datetime(2025, 4, 1).date())
with col2:
    date_end = st.date_input("Date fin", datetime(2025, 7, 1).date())

if st.button("Charger les données"):
    with st.spinner("Chargement..."):
        records = load_json_data(serial_number, date_start, date_end)
        df = records_to_dataframe(records)

    if df.empty:
        st.warning("Aucune donnée trouvée pour cette période.")
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
