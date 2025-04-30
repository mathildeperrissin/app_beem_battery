import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(layout="wide")
st.title("Dashboard batteries")

# -------- Choix de la page --------
page = st.sidebar.selectbox("📄 Choisir une page", ["Page 1 : Dashboard global", "Page 2 : Dashboard zoom battery"])

# -------- Page 1 --------
if page == "Page 1 : Dashboard global":
    st.header("📋 Informations batteries (battery_actives_infos.csv)")

    @st.cache_data
    def load_info():
        df = pd.read_csv("battery_actives_infos.csv")
        return df

    df_infos = load_info()
    st.dataframe(df_infos)

# -------- Page 2 --------
elif page == "Page 2 : Dashboard zoom battery":
    st.header("📈 Données énergétiques détaillées")

    sources = {
        "battery_active_energy_measure.csv": {
            "title": "Consommation infra-journalière",
            "y_label": "Wh par batterie",
            "agg": False,
        },
        "battery_active_returned_energy_meter_measure.csv": {
            "title": "Ré-injection infra-journalière",
            "y_label": "Wh par batterie",
            "agg": False,
        },
        "battery_active_returned_energy_measure.csv": {
            "title": "Mesure de production solaire",
            "y_label": "Wh total (somme MPPT)",
            "agg": True,
        },
        "battery_energy_charged_measure.csv": {
            "title": "Énergie stockée par la batterie",
            "y_label": "Wh",
            "agg": False,
        },
        "battery_energy_discharged_measure.csv": {
            "title": "Énergie déstockée par la batterie",
            "y_label": "Wh",
            "agg": False,
        },
    }

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("📅 Date de début", datetime(2025, 4, 1))
    with col2:
        end_date = st.date_input("📅 Date de fin", datetime(2025, 4, 30))

    col3, col4 = st.columns(2)
    with col3:
        start_time = st.time_input("🕐 Heure de début", datetime.min.time())
    with col4:
        end_time = st.time_input("🕐 Heure de fin", datetime.max.time())

    start_datetime = datetime.combine(start_date, start_time)
    end_datetime = datetime.combine(end_date, end_time)

    @st.cache_data
    def get_all_device_ids():
        df = pd.read_csv("battery_active_energy_measure.csv")
        return sorted(df["device_id"].unique().tolist())

    device_choices = st.multiselect("🔌 Choisir une ou plusieures batteries", get_all_device_ids(), default=[41])

    @st.cache_data
    def load_data(filename):
        df = pd.read_csv(filename)
        df["date"] = pd.to_datetime(df["date"])
        return df

    for file, meta in sources.items():
        df = load_data(file)

        df = df[df["device_id"].isin(device_choices)]
        df = df[(df["date"].dt.tz_localize(None) >= start_datetime) & (df["date"].dt.tz_localize(None) <= end_datetime)]

        if df.empty:
            st.warning(f"Aucune donnée pour : {meta['title']}")
            continue

        if meta["agg"] and "device_sub_id" in df.columns:
            df = df.groupby(["date", "device_id"], as_index=False)["value"].sum()

        df_chart = df.pivot(index="date", columns="device_id", values="value")

        st.subheader(meta["title"])
        st.line_chart(df_chart, use_container_width=True)
        st.caption(f"Axe Y : {meta['y_label']}")
