import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import os
from google.cloud import bigquery
import plotly.graph_objects as go

# Authentification
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\\Users\\floch\\OneDrive\\Documents\\GCP_key\\streamlit_app\\beem-data-warehouse-14a923c674a0.json"
# Authentification
client = bigquery.Client()  # ← utilisé pour `mongo_beem` (région US par défaut)
client_eu = bigquery.Client(location="EU")  # ← pour `mongodb`


st.set_page_config(page_title="BART - performance", layout="wide")
st.title("📊 Performance battery")

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
        sc.nb = 1
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

@st.cache_data
def load_daily_energy_data():
    query_before = """
      -- Requête avant mai 2025 (mongo_beem - US)
      WITH
        conso AS (
          SELECT device_id, DATE(date) AS date, SUM(value) AS conso
          FROM beem-data-warehouse.mongo_beem.battery_active_energy_measure
          GROUP BY device_id, date
        ),
        injection AS (
          SELECT device_id, DATE(date) AS date, SUM(value) AS injection
          FROM beem-data-warehouse.mongo_beem.battery_active_returned_energy_meter_measure
          GROUP BY device_id, date
        ),
        prod AS (
          SELECT device_id, DATE(date) AS date, SUM(value) AS prod
          FROM beem-data-warehouse.mongo_beem.battery_active_returned_energy_measure
          GROUP BY device_id, date
        ),
        energy_charged AS (
          SELECT device_id, DATE(date) AS date, SUM(value) AS energy_charged
          FROM beem-data-warehouse.mongo_beem.battery_energy_charged_measure
          GROUP BY device_id, date
        ),
        energy_discharged AS (
          SELECT device_id, DATE(date) AS date, SUM(value) AS energy_discharged
          FROM beem-data-warehouse.mongo_beem.battery_energy_discharged_measure
          GROUP BY device_id, date
        )
      SELECT
        COALESCE(c.device_id, i.device_id, p.device_id, ec.device_id, ed.device_id) AS device_id,
        COALESCE(c.date, i.date, p.date, ec.date, ed.date) AS date,
        c.conso,
        i.injection,
        p.prod,
        ec.energy_charged,
        ed.energy_discharged
      FROM conso c
      FULL OUTER JOIN injection i ON c.device_id = i.device_id AND c.date = i.date
      FULL OUTER JOIN prod p ON COALESCE(c.device_id, i.device_id) = p.device_id AND COALESCE(c.date, i.date) = p.date
      FULL OUTER JOIN energy_charged ec ON COALESCE(c.device_id, i.device_id, p.device_id) = ec.device_id AND COALESCE(c.date, i.date, p.date) = ec.date
      FULL OUTER JOIN energy_discharged ed ON COALESCE(c.device_id, i.device_id, p.device_id, ec.device_id) = ed.device_id AND COALESCE(c.date, i.date, p.date, ec.date) = ed.date
      WHERE c.date < "2025-05-01"
      ORDER BY device_id, date
    """

    query_after = """
      -- Requête après mai 2025 (mongodb - EU)
      WITH
        conso AS (
          SELECT deviceId, DATE(date) AS date, SUM(value) AS conso
          FROM beem-data-warehouse.mongodb.battery_active_energy_measure
          GROUP BY deviceId, date
        ),
        injection AS (
          SELECT deviceId, DATE(date) AS date, SUM(value) AS injection
          FROM beem-data-warehouse.mongodb.battery_active_returned_energy_meter_measure
          GROUP BY deviceId, date
        ),
        prod AS (
          SELECT deviceId, DATE(date) AS date, SUM(value) AS prod
          FROM beem-data-warehouse.mongodb.battery_active_returned_energy_measure
          GROUP BY deviceId, date
        ),
        energy_charged AS (
          SELECT deviceId, DATE(date) AS date, SUM(value) AS energy_charged
          FROM beem-data-warehouse.mongodb.battery_energy_charged_measure
          GROUP BY deviceId, date
        ),
        energy_discharged AS (
          SELECT deviceId, DATE(date) AS date, SUM(value) AS energy_discharged
          FROM beem-data-warehouse.mongodb.battery_energy_discharged_measure
          GROUP BY deviceId, date
        )
      SELECT
        COALESCE(c.deviceId, i.deviceId, p.deviceId, ec.deviceId, ed.deviceId) AS device_id,
        COALESCE(c.date, i.date, p.date, ec.date, ed.date) AS date,
        c.conso,
        i.injection,
        p.prod,
        ec.energy_charged,
        ed.energy_discharged
      FROM conso c
      FULL OUTER JOIN injection i ON c.deviceId = i.deviceId AND c.date = i.date
      FULL OUTER JOIN prod p ON COALESCE(c.deviceId, i.deviceId) = p.deviceId AND COALESCE(c.date, i.date) = p.date
      FULL OUTER JOIN energy_charged ec ON COALESCE(c.deviceId, i.deviceId, p.deviceId) = ec.deviceId AND COALESCE(c.date, i.date, p.date) = ec.date
      FULL OUTER JOIN energy_discharged ed ON COALESCE(c.deviceId, i.deviceId, p.deviceId, ec.deviceId) = ed.deviceId AND COALESCE(c.date, i.date, p.date, ec.date) = ed.date
      WHERE c.date >= "2025-05-01"
      ORDER BY device_id, date
    """

    df_before_may = client.query(query_before).to_dataframe()
    df_after_may = client_eu.query(query_after).to_dataframe()

    return pd.concat([df_before_may, df_after_may], ignore_index=True).sort_values(["device_id", "date"])




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

# Dictionnaire de conversion numéro → nom du mois
mois_noms = {
    1: "janvier", 2: "février", 3: "mars", 4: "avril",
    5: "mai", 6: "juin", 7: "juillet", 8: "août",
    9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre"
}

# Ajouter une colonne avec le nom du mois
df_comparaison["month_name"] = df_comparaison["month"].astype(int).map(mois_noms)
df_pivot["month_name"] = df_pivot["month"].astype(int).map(mois_noms)

# Calcul du taux de réalisation (%)
df_pivot["Taux de réalisation (%)"] = df_pivot.apply(
    lambda row: round((row["measured"] / row["objective"]) * 100, 1)
    if pd.notnull(row["measured"]) and pd.notnull(row["objective"]) and row["objective"] != 0
    else 0,
    axis=1
)


# Affichage du graphe Objectif vs Mesuré
df_comparaison["month"] = df_comparaison["month"].astype(str)

fig_comp = px.bar(
    df_comparaison,
    x="month_name",
    y="Wh",
    color="Source",
    barmode="group",
    title="Comparaison mensuelle : Objectif vs Production réelle",
    labels={"month": "Mois", "Wh": "Énergie (Wh)"},
    category_orders={"month": [str(i) for i in range(1, 13)]}
)
st.plotly_chart(fig_comp, use_container_width=True)

df_daily = load_daily_energy_data()
df_device = df_daily[df_daily["device_id"] == selected_device]

# ========== 📆 Sélecteur de période ==========
st.subheader("📊 Visualisation mensuelle de l'énergie")

df_device["date"] = pd.to_datetime(df_device["date"])
df_device["month"] = df_device["date"].dt.month
df_device["year"] = df_device["date"].dt.year

# Dictionnaire mois lisible
mois_noms = {
    1: "janvier", 2: "février", 3: "mars", 4: "avril",
    5: "mai", 6: "juin", 7: "juillet", 8: "août",
    9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre"
}
df_device["month_name"] = df_device["month"].map(mois_noms)

# Filtres année + mois
available_years = sorted(df_device["year"].unique())
selected_year = st.selectbox("Année", available_years, index=len(available_years) - 1)



# ========== 📊 Visualisation mensuelle agrégée sur l'année sélectionnée ==========
df_mensuel = (
    df_device[df_device["year"] == selected_year]
    .groupby("month")
    .sum(numeric_only=True)
    .reset_index()
)

df_mensuel["month_name"] = df_mensuel["month"].map(mois_noms)

# Forcer les colonnes à être numériques
for col in ["prod", "injection", "conso"]:
    df_mensuel[col] = pd.to_numeric(df_mensuel[col], errors="coerce")

# Création d'une figure vide
fig_mensuel = go.Figure()

# Barre Production (groupe 1)
fig_mensuel.add_trace(go.Bar(
    x=df_mensuel["month_name"],
    y=df_mensuel["prod"],
    name="Production",
    marker_color="#F4A6B9",  # Rose clair
    offsetgroup="1",
))

# Barre Conso (groupe 2, empilé)
fig_mensuel.add_trace(go.Bar(
    x=df_mensuel["month_name"],
    y=df_mensuel["conso"],
    name="Consommation",
    marker_color="#8ECFF3",  # Bleu clair
    offsetgroup="2",
    base=0
))

# Barre Injection (même groupe, empilé au-dessus de la conso)
fig_mensuel.add_trace(go.Bar(
    x=df_mensuel["month_name"],
    y=df_mensuel["injection"],
    name="Injection",
    marker_color="#1F77B4",  # Bleu foncé
    offsetgroup="2",
    base=df_mensuel["conso"]  # Injection au-dessus de conso
))

# Mise en forme
fig_mensuel.update_layout(
    title=f"Énergie - Agrégation mensuelle ({selected_year})",
    xaxis_title="Mois",
    yaxis_title="Wh",
    barmode="group",
    bargap=0.2,
)

# Affichage
st.plotly_chart(fig_mensuel, use_container_width=True)


available_months = df_device[df_device["year"] == selected_year]["month"].sort_values().unique()
month_options = [mois_noms[m] for m in available_months]
selected_month_name = st.selectbox("Mois", month_options)
selected_month = {v: k for k, v in mois_noms.items()}[selected_month_name]


# ========== 📊 Affichage du graphe ==========
df_filtered = df_device[
    (df_device["year"] == selected_year) & (df_device["month"] == selected_month)
]

if df_filtered.empty:
    st.warning("Aucune donnée disponible pour cette période.")
else:
    df_grouped = df_filtered.groupby(df_filtered["date"].dt.day).sum(numeric_only=True).reset_index()
    df_grouped.rename(columns={"date": "Jour"}, inplace=True)

    fig = go.Figure()

# Production seule (barre 1)
fig.add_trace(go.Bar(
    x=df_grouped["Jour"],
    y=df_grouped["prod"],
    name="Production",
    marker_color="#F4A6B9",  # Rose clair
    offsetgroup="1",
))

# Consommation (barre 2 empilée - base = 0)
fig.add_trace(go.Bar(
    x=df_grouped["Jour"],
    y=df_grouped["conso"],
    name="Consommation",
    marker_color="#8ECFF3",  # Bleu clair
    offsetgroup="2",
    base=0,
))

# Injection (barre 2 empilée - base = conso)
fig.add_trace(go.Bar(
    x=df_grouped["Jour"],
    y=df_grouped["injection"],
    name="Injection",
    marker_color="#1F77B4",  # Bleu foncé
    offsetgroup="2",
    base=df_grouped["conso"]
))

fig.update_layout(
    barmode="group",
    title=f"Énergie - Agrégation quotidienne ({selected_month_name} {selected_year})",
    xaxis_title="Jour du mois",
    yaxis_title="Wh",
    bargap=0.2,
)

st.plotly_chart(fig, use_container_width=True)


# ========== 📋 Nouveau tableau final : taux recalculés proprement ==========

# Recalcul des taux autonomie / autoconsommation depuis les données journalières
df_energy_mensuel = (
    df_device
    .groupby(["year", "month"])
    .agg({
        "prod": "sum",
        "conso": "sum",
        "injection": "sum"
    })
    .reset_index()
)
date_range = pd.date_range(start=df_device["date"].min().replace(day=1), end=datetime.today(), freq="MS")
complete_months = pd.DataFrame({
    "year": date_range.year,
    "month": date_range.month
})

df_energy_mensuel = pd.merge(
    complete_months,
    df_energy_mensuel,
    on=["year", "month"],
    how="left"
)



# Création de la table complète de tous les mois, sur les années utiles
min_date = df_device["date"].min().replace(day=1)
max_date = df_device["date"].max().replace(day=1)
date_range = pd.date_range(start=min_date, end=max_date, freq="MS")
complete_months = pd.DataFrame({
    "year": date_range.year,
    "month": date_range.month
})

# Fusion complète avec les données réelles
df_energy_mensuel = pd.merge(
    complete_months,
    df_energy_mensuel,
    on=["year", "month"],
    how="left"
)

# Ajout des noms de mois
df_energy_mensuel["month_name"] = df_energy_mensuel["month"].map(mois_noms)

# Calculs des taux
df_energy_mensuel["conso_maison"] = df_energy_mensuel["prod"] + df_energy_mensuel["conso"] - df_energy_mensuel["injection"]

df_energy_mensuel["taux_autonomie (%)"] = df_energy_mensuel.apply(
    lambda row: round(
        max(0, min(100, ((row["prod"] - row["injection"]) / row["conso_maison"]) * 100)),
        1
    ) if pd.notnull(row["conso_maison"]) and row["conso_maison"] > 0 and pd.notnull(row["prod"]) and pd.notnull(row["injection"])
    else None,
    axis=1
)


df_energy_mensuel["taux_autoconsommation (%)"] = df_energy_mensuel.apply(
    lambda row: round(
        max(0, min(100, ((row["prod"] - row["injection"]) / row["prod"]) * 100)),
        1
    ) if pd.notnull(row["prod"]) and row["prod"] > 0 and pd.notnull(row["injection"])
    else None,
    axis=1
)


# Ajout des noms de mois
df_energy_mensuel["month_name"] = df_energy_mensuel["month"].map(mois_noms)

# Fusion avec taux de réalisation
df_final = pd.merge(
    df_energy_mensuel[["year", "month", "month_name", "taux_autonomie (%)", "taux_autoconsommation (%)"]],
    df_pivot[["month", "Taux de réalisation (%)"]],
    on="month",
    how="left"
)


# Affichage
st.subheader("📋 Taux mensuels : Réalisation, Autonomie, Autoconsommation")
df_final_sorted = df_final.sort_values(["year", "month"])

df_final_sorted["Mois"] = df_final_sorted["month_name"] + " " + df_final_sorted["year"].astype(str)

st.dataframe(
    df_final_sorted[[  
        "Mois",  
        "Taux de réalisation (%)",  
        "taux_autonomie (%)",  
        "taux_autoconsommation (%)"  
    ]],
    use_container_width=True,
    height=500
)
mois_selection = st.selectbox("🗓️ Choisir un mois :", df_final_sorted["Mois"])

row = df_final_sorted[df_final_sorted["Mois"] == mois_selection].iloc[0]
col1, col2, col3 = st.columns(3)
col1.metric("🎯 Réalisation", f"{row['Taux de réalisation (%)']} %")
col2.metric("⚡ Autonomie", f"{row['taux_autonomie (%)']} %")
col3.metric("🏠 Autoconsommation", f"{row['taux_autoconsommation (%)']} %")

cols_taux = ["Taux de réalisation (%)", "taux_autonomie (%)", "taux_autoconsommation (%)"]
df_final_sorted[cols_taux] = df_final_sorted[cols_taux].apply(pd.to_numeric, errors="coerce")

fig_line = px.line(
    df_final_sorted,
    x="Mois",
    y=["Taux de réalisation (%)", "taux_autonomie (%)", "taux_autoconsommation (%)"],
    markers=True,
    title="📈 Taux mensuels - Évolution",
    labels={"value": "%", "variable": "Indicateur"}
)
st.plotly_chart(fig_line, use_container_width=True)

