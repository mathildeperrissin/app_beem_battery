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

# --- Chargement des fichiers JSON depuis GCS ---
@st.cache_data
def load_json_data(serial_number, selected_date, start_time, end_time):
    client = storage.Client()
    data_bucket = client.bucket(BUCKET_NAME)
    index_bucket = client.bucket(INDEX_BUCKET_NAME)

    # Charger l’index depuis le bucket d’index
    index_blob_path = f"{serial_number}_index.json"
    index_blob = index_bucket.blob(index_blob_path)
    try:
        content = index_blob.download_as_text()
        index = json.loads(content)
    except Exception as e:
        st.error(f"❌ Erreur de lecture de l’index JSON `{index_blob_path}` : {e}")
        return []

    # Filtrer les fichiers
    filtered_files = []
    for entry in index:
        try:
            dt = datetime.strptime(entry["date"], "%Y-%m-%d %H:%M:%S")
            if dt.date() == selected_date and start_time <= dt.time() <= end_time:
                filtered_files.append((dt, entry["path"]))
        except Exception as e:
            print(f"Erreur parsing date dans {entry.get('path', '?')} : {e}")

    # Télécharger les fichiers de données
    records = []
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
            print(f"❌ Erreur de lecture {path} : {e}")

    return records

# --- Création du DataFrame ---
def records_to_dataframe(records):
    if not records:
        return pd.DataFrame()
    
    df = pd.DataFrame(records)
    values_expanded = pd.DataFrame(df['values'].to_list())
    df = pd.concat([df['date'], values_expanded], axis=1)

    # Liste des 349 noms d’index attendus (sans les numéros)
    custom_index_names_raw = [
        "DevProtocol", "Master_Version", "YearMonth", "DateTime", "MinutesSeconds", "Battery_Status",
        "Battery_Volt", "Battery_Curr", "Input_Frequency", "Input_Volt", "Input_Appa.P A", "Input_Acti.P",
        "Input_ReActi.P", "Inverter_Volt", "Inverter_Curr", "Inverter_Acti.P", "Drm0Sts", "WetPortSta",
        "PV_Power", "Bus_Volt", "SysDailyGenerationKwh_L", "SysDailyGenerationKwh_H",
        "SysTotalGenerationKwh_L", "SysTotalGenerationKwh_H", "Load_Volt", "Load_Curr", "Load_Acti.P",
        "Load_Appa.P", "Load_Percentage", "EnergyFlow_Line 1-8", "EnergyFlow_Line 9-16", "MonitorVersion",
        "Reserved", "SOC", "BUS _Volt", "BUS_Curr", "Reserved", "Reserved", "CT_PowerByDC", "BUS_Power",
        "SystemError", "BatteryDailyDischargeKwh_L", "BatteryDailyDischargeKwh_H",
        "BatteryTotalDischargeKwh_L", "BatteryTotalDischargeKwh_H", "DC-AC_StatusMode", "DC-AC_ERR_H",
        "DC-AC_ERR_L", "Reserved", "Reserved", "AC_Version", "AC_Temp1", "AC_Temp2", "AC_InternalVer",
        "Grid_VoltAVG(V)", "Grid_CurrAVG(A)", "Grid_Frequency(Hz)", "Grid_ActiPw(W)", "Grid_Pw(W)",
        "PowerFactor", "Inv_VoltAVG(V)", "Inv_CurrAVG(A)", "Inv_Pw(W)", "Load_Volt(V)", "Load_Pw(W)",
        "PowerSetting", "AC_CtrlPow", "DC-AC_STATE", "DC-AC_ERR_H", "DC-AC_ERR_L", "DC-AC_WARN_H",
        "DC-AC_WARN_L", "Reserved", "Reserved", "UndercurrentStatus", "FullChargeStatus", "AC_User9",
        "Inv_Ileak", "BatteryPower", "MonitorBoard", "DC_FwVersion", "CT1_Power", "AC_User19", "PV1_Power",
        "PV2_Power", "PV3_Power", "WindTurbine_Pw", "PV1_Volt", "PV1_Curr", "PV2_Volt", "PV2_Curr",
        "PV3_Volt", "PV3_Curr", "WindTurbine_Volt", "WindTurbine_Curr", "Reserved",
        "BMS_ChargeLimitVolt", "BMS_MaxChargeCurr", "BMS_MaxDischargeCurr", "BMS_DischargeCutoffVolt",
        "BMS_Volt", "BMS_Curr", "BMS_Temp", "BMS_SOC", "BMS_SOH", "BMS_Status", "BMS_ERR_H", "BMS_ERR_L",
        "BMS_WARN_H", "BMS_WARN_L", "BMS_Version", "BMS_Capacity", "BatteriesCount", "CellsCount",
        "RACK_Volt", "RACK_Curr", "RACK_SOC", "RACK_SOH", "RACK_MaxCellVolt", "RACK_MaxCellVoltNum",
        "RACK_MinCellVolt", "RACK_MinCellVoltNum", "RACK_MaxCellTemp", "RACK_MaxCellTempNum",
        "RACK_MinCellTemp", "RACK_MinCellTempNum", "RACK_HwVersion", "RACK_FwVersion", "RACK_ERR_H",
        "RACK_WARN", "RACK_Sta", "RACK_ERR_L", "RACK_SN_High", "RACK_SN_Mid", "RACK_SN_Low", "RACK_SN_H",
        "RACK_SN_L", "RACK_CycleCount", "RACK_RemainCapacity", "RACK_FullChargeCapacity", "RACK_PlugStatus",
        "Reserved", "Reserved", "Reserved", "Reserved", "Reserved", "Reserved", "Reserved", "Reserved",
        "Reserved", "Reserved", "Reserved", "Reserved", "Reserved", "Reserved", "Reserved", "Reserved",
        "Reserved", "Reserved", "Reserved", "Reserved", "DSP1_REG38", "DSP1_REG39", "DSP1_REG40",
        "DSP1_REG41", "DSP1_REG42", "DSP1_REG43", "DSP1_REG44", "DSP1_REG45", "DSP1_REG46", "DSP1_REG47",
        "DSP1_REG48", "DSP1_REG49", "DSP1_REG50", "DSP1_REG51", "DSP1_REG52", "DSP1_REG53", "DSP1_REG54",
        "DSP1_REG55", "DSP1_REG56", "DSP1_REG57", "DSP1_REG58", "DSP1_REG59", "DSP2_REG00", "DSP2_REG01",
        "DSP2_REG02", "DSP2_REG03", "DSP2_REG04", "DSP2_REG05", "DSP2_REG06", "DSP2_REG07", "DSP2_REG08",
        "DSP2_REG09", "DSP2_REG10", "DSP2_REG11", "DSP2_REG12", "DSP2_REG13", "DSP2_REG14", "DSP2_REG15",
        "DSP2_REG16", "DSP2_REG17", "DSP2_REG18", "DSP2_REG19", "DSP2_REG20", "DSP2_REG21", "DSP2_REG22",
        "DSP2_REG23", "DSP2_REG24", "DSP2_REG25", "DSP2_REG26", "DSP2_REG27", "BMU1_MoudleVolt",
        "BMU1_CellNum", "BMU1_MaxCellVolt", "BMU1_MinCellVolt", "BMU1_CellTempNum", "BMU1_HwVersion",
        "BMU1_FwVersion", "BMU1_SN_H", "BMU1_SN_L", "BMU1_BalancingTarget", "BMU1_Reserved",
        "BMU2_MoudleVolt", "BMU2_CellNum", "BMU2_MaxCellVolt", "BMU2_MinCellVolt", "BMU2_CellTempNum",
        "BMU2_HwVersion", "BMU2_FwVersion", "BMU2_SN_H", "BMU2_SN_L", "BMU2_BalancingTarget",
        "BMU2_Reserved", "BMU3_MoudleVolt", "BMU3_CellNum", "BMU3_MaxCellVolt", "BMU3_MinCellVolt",
        "BMU3_CellTempNum", "BMU3_HwVersion", "BMU3_FwVersion", "BMU3_SN_H", "BMU3_SN_L",
        "BMU3_BalancingTarget", "BMU3_Reserved", "BMU4_MoudleVolt", "BMU4_CellNum", "BMU4_MaxCellVolt",
        "BMU4_MinCellVolt", "BMU4_CellTempNum", "BMU4_HwVersion", "BMU4_FwVersion", "BMU4_SN_H",
        "BMU4_SN_L", "BMU4_BalancingTarget", "BMU4_Reserved", "BMU5_MoudleVolt", "BMU5_CellNum",
        "BMU5_MaxCellVolt", "BMU5_MinCellVolt", "BMU5_CellTempNum", "BMU5_HwVersion", "BMU5_FwVersion",
        "BMU5_SN_H", "BMU5_SN_L", "BMU5_BalancingTarget", "BMU5_Reserved", "BMU6_MoudleVolt",
        "BMU6_CellNum", "BMU6_MaxCellVolt", "BMU6_MinCellVolt", "BMU6_CellTempNum", "BMU6_HwVersion",
        "BMU6_FwVersion", "BMU6_SN_H", "BMU6_SN_L", "BMU6_BalancingTarget", "BMU6_Reserved",
        "BMU7_MoudleVolt", "BMU7_CellNum", "BMU7_MaxCellVolt", "BMU7_MinCellVolt", "BMU7_CellTempNum",
        "BMU7_HwVersion", "BMU7_FwVersion", "BMU7_SN_H", "BMU7_SN_L", "BMU7_BalancingTarget",
        "BMU7_Reserved", "BMU8_MoudleVolt", "BMU8_CellNum", "BMU8_MaxCellVolt", "BMU8_MinCellVolt",
        "BMU8_CellTempNum", "BMU8_HwVersion", "BMU8_FwVersion", "BMU8_SN_H", "BMU8_SN_L",
        "BMU8_BalancingTarget", "BMU8_Reserved", "Reserved", "Reserved", "Reserved", "Reserved", "Reserved",
        "Reserved", "Reserved", "Reserved", "Reserved", "Reserved", "Reserved", "Reserved", "Reserved",
        "Reserved", "Reserved", "Reserved", "Reserved", "Reserved", "Reserved", "Meter1_CombineKwH_H",
        "Meter1_CombineKwH_L", "Meter1_PositiveKwH_H", "Meter1_PositiveKwH_L", "Meter1_NagativeKwH_H",
        "Meter1_NagativeKwH_L", "Meter1_Volt_H", "Meter1_Volt_L", "Meter1_Curr_H", "Meter1_Curr_L",
        "Meter1_ActivePower_H", "Meter1_ActivePower_L", "Meter1_PowerFactor_H", "Meter1_PowerFactor_L",
        "Meter1_Frequency_H", "Meter1_Frequency_L", "Meter2_CombineKwH_H", "Meter2_CombineKwH_L",
        "Meter2_PositiveKwH_H", "Meter2_PositiveKwH_L", "Meter2_NagativeKwH_H", "Meter2_NagativeKwH_L",
        "Meter2_Volt_H", "Meter2_Volt_L", "Meter2_Curr_H", "Meter2_Curr_L", "Meter2_ActivePower_H",
        "Meter2_ActivePower_L", "Meter2_PowerFactor_H", "Meter2_PowerFactor_L", "Meter2_Frequency_H",
        "Meter2_Frequency_L", "Reserved", "Reserved", "Reserved", "Reserved", "Reserved", "Reserved",
        "Reserved", "Reserved", "Reserved", "Reserved"
    ]

    # Renommer les colonnes si 349 colonnes de données
    if df.shape[1] - 1 == 349:
        seen = {}
        new_names = []
        for name in custom_index_names_raw:
            base = name.strip()
            count = seen.get(base, 0)
            final = base if count == 0 else f"{base}_{count}"
            seen[base] = count + 1
            new_names.append(final)
        df.columns = ["date"] + new_names

    return df


# --- Interface utilisateur ---
st.title("📈 Suivi de données batterie (GCS)")

serial_number = st.selectbox("Numéro de série", [
    "021LOLF080004M",
    "021LOLF080008M",
    "021LOLK080001M"
])

selected_date = st.date_input("📅 Date à analyser", datetime(2025, 6, 1).date())

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
        st.markdown("### 🎯 Sélection des index pour le graphique combiné")
        index_names = df.columns[1:].tolist()  # ignorer la colonne "date"
        selected_names = st.multiselect(
            "Colonnes disponibles",
            options=index_names,
            default=index_names[:min(5, len(index_names))]
        )

        # ✅ Graphique combiné
        if selected_indices:
            fig_combined = go.Figure()
            for idx in selected_indices:
                fig_combined.add_trace(go.Scatter(
                    x=df['date'], y=df[idx], mode='lines', name=f"Index {idx}"
                ))
            fig_combined.add_vline(x=bug_datetime, line=dict(color="red", dash="dash"), name="Heure du bug")
            fig_combined.update_layout(
                title="📊 Graphique combiné",
                xaxis_title="Heure",
                yaxis_title="Valeur",
                legend_title="Index"
            )
            st.plotly_chart(fig_combined, use_container_width=True)

        # ✅ Graphiques individuels pour tous les index
        st.markdown("### 📉 Graphiques individuels pour tous les index")
        for idx in range(num_cols):
            fig = px.line(
                df, x="date", y=idx,
                title=f"Index {idx}",
                labels={"date": "Heure", str(idx): "Valeur"}
            )
            fig.add_vline(x=bug_datetime, line_dash="dash", line_color="red")
            st.plotly_chart(fig, use_container_width=True)
