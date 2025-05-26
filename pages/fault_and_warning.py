import streamlit as st
import pandas as pd
from google.cloud import bigquery

client = bigquery.Client()

@st.cache_data
def load_faulty_inverters():
    query = """
        SELECT 
            serial_number,
            firstname,
            lastname,
            working_mode_code,
            last_known_measure_date
        FROM (
            SELECT 
                d.serial_number AS serial_number,
                u.firstname AS firstname,
                u.lastname AS lastname,
                u.id AS user_id,
                ld.last_known_measure_date AS last_known_measure_date,
                ld.working_mode_code AS working_mode_code
            FROM `beem-data-warehouse.airbyte_postgresql.battery_device` AS d
            LEFT JOIN `beem-data-warehouse.airbyte_postgresql.battery_live_data` AS ld ON ld.battery_id = d.id
            INNER JOIN `beem-data-warehouse.airbyte_postgresql.house` AS h ON h.id = d.house_id
            INNER JOIN `beem-data-warehouse.airbyte_postgresql.house_user` AS hu ON hu.house_id = h.id
            INNER JOIN `beem-data-warehouse.airbyte_postgresql.user` AS u ON u.id = hu.user_id
            WHERE d.deleted_at IS NULL
              AND d.replaced_by_id IS NULL
              AND d.warranty_status = 'activated'
              AND hu.mode = 'w'  -- ⚠️ présent dans Bob, pas dans ton code actuel
              AND u.id != 22
              AND u.id != 4395
              AND d.serial_number NOT IN (
                  '021LOLF080008M',
                  '519100001533252014000009',
                  '519100001533252014000010'
              )
              AND ld.working_mode_code NOT IN (
                  'ampace_v1_on_grid_discharge',
                  'ampace_v1_on_grid_charge',
                  'ampace_v1_on_grid_passby',
                  'ampace_v2_normal'
              )
              AND ld.working_mode_code NOT LIKE 'ampace_v2%'
        ) AS virtual_table
        ORDER BY last_known_measure_date ASC
        LIMIT 1000
    """
    return client.query(query).to_dataframe()

# ========== Affichage Streamlit ==========

st.title("⚠️ Not running inverter list")

faulty_df = load_faulty_inverters()

st.dataframe(
    faulty_df[[  # Tri déjà fait dans la requête
        "serial_number", "firstname", "lastname", "working_mode_code", "last_known_measure_date"
    ]]
)

st.download_button(
    label="📥 Télécharger en CSV",
    data=faulty_df.to_csv(index=False).encode('utf-8'),
    file_name="not_running_inverters.csv",
    mime='text/csv'
)
