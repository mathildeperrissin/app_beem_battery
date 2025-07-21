import os
import json
from datetime import datetime
from google.cloud import storage

# Configuration GCP
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\floch\OneDrive\Documents\GCP_key\streamlit_app\beem-data-warehouse-14a923c674a0.json"
BUCKET_NAME = "beem-backend-battery-warranty"
SERIAL_NUMBER = "021LOLF080004M"  # Batterie cible

# Création du client GCS et récupération du bucket
client = storage.Client()
bucket = client.bucket(BUCKET_NAME)

# Index qui va contenir pour chaque fichier : le chemin et la date extraite
index = []

# Lister tous les blobs dont le préfixe correspond au numéro de série
blobs = bucket.list_blobs(prefix=f"{SERIAL_NUMBER}/")

for blob in blobs:
    filename = blob.name.split('/')[-1]
    print(f"📂 Fichier trouvé : {filename}")
    try:
        # Exemple de nom de fichier attendu :
        # 000000522_2025-05-01T23-59-58-000.json
        # On extrait la partie date/heure après le '_' et avant l'extension.
        datetime_str = filename.split('_')[1].split('.')[0]  # => "2025-05-01T23-59-58-000"

        # On parse la date en utilisant le format approprié.
        # Ici le format est "%Y-%m-%dT%H-%M-%S-%f" (les millisecondes avec %f)
        dt = datetime.strptime(datetime_str, "%Y-%m-%dT%H-%M-%S-%f")

        # Ajouter l'entrée à l'index
        index.append({
            "path": blob.name,
            "date": dt.strftime("%Y-%m-%d %H:%M:%S")
        })
    except Exception as e:
        print(f"❌ Erreur avec {filename} : {e}")

# Sauvegarder l'index dans un fichier JSON
index_filename = f"{SERIAL_NUMBER}_index.json"
with open(index_filename, "w") as f:
    json.dump(index, f, indent=2)

print(f"✅ {len(index)} fichiers indexés pour {SERIAL_NUMBER}")
print(f"📁 Index enregistré dans {index_filename}")
