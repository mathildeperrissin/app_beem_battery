import streamlit as st
import pandas as pd
from google.cloud import bigquery

client = bigquery.Client()

@st.cache_data
def load_faulty_inverters():
    query = """
        WITH device_user_data AS (
            SELECT 
                d.serial_number,
                u.firstname,
                u.lastname,
                ld.working_mode_code,
                ld.last_known_measure_date,
                u.email
            FROM `beem-data-warehouse.airbyte_postgresql.battery_device` AS d
            LEFT JOIN `beem-data-warehouse.airbyte_postgresql.battery_live_data` AS ld ON ld.battery_id = d.id
            LEFT JOIN `beem-data-warehouse.airbyte_postgresql.house_user` AS hu ON d.house_id = hu.house_id
            LEFT JOIN `beem-data-warehouse.airbyte_postgresql.user` AS u ON hu.user_id = u.id
            LEFT JOIN `beem-data-warehouse.airbyte_postgresql.house` AS h ON h.id = hu.house_id
            WHERE d.deleted_at IS NULL
              AND d.replaced_by_id IS NULL
              AND d.warranty_status = 'activated'
              AND d.serial_number NOT IN ('021LOLL190154M', '021LOLF080008M')
        ),
        serial_counts AS (
            SELECT 
                serial_number,
                COUNT(*) AS nb
            FROM device_user_data
            GROUP BY serial_number
        ),
        final_filtered AS (
            SELECT dud.*
            FROM device_user_data dud
            JOIN serial_counts sc ON dud.serial_number = sc.serial_number
            WHERE sc.nb = 1
               OR (
                   sc.nb > 1
                   AND dud.email NOT LIKE '%@beemenergy.com'
                   AND dud.email NOT LIKE '%@beemenergy.fr'
               )
        )
        SELECT *
        FROM final_filtered
        WHERE working_mode_code NOT IN (
            'ampace_v1_on_grid_discharge',
            'ampace_v1_on_grid_charge',
            'ampace_v1_on_grid_passby'
        )
          AND working_mode_code NOT LIKE 'ampace_v2%'
          AND serial_number IS NOT NULL
    """
    return client.query(query).to_dataframe()

# ========== Affichage Streamlit ==========

st.title("⚠️ Not running inverter list")

faulty_df = load_faulty_inverters()

# Affichage du tableau
st.dataframe(
    faulty_df.sort_values("last_known_measure_date")[[
        "serial_number", "firstname", "lastname", "working_mode_code", "last_known_measure_date"
    ]]
)

# Bouton de téléchargement
st.download_button(
    label="📥 Télécharger en CSV",
    data=faulty_df.to_csv(index=False).encode('utf-8'),
    file_name="not_running_inverters.csv",
    mime='text/csv'
)
