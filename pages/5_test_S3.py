import streamlit as st 
from google.cloud import storage
import os
import json
from datetime import datetime, time, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Configuration GCP
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\floch\OneDrive\Documents\GCP_key\streamlit_app\beem-data-warehouse-14a923c674a0.json"
BUCKET_NAME = "beem-backend-battery-warranty"
INDEX_BUCKET_NAME = "beem-battery-indexes"  # nouveau

#----- titre de la page
st.title("📈 debug data")

#récupération serial number
from google.cloud import bigquery
@st.cache_data
def get_serial_numbers():
    client = bigquery.Client()
    query = """
        SELECT d.serial_number
        FROM `beem-data-warehouse.airbyte_postgresql.battery_device` AS d
        LEFT JOIN `beem-data-warehouse.airbyte_postgresql.battery_live_data` AS ld 
            ON ld.battery_id = d.id
        LEFT JOIN `beem-data-warehouse.airbyte_postgresql.house` AS h 
            ON d.house_id = h.id
        WHERE d.deleted_at IS NULL
          AND d.replaced_by_id IS NULL
          AND d.warranty_status = 'activated'
          AND d.serial_number NOT IN ('021LOLL190154M', '021LOLF080008M')
    """
    query_job = client.query(query)
    results = query_job.result()
    serials = [row.serial_number for row in results]
    return sorted(serials)


# --- Chargement des fichiers JSON depuis GCS ---
@st.cache_data
def load_json_data(serial_number, selected_date, start_time, end_time):
    client = storage.Client()
    data_bucket = client.bucket(BUCKET_NAME)
    index_bucket = client.bucket(INDEX_BUCKET_NAME)

    date_only = selected_date
    records = []
    filtered_files = []

    def try_arborescence():
        arbo_files = []
        prefix = f"{serial_number}/{selected_date.year}/{selected_date.month}/{selected_date.day}/"
        blobs = client.list_blobs(BUCKET_NAME, prefix=prefix)
        for blob in blobs:
            filename = os.path.basename(blob.name)
            try:
                parts = filename.split('_')
                timestamp_raw = parts[1].split('.')[0]         # "2025-07-23T13-58-43-000"
                timestamp_str = timestamp_raw[:19]             # "2025-07-23T13-58-43"
                dt = datetime.strptime(timestamp_str, "%Y-%m-%dT%H-%M-%S")
                if dt.date() == date_only and start_time <= dt.time() <= end_time:
                    arbo_files.append((dt, blob.name))
            except Exception as e:
                st.warning(f"⚠️ Erreur parsing nom de fichier {filename} : {e}")
        return arbo_files

    def try_index():
        index_files = []
        index_blob_path = f"{serial_number}_index.json"
        index_blob = index_bucket.blob(index_blob_path)
        try:
            content = index_blob.download_as_text()
            index = json.loads(content)
            for entry in index:
                try:
                    dt = datetime.strptime(entry["date"], "%Y-%m-%d %H:%M:%S")
                    if dt.date() == date_only and start_time <= dt.time() <= end_time:
                        index_files.append((dt, entry["path"]))
                except Exception as e:
                    print(f"Erreur parsing date dans {entry.get('path', '?')} : {e}")
        except Exception as e:
            st.error(f"❌ Erreur de lecture de l’index JSON `{index_blob_path}` : {e}")
        return index_files

    # Logique principale selon la date
    if date_only < datetime(2025, 7, 21).date():
        filtered_files = try_index()
    elif date_only > datetime(2025, 7, 23).date():
        filtered_files = try_arborescence()
    else:  # dates 21, 22, 23 → arbo + fallback index si vide
        filtered_files = try_arborescence()
        if not filtered_files:
            st.info("ℹ️ Aucune donnée trouvée dans l’arborescence, tentative via l’index…")
            filtered_files = try_index()

    st.info(f"📂 {len(filtered_files)} fichiers trouvés pour {selected_date} entre {start_time} et {end_time}")

    # Téléchargement des fichiers
    for dt, path in filtered_files:
        try:
            blob = data_bucket.blob(path)
            content = blob.download_as_text()
            parsed = json.loads(content)
            records.append({
                "date": dt,
                "values": parsed["data"]
            })
        except Exception as e:
            st.error(f"❌ Erreur de lecture {path} : {e}")

    return records



# --- Création du DataFrame ---
def records_to_dataframe(records):
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    values_expanded = pd.DataFrame(df['values'].to_list())
    df = pd.concat([df['date'], values_expanded], axis=1)

    # Liste des 350 noms d’index (avec gestion des doublons déjà faite)
    custom_index_names_raw = [
        "DevProtocol", "Master_Version", "YearMonth", "DateTime", "MinutesSeconds", "Battery_Status",
        "Battery_Volt", "Battery_Curr", "Input_Frequency", "Input_Volt", "Input_Appa.P A", "Input_Acti.P",
        "Input_ReActi.P", "Inverter_Volt", "Inverter_Curr", "Inverter_Acti.P", "Drm0Sts", "WetPortSta",
        "PV_Power", "Bus_Volt", "SysDailyGenerationKwh_L", "SysDailyGenerationKwh_H",
        "SysTotalGenerationKwh_L", "SysTotalGenerationKwh_H", "Load_Volt", "Load_Curr", "Load_Acti.P",
        "Load_Appa.P", "Load_Percentage", "EnergyFlow_Line 1-8", "EnergyFlow_Line 9-16", "MonitorVersion",
        "Reserved", "SOC", "BUS _Volt", "BUS_Curr", "Reserved_1", "Reserved_2", "CT_PowerByDC",
        "BUS_Power", "SystemError", "BatteryDailyDischargeKwh_L", "BatteryDailyDischargeKwh_H",
        "BatteryTotalDischargeKwh_L", "BatteryTotalDischargeKwh_H", "DC-AC_StatusMode", "DC-AC_ERR_H",
        "DC-AC_ERR_L", "Reserved_3", "Reserved_4", "AC_Version", "AC_Temp1", "AC_Temp2", "AC_InternalVer",
        "Grid_VoltAVG(V)", "Grid_CurrAVG(A)", "Grid_Frequency(Hz)", "Grid_ActiPw(W)", "Grid_Pw(W)",
        "PowerFactor", "Inv_VoltAVG(V)", "Inv_CurrAVG(A)", "Inv_Pw(W)", "Load_Volt(V)", "Load_Pw(W)",
        "PowerSetting", "AC_CtrlPow", "DC-AC_STATE", "DC-AC_ERR_H_1", "DC-AC_ERR_L_1", "DC-AC_WARN_H",
        "DC-AC_WARN_L", "Reserved_5", "Reserved_6", "UndercurrentStatus", "FullChargeStatus", "AC_User9",
        "Inv_Ileak", "BatteryPower", "MonitorBoard", "DC_FwVersion", "CT1_Power", "AC_User19", "PV1_Power",
        "PV2_Power", "PV3_Power", "WindTurbine_Pw", "PV1_Volt", "PV1_Curr", "PV2_Volt", "PV2_Curr",
        "PV3_Volt", "PV3_Curr", "WindTurbine_Volt", "WindTurbine_Curr", "Reserved_7",
        "BMS_ChargeLimitVolt", "BMS_MaxChargeCurr", "BMS_MaxDischargeCurr", "BMS_DischargeCutoffVolt",
        "BMS_Volt", "BMS_Curr", "BMS_Temp", "BMS_SOC", "BMS_SOH", "BMS_Status", "BMS_ERR_H", "BMS_ERR_L",
        "BMS_WARN_H", "BMS_WARN_L", "BMS_Version", "BMS_Capacity", "BatteriesCount", "CellsCount",
        "RACK_Volt", "RACK_Curr", "RACK_SOC", "RACK_SOH", "RACK_MaxCellVolt", "RACK_MaxCellVoltNum",
        "RACK_MinCellVolt", "RACK_MinCellVoltNum", "RACK_MaxCellTemp", "RACK_MaxCellTempNum",
        "RACK_MinCellTemp", "RACK_MinCellTempNum", "RACK_HwVersion", "RACK_FwVersion", "RACK_ERR_H",
        "RACK_WARN", "RACK_Sta", "RACK_ERR_L", "RACK_SN_High", "RACK_SN_Mid", "RACK_SN_Low", "RACK_SN_H",
        "RACK_SN_L", "RACK_CycleCount", "RACK_RemainCapacity", "RACK_FullChargeCapacity", "RACK_PlugStatus",
        "Reserved_8", "Reserved_9", "Reserved_10", "Reserved_11", "Reserved_12", "Reserved_13", "Reserved_14",
        "Reserved_15", "Reserved_16", "DSP1_REG38", "DSP1_REG39", "DSP1_REG40", "DSP1_REG41", "DSP1_REG42",
        "DSP1_REG43", "DSP1_REG44", "DSP1_REG45", "DSP1_REG46", "DSP1_REG47", "DSP1_REG48", "DSP1_REG49",
        "DSP1_REG50", "DSP1_REG51", "DSP1_REG52", "DSP1_REG53", "DSP1_REG54", "DSP1_REG55", "DSP1_REG56",
        "DSP1_REG57", "DSP1_REG58", "DSP1_REG59", "DSP2_REG00", "DSP2_REG01", "DSP2_REG02", "DSP2_REG03",
        "DSP2_REG04", "DSP2_REG05", "DSP2_REG06", "DSP2_REG07", "DSP2_REG08", "DSP2_REG09", "DSP2_REG10",
        "DSP2_REG11", "DSP2_REG12", "DSP2_REG13", "DSP2_REG14", "DSP2_REG15", "DSP2_REG16", "DSP2_REG17",
        "DSP2_REG18", "DSP2_REG19", "DSP2_REG20", "DSP2_REG21", "DSP2_REG22", "DSP2_REG23", "DSP2_REG24",
        "DSP2_REG25", "DSP2_REG26", "DSP2_REG27", "BMU1_MoudleVolt", "BMU1_CellNum", "BMU1_MaxCellVolt",
        "BMU1_MinCellVolt", "BMU1_CellTempNum", "BMU1_HwVersion", "BMU1_FwVersion", "BMU1_SN_H", "BMU1_SN_L",
        "BMU1_BalancingTarget", "BMU1_Reserved", "BMU2_MoudleVolt", "BMU2_CellNum", "BMU2_MaxCellVolt",
        "BMU2_MinCellVolt", "BMU2_CellTempNum", "BMU2_HwVersion", "BMU2_FwVersion", "BMU2_SN_H",
        "BMU2_SN_L", "BMU2_BalancingTarget", "BMU2_Reserved", "BMU3_MoudleVolt", "BMU3_CellNum",
        "BMU3_MaxCellVolt", "BMU3_MinCellVolt", "BMU3_CellTempNum", "BMU3_HwVersion", "BMU3_FwVersion",
        "BMU3_SN_H", "BMU3_SN_L", "BMU3_BalancingTarget", "BMU3_Reserved", "BMU4_MoudleVolt",
        "BMU4_CellNum", "BMU4_MaxCellVolt", "BMU4_MinCellVolt", "BMU4_CellTempNum", "BMU4_HwVersion",
        "BMU4_FwVersion", "BMU4_SN_H", "BMU4_SN_L", "BMU4_BalancingTarget", "BMU4_Reserved",
        "BMU5_MoudleVolt", "BMU5_CellNum", "BMU5_MaxCellVolt", "BMU5_MinCellVolt", "BMU5_CellTempNum",
        "BMU5_HwVersion", "BMU5_FwVersion", "BMU5_SN_H", "BMU5_SN_L", "BMU5_BalancingTarget",
        "BMU5_Reserved", "BMU6_MoudleVolt", "BMU6_CellNum", "BMU6_MaxCellVolt", "BMU6_MinCellVolt",
        "BMU6_CellTempNum", "BMU6_HwVersion", "BMU6_FwVersion", "BMU6_SN_H", "BMU6_SN_L",
        "BMU6_BalancingTarget", "BMU6_Reserved", "BMU7_MoudleVolt", "BMU7_CellNum", "BMU7_MaxCellVolt",
        "BMU7_MinCellVolt", "BMU7_CellTempNum", "BMU7_HwVersion", "BMU7_FwVersion", "BMU7_SN_H",
        "BMU7_SN_L", "BMU7_BalancingTarget", "BMU7_Reserved", "BMU8_MoudleVolt", "BMU8_CellNum",
        "BMU8_MaxCellVolt", "BMU8_MinCellVolt", "BMU8_CellTempNum", "BMU8_HwVersion", "BMU8_FwVersion",
        "BMU8_SN_H", "BMU8_SN_L", "BMU8_BalancingTarget", "BMU8_Reserved", "Reserved_17", "Reserved_18",
        "Reserved_19", "Reserved_20", "Reserved_21", "Reserved_22", "Reserved_23", "Reserved_24",
        "Reserved_25", "Reserved_26", "Reserved_27", "Reserved_28", "Reserved_29", "Reserved_30",
        "Reserved_31", "Reserved_32", "Reserved_33", "Reserved_34", "Reserved_35", "Reserved_36",
        "Meter1_CombineKwH_H", "Meter1_CombineKwH_L", "Meter1_PositiveKwH_H", "Meter1_PositiveKwH_L",
        "Meter1_NagativeKwH_H", "Meter1_NagativeKwH_L", "Meter1_Volt_H", "Meter1_Volt_L", "Meter1_Curr_H",
        "Meter1_Curr_L", "Meter1_ActivePower_H", "Meter1_ActivePower_L", "Meter1_PowerFactor_H",
        "Meter1_PowerFactor_L", "Meter1_Frequency_H", "Meter1_Frequency_L", "Meter2_CombineKwH_H",
        "Meter2_CombineKwH_L", "Meter2_PositiveKwH_H", "Meter2_PositiveKwH_L", "Meter2_NagativeKwH_H",
        "Meter2_NagativeKwH_L", "Meter2_Volt_H", "Meter2_Volt_L", "Meter2_Curr_H", "Meter2_Curr_L",
        "Meter2_ActivePower_H", "Meter2_ActivePower_L", "Meter2_PowerFactor_H", "Meter2_PowerFactor_L",
        "Meter2_Frequency_H", "Meter2_Frequency_L", "Reserved_37", "Reserved_38", "Reserved_39",
        "Reserved_40", "Reserved_41", "Reserved_42", "Reserved_43", "Reserved_44", "Reserved_45",
        "Reserved_46"
    ]

    # Vérification et renommage si le DataFrame a bien 351 colonnes (date + 350 données)
    if len(df.columns) == 351:
        df.columns = ["date"] + custom_index_names_raw
        st.success("✅ Noms d’index personnalisés appliqués.")
    else:
        st.warning(f"⚠️ Le fichier ne contient pas 350 colonnes de données. Colonnes trouvées : {len(df.columns) - 1}")

    return df





# --- Interface utilisateur ---

serial_options = get_serial_numbers()
serial_number = st.selectbox("Numéro de série", serial_options)


selected_date = st.date_input("📅 Date à analyser", datetime.today().date())
# Heure du bug
col_bug1, col_bug2 = st.columns(2)
with col_bug1:
    bug_hour = st.selectbox("🕒 Heure du bug", list(range(0, 24)), index=12)
with col_bug2:
    bug_minute = st.selectbox("🕐 Minute du bug", list(range(0, 60)), index=0)

bug_datetime = datetime.combine(selected_date, time(bug_hour, bug_minute))

# Plage automatique ou manuelle
auto_range = st.checkbox("🧠 Plage automatique autour du bug (−15min / +5min)", value=True)

if auto_range:
    start_dt = bug_datetime - timedelta(minutes=15)
    end_dt = bug_datetime + timedelta(minutes=5)
    start_time = start_dt.time()
    end_time = end_dt.time()
    st.info(f"⏱ Analyse automatique de {start_time.strftime('%H:%M')} à {end_time.strftime('%H:%M')}")
else:
    col1, col2 = st.columns(2)
    with col1:
        start_time = st.time_input("🕒 Heure de début", time(0, 0), step=timedelta(minutes=5))
    with col2:
        end_time = st.time_input("🕒 Heure de fin", time(23, 55), step=timedelta(minutes=5))

if st.button("Charger les données"):
    with st.spinner("Chargement..."):
        records = load_json_data(serial_number, selected_date, start_time, end_time)
        df = records_to_dataframe(records)

    if df.empty:
        st.warning("Aucune donnée trouvée pour cette date et cette plage horaire.")
    else:
        st.success(f"{len(df)} fichiers chargés.")
        st.write("🧾 Aperçu des données :")
        st.dataframe(df.head())

        num_cols = df.shape[1] - 1

        # Sélection des index pour le graphique combiné
        #st.markdown("### 🎯 Sélection des index pour le graphique combiné")
        #index_names = df.columns[1:].tolist()  # ignorer la colonne "date"
        #selected_names = st.multiselect(
        #    "Colonnes disponibles",
        #    options=index_names,
        #    default=index_names[:min(5, len(index_names))]
        #)

        # ✅ Graphique combiné
        #if selected_names:
        #    fig_combined = go.Figure()
        #    for name in selected_names:
        #        fig_combined.add_trace(go.Scatter(
        #            x=df['date'], y=df[name], mode='lines', name=name
        #        ))

        #    fig_combined.add_vline(x=bug_datetime, line=dict(color="red", dash="dash"), name="Heure du bug")
        #    fig_combined.update_layout(
        #        title="📊 Graphique combiné",
        #        xaxis_title="Heure",
        #        yaxis_title="Valeur",
        #        legend_title="Index"
        #    )
        #    st.plotly_chart(fig_combined, use_container_width=True)

        # ✅ Graphiques individuels pour tous les index
        st.markdown("### 📉 Graphiques individuels pour tous les index")
        for name in df.columns[1:]:
            fig = px.line(
                df, x="date", y=name,
                title=name,
                labels={"date": "Heure", name: "Valeur"},
                markers=True
            )

            fig.add_vline(x=bug_datetime, line_dash="dash", line_color="red")
            st.plotly_chart(fig, use_container_width=True)
