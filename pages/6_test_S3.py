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
    from datetime import datetime
    from google.cloud import storage
    import json

    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blobs = bucket.list_blobs(prefix=f"{serial_number}/")

    records = []

    for blob in blobs:
        filename = blob.name.split('/')[-1]

        try:
            # Exemple : 000000535_2025-06-23T23-59-53-112Z.json
            # Étape 1 : extraire la partie date brute depuis le nom
            raw_datetime = filename.split('_')[1].split('.')[0]  # "2025-06-23T23-59-53-112Z"

            # Étape 2 : convertir en objet datetime
            clean_datetime_str = raw_datetime.replace('T', ' ')[:19]  # "2025-06-23 23:59:53"
            blob_date = datetime.strptime(clean_datetime_str, "%Y-%m-%d %H:%M:%S")

            # Étape 3 : comparaison par date uniquement
            if date_start <= blob_date.date() <= date_end:
                content = blob.download_as_text()
                parsed = json.loads(content)
                records.append({
                    "date": datetime.strptime(parsed["date"], "%Y-%m-%d %H:%M:%S"),
                    "values": parsed["data"]
                })

        except Exception as e:
            print(f"Erreur avec le fichier {filename} : {e}")
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
