import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import os
from google.cloud import bigquery
import plotly.graph_objects as go

# Authentification
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\floch\OneDrive\Documents\GCP_key\streamlit_app\beem-data-warehouse-14a923c674a0.json"
client = bigquery.Client()

st.set_page_config(page_title="BART - data explo", layout="wide")
st.title("🔍 Data exploration")


from zoneinfo import ZoneInfo  # si pas déjà importé

# --- Réglages communs ---
LOCAL_TZ = ZoneInfo("Europe/Paris")

# marges identiques pour tous (ajuste si besoin)
ALIGN_L, ALIGN_R, ALIGN_T, ALIGN_B = 90, 30, 60, 0

def _choose_dtick(start_dt, end_dt):
    delta = (end_dt - start_dt).total_seconds()
    if delta <= 48*3600:     # <= 2 jours -> 1h
        return 3600_000
    if delta <= 7*24*3600:   # <= 7 jours -> 6h
        return 6*3600_000
    if delta <= 14*24*3600:  # <= 14 jours -> 12h
        return 12*3600_000
    return 24*3600_000       # sinon 1 jour

def apply_common_time_axis(fig, start_dt, end_dt, *, hide_xticks=False):
    """Applique la même échelle X + mêmes marges à une figure Plotly."""
    fig.update_xaxes(
        range=[start_dt, end_dt],
        type="date",
        tick0=start_dt,
        dtick=_choose_dtick(start_dt, end_dt),
        tickformat="%H:%M\n%b %d",
        showgrid=True,
        showticklabels=not hide_xticks
    )
    fig.update_yaxes(automargin=False, title_standoff=10)  # évite les marges auto variables
    fig.update_layout(margin=dict(l=ALIGN_L, r=ALIGN_R, t=ALIGN_T, b=ALIGN_B))
    return fig


# ========== 📦 Charger infos batteries ==========
@st.cache_data
def load_infos():
    query = """
        WITH device_user_data AS (
     SELECT 
        *
      FROM `beem-data-warehouse.airbyte_postgresql.battery_device` AS d
      LEFT JOIN `beem-data-warehouse.airbyte_postgresql.battery_live_data` AS ld ON ld.battery_id = d.id
      LEFT JOIN `beem-data-warehouse.airbyte_postgresql.house_user` AS hu ON d.house_id = hu.house_id 
      LEFT JOIN `beem-data-warehouse.airbyte_postgresql.user` AS u ON hu.user_id = u.id
      LEFT JOIN `beem-data-warehouse.airbyte_postgresql.house` AS h ON h.id = hu.house_id
      WHERE d.deleted_at IS NULL
        AND d.replaced_by_id IS NULL
        AND d.warranty_status = 'activated'
        --AND d.serial_number NOT IN ('021LOLL190154M','021LOLF080008M')
        --AND u.id NOT IN (22, 4395, 34538)
        --AND d.hardware_version = 'ampace_v1'
    ),

    serial_counts AS (
      SELECT 
        serial_number,
        COUNT(*) AS nb
      FROM device_user_data
      GROUP BY serial_number
    ),
    final AS (
      SELECT dud.*
      FROM device_user_data dud
      JOIN serial_counts sc ON dud.serial_number = sc.serial_number
      WHERE 
        -- si le serial est unique, on garde tout
        sc.nb = 1

        -- si le serial est dupliqué, on garde seulement si email ne se termine pas par @beemenergy
        OR (
        sc.nb > 1
       AND dud.email NOT LIKE '%@beemenergy.com'
        AND dud.email NOT LIKE '%@beemenergy.fr'
      )
    )
    SELECT * FROM final;
    """
    df = client.query(query).to_dataframe()
    df.rename(columns={"id": "device_id"}, inplace=True)
    return df.dropna(subset=["device_id"])

infos_df = load_infos()

# ========== 🎛️ Filtres liés ==========
st.subheader("🎛️ Filtrage batterie (par nom / n° série / device)")

lastnames = sorted(infos_df["lastname"].dropna().unique().tolist())
serials = sorted(infos_df["serial_number"].dropna().unique().tolist())

col1, col2 = st.columns(2)
with col1:
    selected_name = st.selectbox("👤 Nom (lastname)", [""] + lastnames)
with col2:
    selected_serial = st.selectbox("🖟️ Numéro de série", [""] + serials)

filtered_df = infos_df.copy()
if selected_name:
    filtered_df = filtered_df[filtered_df["lastname"] == selected_name]
if selected_serial:
    filtered_df = filtered_df[filtered_df["serial_number"] == selected_serial]

available_devices = sorted(filtered_df["device_id"].dropna().unique().tolist())

if not available_devices:
    st.warning("Aucune correspondance pour cette combinaison.")
    st.stop()

selected_device = st.selectbox("🔌 Choisir un device_id", available_devices)

# Affichage infos liées
ligne = infos_df[infos_df["device_id"] == selected_device].iloc[0]
st.info(
    f"👤 Utilisateur associé : **{ligne['lastname']}**\n\n"
    f"🖟️ Numéro de série : **{ligne['serial_number']}**\n\n"
    f"🔌 device_id sélectionné : **{selected_device}**"
)

# ========== 🨾 Informations techniques ==========
device_info = infos_df[infos_df["device_id"] == selected_device]
st.subheader("🔧 Informations techniques")
created_at_str = pd.to_datetime(device_info["created_at"].values[0]).strftime("%d/%m/%Y") \
    if pd.notnull(device_info["created_at"].values[0]) else "Inconnue"

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Version hardware", device_info["hardware_version"].values[0])
with col2:
    st.metric("Mise en service", created_at_str)
with col3:
    st.metric("Nombre de cycles", int(device_info["nb_cycles"].values[0]))

col4, col5, col6 = st.columns(3)
with col4:
    st.metric("Nb modules", int(device_info["nb_modules"].values[0]))
with col5:
    st.metric("SOH (%)", round(device_info["global_soh"].values[0], 1))



# ========== 🗓️ Filtres temporels ==========

st.subheader("⏱️ Plage de temps pour les courbes")

from datetime import date, timedelta


# Définir les dates par défaut dynamiquement
default_end_date = date.today()
default_start_date = default_end_date - timedelta(days=2)

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Date de début", default_start_date, key="start_main")
with col2:
    end_date = st.date_input("Date de fin", default_end_date, key="end_main")

col3, col4 = st.columns(2)
with col3:
    start_time = st.time_input("Heure de début", datetime.min.time())
with col4:
    end_time = st.time_input("Heure de fin", datetime.max.time())

start_datetime = datetime.combine(start_date, start_time)
end_datetime = datetime.combine(end_date, end_time)

start_str = start_datetime.isoformat()
end_str = end_datetime.isoformat()

# ========== 📍 Repère temporel ==========

st.subheader("📍 Repère temporel (ligne verticale)")

col1, col2 = st.columns(2)
with col1:
    repere_date = st.date_input("Date du repère", value=start_date, key="repere_date")
with col2:
    repere_time = st.time_input("Heure du repère", value=datetime.min.time(), key="repere_time")

repere_datetime = datetime.combine(repere_date, repere_time)


# ========== 📈 Courbes multi-sources combinées ==========

sources = {
    "battery_active_energy_measure": {
        "title": "Consommation infra-journalière",
        "y_label": "Wh par batterie",
        "agg": False,
    },
    "battery_active_returned_energy_meter_measure": {
        "title": "Ré-injection infra-journalière",
        "y_label": "Wh par batterie",
        "agg": False,
    },
    "battery_active_returned_energy_measure": {
        "title": "Production solaire (somme MPPT)",
        "y_label": "Wh total",
        "agg": True,
    },
    "battery_energy_charged_measure": {
        "title": "Énergie stockée (batterie)",
        "y_label": "Wh",
        "agg": False,
    },
    "battery_energy_discharged_measure": {
        "title": "Énergie déstockée (batterie)",
        "y_label": "Wh",
        "agg": False,
    },
}

@st.cache_data
def load_data(table_name, device_id, start_dt, end_dt):
    """
    Charge une table mongodb en détectant automatiquement la colonne id (deviceId/batteryId/...)
    et en filtrant sur la période en TIMESTAMP (compatible TIMESTAMP & DATETIME).
    """
    if isinstance(device_id, str) and device_id.isdigit():
        device_id = int(device_id)

    full_table = f"beem-data-warehouse.mongodb.{table_name}"
    table = client.get_table(full_table)
    cols = {f.name: f.field_type for f in table.schema}

    # 1) Colonne d'identifiant (ordres de préférence)
    id_col = next((c for c in ["deviceId", "batteryId", "device_id", "battery_id"] if c in cols), None)
    if id_col is None:
        raise ValueError(f"Aucune colonne id reconnue dans {full_table} (attendu deviceId/batteryId/...).")

    # 2) Colonne de date
    date_col = "date" if "date" in cols else ("timestamp" if "timestamp" in cols else None)
    if date_col is None:
        raise ValueError(f"Aucune colonne de date reconnue dans {full_table} (attendu date/timestamp).")

    # 3) Build requête (filtre en TIMESTAMP pour éviter les soucis DATETIME)
    query = f"""
        SELECT *
        FROM `{full_table}`
        WHERE {id_col} = {device_id}
          AND TIMESTAMP({date_col}) BETWEEN TIMESTAMP('{start_dt}') AND TIMESTAMP('{end_dt}')
    """

    df = client.query(query).to_dataframe()

    # Normalise la colonne date pour l'affichage Plotly (naive)
    if not df.empty and date_col in df.columns:
        df["date"] = pd.to_datetime(df[date_col], utc=True).dt.tz_localize(None)

    # Valeur : cast en numérique au besoin
    if "value" in df.columns and df["value"].dtype == "object":
        df["value"] = pd.to_numeric(df["value"], errors="coerce")

    return df


# ========= 🔋 Loader SOC (battery_status_entity) =========
@st.cache_data
def load_soc(device_id, start_dt, end_dt):
    # device_id peut venir en str => on cast en int si besoin
    if isinstance(device_id, str) and device_id.isdigit():
        device_id = int(device_id)

    query = f"""
        SELECT date, soc
        FROM `beem-data-warehouse.mongodb.battery_status_entity`
        WHERE batteryId = {device_id}
          AND TIMESTAMP(date) BETWEEN TIMESTAMP('{start_dt}') AND TIMESTAMP('{end_dt}')
          AND soc IS NOT NULL
        ORDER BY date
    """
    df = client.query(query).to_dataframe()
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_localize(None)
    return df

# ========= 🔋 battery_status_entity : colonnes & loader =========
@st.cache_data
def get_status_numeric_cols():
    """Récupère les colonnes numériques de la table battery_status_entity (hors batteryId / date)."""
    table = client.get_table("beem-data-warehouse.mongodb.battery_status_entity")
    numeric_types = {"INTEGER", "INT64", "FLOAT", "FLOAT64", "NUMERIC", "BIGNUMERIC"}
    cols = [
        f.name for f in table.schema
        if f.field_type in numeric_types and f.name not in ("batteryId", "date")
    ]
    cols.sort()
    return cols

@st.cache_data
def load_status_entity(device_id, start_dt, end_dt, columns):
    """Charge date + colonnes demandées pour la batterie et la période données."""
    if isinstance(device_id, str) and device_id.isdigit():
        device_id = int(device_id)

    # dédoublonne et conserve l'ordre
    cols = ["date"] + list(dict.fromkeys(columns))
    select_cols = ", ".join(cols)

    query = f"""
        SELECT {select_cols}
        FROM `beem-data-warehouse.mongodb.battery_status_entity`
        WHERE batteryId = {device_id}
          AND TIMESTAMP(date) BETWEEN TIMESTAMP('{start_dt}') AND TIMESTAMP('{end_dt}')
        ORDER BY date
    """
    df = client.query(query).to_dataframe()
    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_localize(None)
    return df

# ========= 🧭 Mapping + loaders frise modes =========
# ========= 🧭 Mappings V1/V2 =========
# V1 -> workingMode
WORKING_MODE_V1 = {
    0: "Idle",
    1: "PV Check",
    2: "Standby",
    3: "Selfcheck",
    4: "Inverter_wait",
    5: "OffGridInverter",
    6: "OnGridPassby",
    7: "OnGridCharge",
    8: "OnGridDischarge",
    9: "Fault",
}

# V2 -> workingMode (détails officiels)
WORKING_MODE_V2 = {
    0: "cPowerOnMode",
    1: "cWaitMode",
    2: "cBusCheckMode",
    3: "cPreCheckMode",
    4: "cRdyOnGridMode",
    5: "cNormalMode",
    6: "cFaultMode",
    7: "Rsv",
    8: "cFlashMode",
    9: "cShutdownMode",
}

# V2 -> mode
MODE_V2 = {
    0: "smart",
    1: "backup",
    2: "economic",
    3: "off_grid",
    4: "hybrid",
    5: "hybrid_economic",
}

def detect_generation(hardware_version: str) -> str:
    """Retourne 'v2' si la version le suggère, sinon 'v1'."""
    hv = (str(hardware_version) if hardware_version is not None else "").lower()
    if "v2" in hv or "ampace_v2" in hv or "gen2" in hv:
        return "v2"
    return "v1"

def label_func_factory(track: str, gen: str):
    """Retourne une fonction qui mappe la valeur -> label selon la piste et la génération."""
    if track == "mode":
        mapping = MODE_V2
    else:  # workingMode
        mapping = WORKING_MODE_V2 if gen == "v2" else WORKING_MODE_V1

    def _lab(v):
        try:
            return mapping.get(int(v), str(v))
        except Exception:
            return mapping.get(v, str(v))
    return _lab

@st.cache_data
def get_mode_cols(gen: str):
    """Colonnes présentes et pertinentes selon la génération."""
    table = client.get_table("beem-data-warehouse.mongodb.battery_status_entity")
    present = {f.name for f in table.schema}
    cols = []
    if "workingMode" in present:
        cols.append("workingMode")
    if gen == "v2" and "mode" in present:
        cols.append("mode")
    return cols

@st.cache_data
def load_modes_entity(device_id, start_dt, end_dt, cols):
    """Charge date + colonnes de mode demandées (datetimes naïves)."""
    if isinstance(device_id, str) and device_id.isdigit():
        device_id = int(device_id)
    if not cols:
        return pd.DataFrame(columns=["date"])

    select_cols = ", ".join(["date"] + cols)
    query = f"""
        SELECT {select_cols}
        FROM `beem-data-warehouse.mongodb.battery_status_entity`
        WHERE batteryId = {device_id}
          AND TIMESTAMP(date) BETWEEN TIMESTAMP('{start_dt}') AND TIMESTAMP('{end_dt}')
        ORDER BY date
    """
    df = client.query(query).to_dataframe()
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_localize(None)
    return df

def _compress_to_segments(df, col, end_dt, label_func):
    """
    Transforme une série discrète (col) en segments [start, end).
    """
    s = df[["date", col]].dropna().sort_values("date").copy()
    if s.empty:
        return pd.DataFrame(columns=["start", "end", "track", "label"])

    s["date"] = pd.to_datetime(s["date"], utc=True).dt.tz_localize(None)
    end_naive = pd.Timestamp(end_dt)
    if end_naive.tzinfo:
        end_naive = end_naive.tz_localize(None)

    run_id = (s[col] != s[col].shift()).cumsum()
    segs = s.groupby(run_id).agg(start=("date", "first"), value=(col, "last")).reset_index(drop=True)
    segs["end"] = segs["start"].shift(-1)
    segs.loc[segs["end"].isna(), "end"] = end_naive
    segs["track"] = col
    segs["label"] = [label_func(v) for v in segs["value"]]
    segs = segs[segs["end"] > segs["start"]]
    return segs[["start", "end", "track", "label"]]



#########################"GROS GRAPH combiné"""""########################

st.subheader("📊 Visualisation combinée des mesures")

selected_sources = st.multiselect(
    "Sélectionne les courbes à afficher :",
    options=list(sources.keys()),
    format_func=lambda x: sources[x]["title"],
    default=list(sources.keys())  # ou [] si tu veux les cacher par défaut
)

fig = go.Figure()

# Option pour afficher / masquer le SOC (%)
show_soc = st.toggle("Afficher le SOC (%)", value=True)


for table_name in selected_sources:
    meta = sources[table_name]
    df = load_data(table_name, selected_device, start_str, end_str)

    if df.empty:
        st.warning(f"Aucune donnée pour : {meta['title']}")
        continue

    # 🔧 Si la source est "somme MPPT", on agrège par date
    if meta["agg"]:
        # on tolère plusieurs noms possibles de sous-voie selon V1/V2
        if any(c in df.columns for c in ["deviceSubId", "device_sub_id", "mppt", "mpptId"]):
            df = df.groupby("date", as_index=False)["value"].sum()

    df = df.sort_values("date")
    fig.add_trace(go.Scatter(
        x=df["date"],
        y=df["value"],
        mode="lines",
        name=meta["title"]
    ))


# ----- Trace SOC sur axe Y droit -----
if show_soc:
    df_soc = load_soc(selected_device, start_str, end_str)
    if df_soc.empty:
        st.warning("Aucun SOC sur la période.")
    else:
        df_soc = df_soc.sort_values("date")
        fig.add_trace(go.Scatter(
            x=df_soc["date"],
            y=df_soc["soc"],
            mode="lines",
            name="SOC (%)",
            yaxis="y2"  # utilise l'axe droit
        ))

    
# Ajout de la ligne verticale du repère
fig.add_vline(
    x=repere_datetime,
    line_width=2,
    line_dash="dash",
    line_color="red"
)

# Ajout d'une annotation manuelle au-dessus de la ligne
fig.add_annotation(
    x=repere_datetime,
    y=1,
    yref="paper",
    text=repere_datetime.strftime("%Y-%m-%d %H:%M"),
    showarrow=False,
    bgcolor="red",
    font=dict(color="white"),
    xanchor="left"
)

st.subheader("📏 Réglage de l'échelle Y")

max_y = st.number_input(
    "Valeur maximale de l'axe Y (Wh)",
    min_value=0,
    max_value=15000,
    value=600,
    step=100
)


fig.update_layout(
    title="Courbes combinées des mesures",
    title_y=0.99,
    xaxis_title=None,        # on masque le titre X ici
    yaxis_title="Wh",
    legend_title="Type de mesure",
    height=600,
    yaxis=dict(title="Wh", range=[0, max_y]),
    yaxis2=dict(title="SOC (%)", overlaying="y", side="right", range=[0, 100], ticksuffix="%"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0)
)


apply_common_time_axis(fig, start_datetime, end_datetime, hide_xticks=False)




st.plotly_chart(fig, use_container_width=True)

# ========== 🔋 Courbes battery_status_entity (2 axes Y) ==========
st.subheader("🔋 Mesures battery_status_entity")

available_status_cols = get_status_numeric_cols()
if len(available_status_cols) < 2:
    st.info("Pas assez de colonnes numériques dans battery_status_entity pour tracer deux courbes.")
else:
    c1, c2 = st.columns(2)
    with c1:
        y_left_col = st.selectbox(
            "Axe Y gauche",
            options=available_status_cols,
            index=(available_status_cols.index("batteryPower") if "batteryPower" in available_status_cols else 0),
            key="bse_y_left"
        )
    with c2:
        # par défaut: SOC à droite si dispo
        default_right_idx = (
            available_status_cols.index("soc") if "soc" in available_status_cols
            else (1 if len(available_status_cols) > 1 else 0)
        )
        y_right_col = st.selectbox(
            "Axe Y droite",
            options=available_status_cols,
            index=default_right_idx,
            key="bse_y_right"
        )

    df_status = load_status_entity(selected_device, start_str, end_str, [y_left_col, y_right_col])

    if df_status.empty:
        st.info("Aucune donnée battery_status_entity sur cette période.")
    else:
        fig_status = go.Figure()

        # Trace gauche
        fig_status.add_trace(go.Scatter(
            x=df_status["date"],
            y=df_status[y_left_col],
            mode="lines",
            name=y_left_col,
            yaxis="y"
        ))

        # Trace droite (si différente)
        if y_right_col != y_left_col and y_right_col in df_status.columns:
            fig_status.add_trace(go.Scatter(
                x=df_status["date"],
                y=df_status[y_right_col],
                mode="lines",
                name=y_right_col,
                yaxis="y2"
            ))

        # Axes dynamiques + formatage SOC en %
        yaxis_left = dict(title=y_left_col)
        yaxis_right = dict(title=y_right_col, overlaying="y", side="right")

        if y_left_col == "soc":
            yaxis_left.update(range=[0, 100], ticksuffix="%")
        if y_right_col == "soc":
            yaxis_right.update(range=[0, 100], ticksuffix="%")

        fig_status.update_layout(
            title="battery_status_entity",
            yaxis=yaxis_left,
            yaxis2=yaxis_right,
            height=380,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0)
        )
        apply_common_time_axis(fig_status, start_datetime, end_datetime, hide_xticks=False)



        st.plotly_chart(fig_status, use_container_width=True)




# ========== 🧭 Frise temporelle des modes ==========
st.subheader("🧭 Frise temporelle des modes")

# Détecte génération à partir des infos device sélectionné
hw_version = device_info["hardware_version"].values[0] if "hardware_version" in device_info.columns else None
gen = detect_generation(hw_version)

tracks_available = get_mode_cols(gen)
if not tracks_available:
    st.info("Aucune colonne de mode disponible (workingMode/mode).")
else:
    # par défaut : toutes les pistes pertinentes (V1: workingMode ; V2: workingMode + mode)
    selected_tracks = st.multiselect(
        "Pistes à afficher",
        options=tracks_available,
        default=tracks_available,
        help="V1 : workingMode. V2 : workingMode + mode."
    )

    df_modes = load_modes_entity(selected_device, start_str, end_str, selected_tracks)

    if df_modes.empty or not selected_tracks:
        st.info("Aucune donnée de mode sur cette période.")
    else:
        segs_all = []
        for col in selected_tracks:
            labf = label_func_factory(col, gen)
            segs_all.append(_compress_to_segments(df_modes, col, end_datetime, labf))
        segs = pd.concat(segs_all, ignore_index=True) if segs_all else pd.DataFrame()

        if segs.empty:
            st.info("Pas de segments exploitables.")
        else:
            # Libellés lisibles pour les pistes
            name_map = {
                "workingMode": f"Working mode ({gen})",
                "mode": "Mode (v2)"
            }
            segs["track"] = segs["track"].map(name_map).fillna(segs["track"])

            fig_mode = px.timeline(
                segs,
                x_start="start", x_end="end",
                y="track",
                color="label",
                hover_data={"start": "|%Y-%m-%d %H:%M", "end": "|%Y-%m-%d %H:%M", "track": False},
                title="Frise temporelle des modes"
            )

            # ordre stable
            desired = [name_map[c] for c in ["workingMode", "mode"] if c in selected_tracks]
            fig_mode.update_yaxes(categoryorder="array", categoryarray=desired)
            
            fig_mode.update_layout(
                height=160 + 40 * len(desired),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0)
            )

            apply_common_time_axis(fig_mode, start_datetime, end_datetime, hide_xticks=False)

            fig_mode.add_vline(x=repere_datetime, line_width=2, line_dash="dash", line_color="red")
            
            fig_mode.update_yaxes(title_text="")   

            
            st.plotly_chart(fig_mode, use_container_width=True)





# ========== 📍 Graphique séparé des logs sur la même échelle de temps ==========

st.subheader("📍 Fault ou warning sur la période")


@st.cache_data
def load_logs_all(device_id):
    query = f"""
        SELECT date, code, type, message, cleared, cleared_at, cleared_by
        FROM `beem-data-warehouse.airbyte_postgresql.battery_device_log`
        WHERE battery_id = {device_id}
          AND type IN ('fault', 'warning')
    """
    df = client.query(query).to_dataframe()
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_convert(LOCAL_TZ).dt.tz_localize(None)
    return df.sort_values("date", ascending=False)


# Charger les logs si ce n’est pas déjà fait
df_logs_all = load_logs_all(selected_device)





# Appliquer les mêmes filtres temporels + types sélectionnés (on met tout par défaut ici)
df_logs_chart = df_logs_all.copy()
df_logs_chart = df_logs_all[
    (df_logs_all["date"] >= start_datetime) &
    (df_logs_all["date"] <= end_datetime)
].copy()





# Optionnel : filtrer par type (affiche tout par défaut)
log_types_to_show = ["fault", "warning"]  # ou lis depuis type_filter si tu veux réutiliser la sélection utilisateur

df_logs_chart = df_logs_chart[df_logs_chart["type"].isin(log_types_to_show)]

if df_logs_chart.empty:
    st.info("Aucun log 'fault' ou 'warning' sur cette période.")
else:
    fig_logs = go.Figure()
    y_positions = {"fault": 1, "warning": 2}
    colors = {"fault": "red", "warning": "orange"}

    for log_type in df_logs_chart["type"].unique():
        df_sub = df_logs_chart[df_logs_chart["type"] == log_type]
        fig_logs.add_trace(go.Scatter(
            x=df_sub["date"],
            y=[y_positions[log_type]] * len(df_sub),
            mode="markers",
            name=log_type,
            marker=dict(
                symbol="line-ns-open",  
                size=30,            # plus grand (hauteur visuelle de la barre)
                color=colors[log_type],
                line=dict(width=2)  # plus épais (épaisseur du trait)
            ),
            hovertext=df_sub["message"],
            hoverinfo="text+x"
        ))

    fig_logs.update_layout(
        title="Logs 'fault' / 'warning' (barres verticales)",
        yaxis=dict(title="Type", tickvals=[1, 2], ticktext=["fault", "warning"], range=[0.5, 2.5]),
        height=300,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0)
    )
    apply_common_time_axis(fig_logs, start_datetime, end_datetime, hide_xticks=False) 
    # bandes horizontales plus visibles pour les 2 lignes (fault / warning)
    fig_logs.add_hline(y=1, line_width=6, line_color="rgba(255,255,255,0.25)")
    fig_logs.add_hline(y=2, line_width=6, line_color="rgba(255,255,255,0.25)")




    st.plotly_chart(fig_logs, use_container_width=True)



# ========== 🪝 Logs Fault/Warning avec filtres ==========

st.subheader("🪝 Logs ")



df_logs_all = load_logs_all(selected_device)

if df_logs_all.empty:
    st.info("Aucun log de type 'fault' ou 'warning' pour cette batterie.")
else:
    col1, col2 = st.columns(2)

    with col1:
        type_filter = st.multiselect(
         "Type de log",
         options=["fault", "warning"],
          default=["fault", "warning"],
         key="type_filter_main"
        )

    

    df_filtered = df_logs_all.copy()

    if type_filter:
        df_filtered = df_filtered[df_filtered["type"].isin(type_filter)]

   

    # ordre voulu des colonnes avec "code" entre "date" et "type"
    cols = ["date", "code", "type", "message", "cleared", "cleared_at", "cleared_by"]
    df_filtered = df_filtered[cols]

    st.dataframe(df_filtered, use_container_width=True, height=400, hide_index=True)


# ========== 📊 Résumé des logs par type + message (filtres indépendants) ==========
st.subheader("🧮 Total des logs par type et message")

# Création du tableau résumé sans aucun filtre
df_summary_all = df_logs_all.copy()

if not df_summary_all.empty:
    df_summary_all["type_message"] = df_summary_all["type"] + " - " + df_summary_all["message"]
    summary_all = df_summary_all.groupby("type_message").size().reset_index(name="count")
    summary_all = summary_all.sort_values(by="count", ascending=False)

    fig_bar = px.bar(
        summary_all.head(20),  # Limite aux 20 messages les plus fréquents (ajuste si besoin)
        x="count",
        y="type_message",
        orientation="h",
        title="Nombre de logs par type et message",
        labels={"count": "Nombre de logs", "type_message": "Type + message"}
    )

    fig_bar.update_layout(
        yaxis=dict(automargin=True),
        height=700
    )

    st.plotly_chart(fig_bar, use_container_width=True)


else:
    st.info("Aucune donnée à afficher pour ce résumé.")
