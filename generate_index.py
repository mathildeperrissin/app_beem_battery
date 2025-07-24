import os
import json
from datetime import datetime
from google.cloud import storage, bigquery
from concurrent.futures import ThreadPoolExecutor, as_completed

# Config
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\floch\OneDrive\Documents\GCP_key\streamlit_app\beem-data-warehouse-14a923c674a0.json"
DATA_BUCKET_NAME = "beem-backend-battery-warranty"
INDEX_BUCKET_NAME = "beem-battery-indexes"
MAX_WORKERS = 10  # à ajuster selon ta machine

# Clients
storage_client = storage.Client()
bq_client = bigquery.Client()
data_bucket = storage_client.bucket(DATA_BUCKET_NAME)
index_bucket = storage_client.bucket(INDEX_BUCKET_NAME)

# Requête BQ pour les serials valides
print("📥 Récupération des serials depuis BigQuery...")
results = bq_client.query("""
SELECT DISTINCT serial_number
FROM `beem-data-warehouse.airbyte_postgresql.battery_device` AS d
LEFT JOIN `beem-data-warehouse.airbyte_postgresql.battery_live_data` AS ld
  ON ld.battery_id = d.id
WHERE d.deleted_at IS NULL
  AND d.replaced_by_id IS NULL
  AND d.warranty_status = 'activated'
""").result()
serials = [row.serial_number for row in results if row.serial_number]
print(f"🔎 {len(serials)} batteries actives trouvées")

# Fonction de traitement d'une batterie
def process_battery(serial):
    try:
        blobs = data_bucket.list_blobs(prefix=f"{serial}/")

        # Charger l’index existant s’il existe
        index_blob = index_bucket.blob(f"{serial}_index.json")
        existing_index = []
        existing_paths = set()
        if index_blob.exists():
            existing_index = json.loads(index_blob.download_as_text(timeout=300))
            existing_paths = set(e["path"] for e in existing_index)

        # Construire l'index à jour
        updated_index = existing_index.copy()
        new_entries = 0

        for blob in blobs:
            filename = blob.name.split('/')[-1]
            if not filename or blob.name in existing_paths:
                continue
            try:
                datetime_str = filename.split('_')[1].split('.')[0]
                dt = datetime.strptime(datetime_str, "%Y-%m-%dT%H-%M-%S-%f")
                updated_index.append({
                    "path": blob.name,
                    "date": dt.strftime("%Y-%m-%d %H:%M:%S")
                })
                new_entries += 1
            except Exception:
                continue

        if new_entries > 0:
            updated_index.sort(key=lambda x: x["date"])
            local_file = f"{serial}_index.json"
            with open(local_file, "w") as f:
                json.dump(updated_index, f, indent=2)
            index_blob.upload_from_filename(local_file)
            os.remove(local_file)
        return f"✅ {serial} : +{new_entries} fichiers"
    except Exception as e:
        return f"❌ {serial} : erreur {e}"

# Exécution en parallèle
print(f"🚀 Traitement parallèle des {len(serials)} batteries...")
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {executor.submit(process_battery, s): s for s in serials}
    for future in as_completed(futures):
        print(future.result())
