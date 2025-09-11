import streamlit as st
import pandas as pd
from google.cloud import bigquery

# --- Config ---
st.set_page_config(page_title="BART - monitoring and warning", layout="wide")
st.title("Monitoring and warning")

client = bigquery.Client()

# ============================
# Loads
# ============================

@st.cache_data
def load_new_systems_last_24h():
    query = """
    WITH base AS (
      SELECT
        d.serial_number,
        d.created_at AS created_at,
        d.warranty_status,
        u.firstname,
        u.lastname,
        u.email
      FROM `beem-data-warehouse.airbyte_postgresql.battery_device` d
      INNER JOIN `beem-data-warehouse.airbyte_postgresql.house` h ON h.id = d.house_id
      INNER JOIN `beem-data-warehouse.airbyte_postgresql.house_user` hu ON hu.house_id = h.id AND hu.mode = 'W'
      INNER JOIN `beem-data-warehouse.airbyte_postgresql.user` u ON u.id = hu.user_id
      WHERE d.deleted_at IS NULL
        AND d.replaced_by_id IS NULL
        AND u.id NOT IN (22, 4395)
        AND d.created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
    )
    SELECT
      serial_number,
      firstname,
      lastname,
      email,
      created_at,
      warranty_status,
      CASE
        WHEN LOWER(COALESCE(warranty_status, '')) = 'pending' THEN '❗ Pending'
        ELSE '✅ Completed'
      END AS pairing_status_hint
    FROM base
    ORDER BY created_at DESC
    """
    return client.query(query).to_dataframe()


@st.cache_data
def load_disconnected_batteries():
    query = """
    SELECT
      d.serial_number,
      u.firstname,
      u.lastname,
      u.email,
      bld.last_known_measure_date,
      TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), bld.last_known_measure_date, HOUR) AS hours_since_last_seen
    FROM `beem-data-warehouse.airbyte_postgresql.battery_device` d
    LEFT JOIN `beem-data-warehouse.airbyte_postgresql.battery_live_data` bld ON bld.battery_id = d.id
    INNER JOIN `beem-data-warehouse.airbyte_postgresql.house` h ON h.id = d.house_id
    INNER JOIN `beem-data-warehouse.airbyte_postgresql.house_user` hu ON hu.house_id = h.id AND hu.mode = 'W'
    INNER JOIN `beem-data-warehouse.airbyte_postgresql.user` u ON u.id = hu.user_id
    WHERE d.deleted_at IS NULL
      AND d.replaced_by_id IS NULL
      AND u.id NOT IN (22, 4395)
      AND bld.last_known_measure_date IS NOT NULL
      AND bld.last_known_measure_date < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
    ORDER BY bld.last_known_measure_date ASC
    """
    return client.query(query).to_dataframe()


@st.cache_data
def load_active_issues():
    query = """
    WITH faults AS (
      SELECT
        b.serial_number,
        u.firstname,
        u.lastname,
        u.email,
        'fault' AS issue_type,
        l.code AS issue_code,
        l.message AS issue_message,
        l.date AS issue_date,
        l.created_at AS issue_created_at
      FROM `beem-data-warehouse.airbyte_postgresql.battery_device` b
      INNER JOIN `beem-data-warehouse.airbyte_postgresql.house` h ON h.id = b.house_id
      INNER JOIN `beem-data-warehouse.airbyte_postgresql.house_user` hu ON hu.house_id = h.id AND hu.mode = 'W'
      INNER JOIN `beem-data-warehouse.airbyte_postgresql.user` u ON u.id = hu.user_id
      INNER JOIN `beem-data-warehouse.airbyte_postgresql.battery_device_log` l ON l.battery_id = b.id
      WHERE b.deleted_at IS NULL
        AND b.replaced_by_id IS NULL
        AND u.id NOT IN (22, 4395)
        AND l.cleared_at IS NULL
        AND l.type = 'fault'
    ),
    warn_no_grid AS (
      SELECT
        b.serial_number,
        u.firstname,
        u.lastname,
        u.email,
        'warning_no_grid_input' AS issue_type,
        l.code AS issue_code,
        l.message AS issue_message,
        l.date AS issue_date,
        l.created_at AS issue_created_at
      FROM `beem-data-warehouse.airbyte_postgresql.battery_device` b
      INNER JOIN `beem-data-warehouse.airbyte_postgresql.house` h ON h.id = b.house_id
      INNER JOIN `beem-data-warehouse.airbyte_postgresql.house_user` hu ON hu.house_id = h.id AND hu.mode = 'W'
      INNER JOIN `beem-data-warehouse.airbyte_postgresql.user` u ON u.id = hu.user_id
      INNER JOIN `beem-data-warehouse.airbyte_postgresql.battery_device_log` l ON l.battery_id = b.id
      WHERE b.deleted_at IS NULL
        AND b.replaced_by_id IS NULL
        AND u.id NOT IN (22, 4395)
        AND l.cleared_at IS NULL
        AND l.type = 'warning'
        AND LOWER(l.message) = 'no grid input'
    ),
    standby_offgrid AS (
      SELECT
        d.serial_number,
        u.firstname,
        u.lastname,
        u.email,
        'standby_or_offgrid' AS issue_type,
        NULL AS issue_code,
        CONCAT('Mode: ', COALESCE(bld.working_mode_code, 'UNKNOWN')) AS issue_message,
        bld.last_known_measure_date AS issue_date,
        bld.last_known_measure_date AS issue_created_at
      FROM `beem-data-warehouse.airbyte_postgresql.battery_device` d
      LEFT JOIN `beem-data-warehouse.airbyte_postgresql.battery_live_data` bld ON bld.battery_id = d.id
      INNER JOIN `beem-data-warehouse.airbyte_postgresql.house` h ON h.id = d.house_id
      INNER JOIN `beem-data-warehouse.airbyte_postgresql.house_user` hu ON hu.house_id = h.id AND hu.mode = 'W'
      INNER JOIN `beem-data-warehouse.airbyte_postgresql.user` u ON u.id = hu.user_id
      WHERE d.deleted_at IS NULL
        AND d.replaced_by_id IS NULL
        AND u.id NOT IN (22, 4395)
        AND bld.working_mode_code IS NOT NULL
        AND (
              LOWER(bld.working_mode_code) LIKE '%standby%'
           OR LOWER(bld.working_mode_code) LIKE '%offgrid%'
           OR LOWER(bld.working_mode_code) LIKE '%off_grid%'
        )
    )
    SELECT * FROM faults
    UNION ALL
    SELECT * FROM warn_no_grid
    UNION ALL
    SELECT * FROM standby_offgrid
    ORDER BY issue_created_at ASC
    """
    return client.query(query).to_dataframe()

# ============================
# UI (3 tableaux empilés)
# ============================

# 1) New systems <24h
st.header("🆕 New systems in last 24h (+ warranty/pairing)")
new_sys_df = load_new_systems_last_24h()
if new_sys_df.empty:
    st.info("Aucun nouveau système sur les dernières 24h.")
else:
    st.caption(f"{len(new_sys_df)} lignes")
    st.dataframe(new_sys_df[[
        "serial_number", "firstname", "lastname", "email",
        "created_at", "warranty_status", "pairing_status_hint"
    ]])
    st.download_button(
        "📥 Export CSV (new systems)",
        data=new_sys_df.to_csv(index=False).encode("utf-8"),
        file_name="new_systems_last_24h.csv",
        mime="text/csv"
    )

st.divider()

# 2) Disconnected >24h
st.header("🔌 Batteries disconnected (>24h since last connection)")
disc_df = load_disconnected_batteries()
if disc_df.empty:
    st.success("Aucune batterie déconnectée depuis plus de 24h ✅")
else:
    st.caption(f"{len(disc_df)} lignes")
    st.dataframe(disc_df[[
        "serial_number", "firstname", "lastname", "email",
        "last_known_measure_date", "hours_since_last_seen"
    ]])
    st.download_button(
        "📥 Export CSV (disconnected)",
        data=disc_df.to_csv(index=False).encode("utf-8"),
        file_name="disconnected_batteries_gt24h.csv",
        mime="text/csv"
    )

st.divider()

# 3) Active issues
st.header("🚧 Active issues (faults not cleared, standby/offgrid, 'No grid input')")
issues_df = load_active_issues()
if issues_df.empty:
    st.success("Aucun problème actif détecté ✅")
else:
    st.caption(f"{len(issues_df)} lignes")
    st.dataframe(issues_df[[
        "serial_number", "firstname", "lastname", "email",
        "issue_type", "issue_message", "issue_date", "issue_created_at"
    ]])
    st.download_button(
        "📥 Export CSV (active issues)",
        data=issues_df.to_csv(index=False).encode("utf-8"),
        file_name="active_issues.csv",
        mime="text/csv"
    )

