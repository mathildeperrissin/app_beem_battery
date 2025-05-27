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
        d.serial_number,
        u.firstname,
        u.id,
        u.lastname,
        last_known_measure_date,
        working_mode_code
      FROM `beem-data-warehouse.airbyte_postgresql.battery_device` d
      LEFT JOIN `beem-data-warehouse.airbyte_postgresql.battery_live_data` bld ON bld.battery_id = d.id
      INNER JOIN `beem-data-warehouse.airbyte_postgresql.house` h ON h.id = d.house_id
      INNER JOIN `beem-data-warehouse.airbyte_postgresql.house_user` hu ON hu.house_id = h.id AND hu.mode = 'W'
      INNER JOIN `beem-data-warehouse.airbyte_postgresql.user` u ON u.id = hu.user_id
      WHERE d.deleted_at IS NULL
        AND u.id NOT IN (22, 4395)
        AND d.replaced_by_id IS NULL
        AND working_mode_code NOT IN (
          'ampace_v1_on_grid_discharge',
          'ampace_v1_on_grid_charge',
          'ampace_v1_on_grid_passby',
          'ampace_v2_normal'
        )
      ORDER BY last_known_measure_date ASC
    ) AS virtual_table
    WHERE serial_number NOT IN (
      '021LOLF080008M',
      '519100001533250214000009',
      '519100001533250214000010'
    )
    """
    return client.query(query).to_dataframe()

@st.cache_data
def load_fault_and_warning_logs():
    query = """
    WITH virtual_table AS (
      SELECT 
        b.serial_number,
        u.firstname,
        u.lastname,
        u.email,
        l.type,
        l.code,
        l.date,
        l.message,
        l.created_at
      FROM `beem-data-warehouse.airbyte_postgresql.battery_device` b
      INNER JOIN `beem-data-warehouse.airbyte_postgresql.house` h 
        ON h.id = b.house_id
      INNER JOIN `beem-data-warehouse.airbyte_postgresql.house_user` hu 
        ON hu.house_id = h.id AND hu.mode = 'W'
      INNER JOIN `beem-data-warehouse.airbyte_postgresql.user` u 
        ON u.id = hu.user_id
      INNER JOIN `beem-data-warehouse.airbyte_postgresql.battery_device_log` l 
        ON l.battery_id = b.id
      WHERE 
        b.deleted_at IS NULL
        AND b.replaced_by_id IS NULL
        AND l.cleared_at IS NULL
        AND l.type NOT IN ('Offline Reason')
    )

    SELECT 
      serial_number,
      firstname,
      lastname,
      email,
      CASE type
        WHEN 'fault' THEN 3
        WHEN 'warning' THEN 2
        ELSE 1
      END AS type_as_int,
      type,
      message,
      created_at,
      date
    FROM virtual_table
    WHERE 
      serial_number NOT IN (
        '519100001533250214000009',
        '021LOLF080008M',
        '519100001533250214000010'
      )
      AND (
        type = 'fault' OR 
        (type = 'warning' AND message = 'No grid input')
      )
    ORDER BY created_at ASC
    LIMIT 1000
    """
    return client.query(query).to_dataframe()

# ========== Affichage Streamlit ==========

st.title("⚠️ Not running inverter list")

faulty_df = load_faulty_inverters()

st.dataframe(
    faulty_df[[
        "serial_number", "firstname", "lastname", "working_mode_code", "last_known_measure_date"
    ]]
)

st.download_button(
    label="📥 Télécharger en CSV",
    data=faulty_df.to_csv(index=False).encode('utf-8'),
    file_name="not_running_inverters.csv",
    mime='text/csv'
)

# ========== Ajout des logs fault & warning ==========

st.title("🚨 Battery Fault & Warning Logs")

fault_warning_df = load_fault_and_warning_logs()

st.dataframe(
    fault_warning_df[[
        "serial_number", "firstname", "lastname", "email", "type", "message", "created_at", "date"
    ]]
)

st.download_button(
    label="📥 Télécharger les logs",
    data=fault_warning_df.to_csv(index=False).encode('utf-8'),
    file_name="fault_and_warning_logs.csv",
    mime='text/csv'
)
