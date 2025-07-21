import os
import json
from datetime import datetime
from google.cloud import storage

# Configuration GCP
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\floch\OneDrive\Documents\GCP_key\streamlit_app\beem-data-warehouse-14a923c674a0.json"
DATA_BUCKET_NAME = "beem-backend-battery-warranty"
INDEX_BUCKET_NAME = "beem-battery-indexes"

# Liste des batteries à traiter
SERIAL_NUMBERS = [
    "021LOLF080004M",
    "021LOLF080008M",
    "021LOLK080001M"
]

# Clients GCS
client = storage.Client()
data_bucket = client.bucket(DATA_BUCKET_NAME)
index_bucket = client.bucket(INDEX_BUCKET_NAME)

for serial in SERIAL_NUMBERS:
    print(f"\n🔍 Traitement de la batterie {serial}")
    blobs = data_bucket.list_blobs(prefix=f"{serial}/")
    index = []

    for blob in blobs:
        filename = blob.name.split('/')[-1]
        try:
            datetime_str = filename.split('_')[1].split('.')[0]
            dt = datetime.strptime(datetime_str, "%Y-%m-%dT%H-%M-%S-%f")
            index.append({
                "path": blob.name,
                "date": dt.strftime("%Y-%m-%d %H:%M:%S")
            })
        except Exception as e:
            print(f"❌ Erreur avec {filename} : {e}")

    if index:
        # Fichier local temporaire
        local_index_file = f"{serial}_index.json"
        with open(local_index_file, "w") as f:
            json.dump(index, f, indent=2)

        # Upload vers le bucket d’index
        index_blob = index_bucket.blob(f"{serial}_index.json")
        index_blob.upload_from_filename(local_index_file)
        print(f"✅ {len(index)} fichiers indexés pour {serial}")
        print(f"☁️ Index uploadé vers GCS : {INDEX_BUCKET_NAME}/{serial}_index.json")

        os.remove(local_index_file)
    else:
        print(f"⚠️ Aucun fichier indexé pour {serial}")
