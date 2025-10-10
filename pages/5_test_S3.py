import streamlit as st
from google.cloud import storage, bigquery
import os
import json
from datetime import datetime, time, timedelta
import pandas as pd
import plotly.express as px

# =========================
# Config GCP
# =========================
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\floch\OneDrive\Documents\GCP_key\streamlit_app\beem-data-warehouse-14a923c674a0.json"
BUCKET_NAME = "beem-backend-battery-warranty"
INDEX_BUCKET_NAME = "beem-battery-indexes"

st.title("📈 Debug data batteries")

# =========================
# Lecture silencieuse des noms de colonnes depuis 2 CSV locaux
# =========================
BBV1_COLUMNS_CSV_PATH = "column_BBV1.csv"
BBV2_COLUMNS_CSV_PATH = "column_BBV2.csv"

@st.cache_data
def _make_unique(names):
    seen = {}
    out = []
    for n in names:
        if n not in seen:
            seen[n] = 0
            out.append(n)
        else:
            seen[n] += 1
            out.append(f"{n}_{seen[n]}")
    return out

@st.cache_data
def _read_names_from_csv(path) -> list:
    """
    Accepte :
      - une seule ligne "a,b,c,..."
      - une valeur par ligne (avec ou sans en-tête 'name')
      - séparateurs virgule ou point-virgule
    """
    import re
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []

    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

    if len(lines) == 1:
        items = [x.strip().strip('"').strip("'") for x in re.split(r"[;,]", lines[0]) if x.strip()]
    else:
        if lines[0].lower() in {"name", "names", "column", "columns"}:
            lines = lines[1:]
        if any(("," in ln) or (";" in ln) for ln in lines):
            tokens = []
            for ln in lines:
                tokens += [x.strip().strip('"').strip("'") for x in re.split(r"[;,]", ln) if x.strip()]
            items = tokens
        else:
            items = [ln.strip('"').strip("'") for ln in lines]

    return _make_unique(items)

try:
    BBV1_COLUMNS = _read_names_from_csv(BBV1_COLUMNS_CSV_PATH)
    BBV2_COLUMNS = _read_names_from_csv(BBV2_COLUMNS_CSV_PATH)
except Exception as e:
    st.error(f"Impossible de lire les CSV de colonnes ({BBV1_COLUMNS_CSV_PATH}, {BBV2_COLUMNS_CSV_PATH}) : {e}")
    st.stop()

# =========================
# Battery devices (serial -> hardware_version)
# =========================
@st.cache_data
def get_devices_table():
    client = bigquery.Client()
    query = """
        SELECT d.serial_number, d.hardware_version
        FROM `beem-data-warehouse.airbyte_postgresql.battery_device` AS d
        WHERE d.deleted_at IS NULL
          AND d.replaced_by_id IS NULL
          AND d.warranty_status = 'activated'
    """
    rows = client.query(query).result()
    df = pd.DataFrame([{"serial_number": r.serial_number, "hardware_version": r.hardware_version} for r in rows])
    df = df.sort_values("serial_number")
    return df

@st.cache_data
def get_serial_numbers():
    return get_devices_table()["serial_number"].tolist()

def get_hw_version_for_serial(serial_number: str) -> str | None:
    df = get_devices_table()
    row = df.loc[df["serial_number"] == serial_number]
    if row.empty:
        return None
    return (row["hardware_version"].iloc[0] or "").strip().lower()

# =========================
# Chargement JSON depuis GCS (arbo + index)
# =========================
@st.cache_data
def load_json_data(serial_number, selected_date, start_time, end_time):
    client = storage.Client()
    data_bucket = client.bucket(BUCKET_NAME)
    index_bucket = client.bucket(INDEX_BUCKET_NAME)

    date_only = selected_date
    records = []

    def try_arborescence():
        out = []
        prefix = f"{serial_number}/{selected_date.year}/{selected_date.month}/{selected_date.day}/"
        blobs = client.list_blobs(BUCKET_NAME, prefix=prefix)
        for blob in blobs:
            filename = os.path.basename(blob.name)
            try:
                parts = filename.split('_')
                timestamp_raw = parts[1].split('.')[0]         # 2025-07-23T13-58-43-000
                timestamp_str = timestamp_raw[:19]             # 2025-07-23T13-58-43
                dt = datetime.strptime(timestamp_str, "%Y-%m-%dT%H-%M-%S")
                if dt.date() == date_only and start_time <= dt.time() <= end_time:
                    out.append((dt, blob.name))
            except:
                pass
        return out

    def try_index():
        out = []
        index_blob_path = f"{serial_number}_index.json"
        index_blob = index_bucket.blob(index_blob_path)
        content = index_blob.download_as_text()
        index = json.loads(content)
        for entry in index:
            dt = datetime.strptime(entry["date"], "%Y-%m-%d %H:%M:%S")
            if dt.date() == date_only and start_time <= dt.time() <= end_time:
                out.append((dt, entry["path"]))
        return out

    if date_only < datetime(2025, 7, 21).date():
        filtered_files = try_index()
    elif date_only > datetime(2025, 7, 23).date():
        filtered_files = try_arborescence()
    else:
        filtered_files = try_arborescence() or try_index()

    for dt, path in filtered_files:
        blob = data_bucket.blob(path)
        parsed = json.loads(blob.download_as_text())
        records.append({"date": dt, "values": parsed["data"]})

    return records

# =========================
# Transformation -> DataFrame + renommage selon hardware_version
# =========================
def align_and_warn(names: list, n_data_cols: int, label: str):
    """
    Le CSV (names) est la référence.
    - Si JSON a moins de colonnes que le CSV : on l'indique et on tronque les noms.
    - Si JSON a plus de colonnes : on complète avec extra_*.
    - Si égal : message OK.
    """
    expected = len(names)

    if n_data_cols == expected:
        st.info(f"{label} : {expected} colonnes attendues, et {n_data_cols} colonnes trouvées dans les fichiers JSON — correspondance parfaite ✅")
        return names

    if n_data_cols < expected:
        diff = expected - n_data_cols
        st.warning(
            f"{label} : on attend {expected} colonnes, ici il y a {n_data_cols} colonnes dans les fichiers JSON "
            f"(−{diff}). Les {diff} dernières colonnes du CSV ne seront pas utilisées."
        )
        return names[:n_data_cols]

    # n_data_cols > expected
    diff = n_data_cols - expected
    fill = [f"extra_{i+1}" for i in range(diff)]
    st.warning(
        f"{label} : on attend {expected} colonnes, ici il y a {n_data_cols} colonnes dans les fichiers JSON "
        f"(+{diff}). {diff} noms fictifs (extra_*) ont été ajoutés."
    )
    return names + fill



def records_to_dataframe(records, serial_number: str):
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    values = pd.DataFrame(df["values"].to_list())
    df = pd.concat([df["date"], values], axis=1)

    n = df.shape[1] - 1  # hors "date"

    hw = get_hw_version_for_serial(serial_number)
    if hw == "ampace_v1":
        chosen_names = align_and_warn(BBV1_COLUMNS, n, "BBV1")
        df.columns = ["date"] + chosen_names
        st.info("Attribution des noms basée sur hardware_version = ampace_v1 (BBV1).")
    elif hw == "ampace_v2":
        chosen_names = align_and_warn(BBV2_COLUMNS, n, "BBV2")
        df.columns = ["date"] + chosen_names
        st.info("Attribution des noms basée sur hardware_version = ampace_v2 (BBV2).")
    else:
        # fallback si pas trouvé : on informe et on applique BBV2 par défaut (ou BBV1 si tu préfères)
        st.warning(f"hardware_version inconnue pour {serial_number} → fallback BBV2.")
        chosen_names = align_and_warn(BBV2_COLUMNS, n, "BBV2")
        df.columns = ["date"] + chosen_names

    return df

# =========================
# Sélection de la plage horaire (avec option auto/manuelle)
# =========================
serial_number = st.selectbox("Numéro de série", get_serial_numbers())
selected_date = st.date_input("📅 Date", datetime.today().date())

c1, c2 = st.columns(2)
with c1:
    bug_hour = st.selectbox("Heure du bug", list(range(24)), index=12)
with c2:
    bug_minute = st.selectbox("Minute du bug", list(range(60)), index=0)

bug_datetime = datetime.combine(selected_date, time(bug_hour, bug_minute))

auto_range = st.checkbox("🧠 Plage automatique autour du bug (−15min / +5min)", value=True)

if auto_range:
    start_dt = bug_datetime - timedelta(minutes=15)
    end_dt   = bug_datetime + timedelta(minutes=5)
    start_time = start_dt.time()
    end_time   = end_dt.time()
    st.info(f"⏱ Analyse automatique de {start_time.strftime('%H:%M')} à {end_time.strftime('%H:%M')}")
else:
    c3, c4 = st.columns(2)
    with c3:
        start_time = st.time_input("🕒 Heure de début", time(0, 0), step=timedelta(minutes=5))
    with c4:
        end_time = st.time_input("🕒 Heure de fin", time(23, 55), step=timedelta(minutes=5))

# =========================
# Chargement + affichage
# =========================
if st.button("Charger"):
    records = load_json_data(serial_number, selected_date, start_time, end_time)
    df = records_to_dataframe(records, serial_number)

    if df.empty:
        st.warning("Aucune donnée sur la plage demandée.")
    else:
        st.dataframe(df.head())

        st.markdown("### 📉 Graphs")

        # Conversion sûre pour les dates
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

        for name in df.columns[1:]:
            fig = px.line(
                df,
                x="date",
                y=name,
                title=name,
                labels={"date": "Heure", name: "Valeur"},
                markers=True,
            )

            # 🔴 Ligne verticale pointillée à l'heure du bug (sans texte)
            fig.add_vline(
                x=bug_datetime,
                line_dash="dash",
                line_color="red"
            )

            st.plotly_chart(fig, use_container_width=True)

