import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import os
from google.cloud import bigquery

# Authentification
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\floch\OneDrive\Documents\GCP_key\streamlit_app\beem-data-warehouse-14a923c674a0.json"
client = bigquery.Client()

st.set_page_config(page_title="Zoom Battery", layout="wide")
st.title("🔍 Dashboard Zoom sur une batterie")

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
        AND d.serial_number NOT IN ('021LOLL190154M','021LOLF080008M')
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
st.subheader("🎛️ Filtrage batterie (lié par nom / n° série / device)")

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
with col6:
    mode_clean = device_info["working_mode_code"].astype(str).values[0]
    mode_clean = mode_clean.replace("ampace_v1_", "").replace("ampace_v2_", "")
    st.metric("Mode de fonctionnement", mode_clean)

# ========== 📜 Comparaison Objectif vs Mesuré ==========
@st.cache_data
def load_monthly_data(device_id):
    device_sql = f"'{device_id}'" if isinstance(device_id, str) else str(device_id)

    query_obj = f"""
        SELECT * FROM `beem-data-warehouse.airbyte_postgresql.objective_battery`
        WHERE battery_id = {device_sql}
    """
    query_prod = f"""
        SELECT * FROM `beem-data-warehouse.airbyte_postgresql.monthly_production_battery`
        WHERE battery_id = {device_sql}
    """

    df_obj = client.query(query_obj).to_dataframe()
    df_prod = client.query(query_prod).to_dataframe()

    df_prod["date"] = pd.to_datetime(df_prod["date"])
    df_prod["month"] = df_prod["date"].dt.month
    df_prod["year"] = df_prod["date"].dt.year

    latest_per_month = df_prod.groupby("month")["year"].max().reset_index()
    df_prod = pd.merge(df_prod, latest_per_month, on=["month", "year"], how="inner")

    agg_obj = df_obj.groupby("month")["value"].sum().reset_index().rename(columns={"value": "objective"})
    agg_prod = df_prod.groupby("month")["watt_hours"].sum().reset_index().rename(columns={"watt_hours": "measured"})

    df_merge = pd.merge(agg_obj, agg_prod, on="month", how="outer").sort_values("month").fillna(0)
    df_melted = df_merge.melt(id_vars="month", var_name="Source", value_name="Wh")

    return df_melted, df_merge

df_comparaison, df_pivot = load_monthly_data(selected_device)

# Affichage du graphe Objectif vs Mesuré
df_comparaison["month"] = df_comparaison["month"].astype(str)

fig_comp = px.bar(
    df_comparaison,
    x="month",
    y="Wh",
    color="Source",
    barmode="group",
    title="Comparaison mensuelle : Objectif vs Production réelle",
    labels={"month": "Mois", "Wh": "Énergie (Wh)"},
    category_orders={"month": [str(i) for i in range(1, 13)]}
)
st.plotly_chart(fig_comp, use_container_width=True)

# Affichage du tableau de taux de réalisation
st.subheader("📋 Taux de réalisation par mois (%)")

df_pivot["Taux de réalisation (%)"] = (
    (df_pivot["measured"] / df_pivot["objective"]) * 100
).round(1).replace([float("inf"), -float("inf")], 0).fillna(0)

st.dataframe(
    df_pivot[["month", "objective", "measured", "Taux de réalisation (%)"]],
    use_container_width=True,
    height=400
)

import plotly.graph_objects as go

# ========== 🗓️ Filtres temporels ==========

st.subheader("⏱️ Plage de temps pour les courbes")

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Date de début", datetime(2025, 4, 1), key="start_main")
with col2:
    end_date = st.date_input("Date de fin", datetime(2025, 4, 30), key="end_main")


col3, col4 = st.columns(2)
with col3:
    start_time = st.time_input("Heure de début", datetime.min.time())
with col4:
    end_time = st.time_input("Heure de fin", datetime.max.time())

start_datetime = datetime.combine(start_date, start_time)
end_datetime = datetime.combine(end_date, end_time)

start_str = start_datetime.isoformat()
end_str = end_datetime.isoformat()

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
    query = f"""
        SELECT *
        FROM `beem-data-warehouse.mongo_beem.{table_name}`
        WHERE device_id = {device_id}
          AND DATETIME(date) BETWEEN DATETIME('{start_dt}') AND DATETIME('{end_dt}')
    """
    df = client.query(query).to_dataframe()
    df["date"] = pd.to_datetime(df["date"])
    return df

st.subheader("📊 Visualisation combinée des mesures")

selected_sources = st.multiselect(
    "Sélectionne les courbes à afficher :",
    options=list(sources.keys()),
    format_func=lambda x: sources[x]["title"],
    default=list(sources.keys())  # ou [] si tu veux les cacher par défaut
)

fig = go.Figure()

for table_name in selected_sources:
    meta = sources[table_name]
    df = load_data(table_name, selected_device, start_str, end_str)

    if df.empty:
        st.warning(f"Aucune donnée pour : {meta['title']}")
        continue

    if meta["agg"] and "device_sub_id" in df.columns:
        df = df.groupby(["date", "device_id"], as_index=False)["value"].sum()

    df = df.sort_values("date")
    fig.add_trace(go.Scatter(
        x=df["date"],
        y=df["value"],
        mode="lines",
        name=meta["title"]
    ))

fig.update_layout(
    title="Courbes combinées des mesures",
    xaxis_title="Date",
    yaxis_title="Wh",
    legend_title="Type de mesure",
    height=600,
    xaxis=dict(
        rangeselector=dict(
            buttons=list([
                dict(count=1, label="1j", step="day", stepmode="backward"),
                dict(count=7, label="1s", step="day", stepmode="backward"),
                dict(count=1, label="1m", step="month", stepmode="backward"),
                dict(step="all", label="Tout")
            ])
        ),
        rangeslider=dict(visible=False),
        type="date"
    )
)

st.plotly_chart(fig, use_container_width=True)

# ========== 🔍 Valeurs proches d'une date/heure sélectionnée ==========

st.subheader("📍 Obtenir les valeurs les plus proches d'un moment donné")

col1, col2 = st.columns(2)
with col1:
    search_date = st.date_input("📅 Date cible", datetime(2025, 4, 15), key="search_date")
with col2:
    from datetime import timedelta

    search_time = st.time_input(
        "🕒 Heure cible",
        datetime(2025, 4, 15, 12, 0).time(),
        key="search_time",
        step=timedelta(minutes=5)
    )


from datetime import timezone
search_datetime = datetime.combine(search_date, search_time).replace(tzinfo=timezone.utc)


# Fusionner toutes les sources sélectionnées
closest_rows = []

for table_name in selected_sources:
    meta = sources[table_name]
    df = load_data(table_name, selected_device, start_str, end_str)

    if df.empty:
        continue

    if meta["agg"] and "device_sub_id" in df.columns:
        df = df.groupby(["date", "device_id"], as_index=False)["value"].sum()

    df = df.sort_values("date")
    df["time_diff"] = (df["date"] - search_datetime).abs()
    closest = df.loc[df["time_diff"].idxmin()]
    closest_rows.append({
        "Type de mesure": meta["title"],
        "Date/heure la plus proche": closest["date"],
        "Valeur": closest["value"]
    })

if closest_rows:
    df_closest = pd.DataFrame(closest_rows)
    st.dataframe(df_closest, use_container_width=True)
else:
    st.info("Aucune donnée disponible pour cette période.")


# ========== 🪝 Logs Fault/Warning avec filtres ==========

st.subheader("🪝 Logs de type 'fault' ou 'warning'")

@st.cache_data
def load_logs_all(device_id):
    query = f"""
        SELECT date, type, message, cleared, cleared_at, cleared_by
        FROM `beem-data-warehouse.airbyte_postgresql.battery_device_log`
        WHERE battery_id = {device_id}
          AND type IN ('fault', 'warning')
    """
    df = client.query(query).to_dataframe()
    df["date"] = pd.to_datetime(df["date"], utc=True)
    return df.sort_values("date", ascending=False)

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

    with col2:
        min_date = df_logs_all["date"].min().date()
        max_date = df_logs_all["date"].max().date()
        date_range = st.date_input("Plage de dates", [min_date, max_date])

    df_filtered = df_logs_all.copy()

    if type_filter:
        df_filtered = df_filtered[df_filtered["type"].isin(type_filter)]

    if len(date_range) == 2:
        start = pd.to_datetime(date_range[0]).tz_localize("UTC")
        end = pd.to_datetime(date_range[1]).tz_localize("UTC")
        df_filtered = df_filtered[df_filtered["date"].between(start, end)]

    st.dataframe(df_filtered, use_container_width=True, height=400)

# ========== 📊 Résumé des logs par type + message (filtres indépendants) ==========
st.subheader("🧮 Total des logs par type et message")

# Filtres spécifiques à ce tableau
col1, col2 = st.columns(2)
with col1:
    type_filter_summary = st.multiselect(
      "Type de log",
       options=["fault", "warning"],
       default=["fault", "warning"],
       key="type_filter_summary"
    )

with col2:
    min_date_summary = df_logs_all["date"].min().date()
    max_date_summary = df_logs_all["date"].max().date()
    date_range_summary = st.date_input(
    "Plage de dates", [min_date_summary, max_date_summary], key="date_range_summary"
    )


# Application des filtres spécifiques
df_summary_filtered = df_logs_all.copy()

if type_filter_summary:
    df_summary_filtered = df_summary_filtered[df_summary_filtered["type"].isin(type_filter_summary)]

if len(date_range_summary) == 2:
    start_summary = pd.to_datetime(date_range_summary[0]).tz_localize("UTC")
    end_summary = pd.to_datetime(date_range_summary[1]).tz_localize("UTC")
    df_summary_filtered = df_summary_filtered[
        df_summary_filtered["date"].between(start_summary, end_summary)
    ]

# Comptage des combinaisons type + message
if not df_summary_filtered.empty:
    df_summary_filtered["type_message"] = df_summary_filtered["type"] + " - " + df_summary_filtered["message"]
    summary = df_summary_filtered.groupby("type_message").size().reset_index(name="count")
    summary = summary.sort_values(by="count", ascending=False)

    st.dataframe(summary, use_container_width=True)
else:
    st.info("Aucune donnée à afficher pour ce résumé.")