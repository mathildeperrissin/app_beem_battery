import streamlit as st
from google.cloud import storage
import os

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\floch\OneDrive\Documents\GCP_key\streamlit_app\beem-data-warehouse-14a923c674a0.json"
BUCKET_NAME = "beem-backend-battery-warranty"

client = storage.Client()
bucket = client.bucket(BUCKET_NAME)

serial_number = "021LOLF080004M"

st.title("🔍 Test de listing GCS")
st.write(f"Fichiers dans `{serial_number}/` :")

blobs = list(bucket.list_blobs(prefix=f"{serial_number}/"))
if not blobs:
    st.error("❌ Aucun fichier trouvé — vérifie les permissions ou le chemin.")
else:
    for blob in blobs:
        st.write("📄", blob.name)
