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
def load_recent_creations_3d():
    # Créations sur les 3 derniers jours, avec statut de pairing
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
        AND d.created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 72 HOUR)
    )
    SELECT
      serial_number,
      firstname,
      lastname,
      email,
      created_at,
      warranty_status,
      CASE
        WHEN LOWER(TRIM(COALESCE(NULLIF(warranty_status, ''), 'pending'))) = 'pending'
          THEN '❗ Pending'
        ELSE '✅ Completed'
      END AS pairing_status_hint
    FROM base
    ORDER BY created_at DESC
    """
    return client.query(query).to_dataframe()


@st.cache_data
def load_unpaired_all_time():
    # Tous les systèmes dont le pairing n'est pas terminé (warranty_status = 'pending'), sans limite de date
    query = """
    SELECT
      d.serial_number,
      d.created_at,
      u.firstname,
      u.lastname,
      u.email,
      d.warranty_status
    FROM `beem-data-warehouse.airbyte_postgresql.battery_device` d
    INNER JOIN `beem-data-warehouse.airbyte_postgresql.house` h ON h.id = d.house_id
    INNER JOIN `beem-data-warehouse.airbyte_postgresql.house_user` hu ON hu.house_id = h.id AND hu.mode = 'W'
    INNER JOIN `beem-data-warehouse.airbyte_postgresql.user` u ON u.id = hu.user_id
    WHERE d.deleted_at IS NULL
      AND d.replaced_by_id IS NULL
      AND u.id NOT IN (22, 4395)
      AND (
            LOWER(TRIM(d.warranty_status)) = 'pending'
            OR NULLIF(TRIM(d.warranty_status), '') IS NULL
          )
    ORDER BY d.created_at DESC
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
      AND NOT REGEXP_CONTAINS(LOWER(u.email), r'@beemenergy\.(com|fr)$')
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
# UI (4 tableaux empilés)
# ============================

# A) Créations récentes (3 jours)
st.header("🆕 Newly created systems (last 3 days) — pairing status")
recent_df = load_recent_creations_3d()
if recent_df.empty:
    st.info("Aucune création sur les 3 derniers jours.")
else:
    st.caption(f"{len(recent_df)} lignes")
    st.dataframe(recent_df[[
        "serial_number", "firstname", "lastname", "email",
        "created_at", "warranty_status", "pairing_status_hint"
    ]])
    st.download_button(
        "📥 Export CSV (recent creations 3d)",
        data=recent_df.to_csv(index=False).encode("utf-8"),
        file_name="recent_creations_3d.csv",
        mime="text/csv"
    )

st.divider()

# B) Tous les systèmes non appairés (peu importe la date)
st.header("⏳ Systems with pairing pending or NULL (all-time)")
unpaired_df = load_unpaired_all_time()
if unpaired_df.empty:
    st.success("Aucun système en 'pending' ✅")
else:
    st.caption(f"{len(unpaired_df)} lignes")
    st.dataframe(unpaired_df[[
        "serial_number", "firstname", "lastname", "email",
        "created_at", "warranty_status"
    ]])
    st.download_button(
        "📥 Export CSV (unpaired all-time)",
        data=unpaired_df.to_csv(index=False).encode("utf-8"),
        file_name="unpaired_all_time.csv",
        mime="text/csv"
    )

st.divider()

# C) Déconnectées >24h
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

# D) Issues actives
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

@st.cache_data
def load_low_soc_batteries():
    # Batteries avec SOC < 5% (en supposant que bld.soc existe ; convertit [0–1] -> % si besoin)
    query = """
    WITH base AS (
      SELECT
        d.id AS battery_id,
        d.serial_number,
        u.firstname,
        u.lastname,
        bld.soc AS soc_raw
      FROM `beem-data-warehouse.airbyte_postgresql.battery_device` d
      LEFT JOIN `beem-data-warehouse.airbyte_postgresql.battery_live_data` bld
        ON bld.battery_id = d.id
      INNER JOIN `beem-data-warehouse.airbyte_postgresql.house` h
        ON h.id = d.house_id
      INNER JOIN `beem-data-warehouse.airbyte_postgresql.house_user` hu
        ON hu.house_id = h.id AND hu.mode = 'W'
      INNER JOIN `beem-data-warehouse.airbyte_postgresql.user` u
        ON u.id = hu.user_id
      WHERE d.deleted_at IS NULL
        AND d.replaced_by_id IS NULL
        AND u.id NOT IN (22, 4395)
        AND NOT REGEXP_CONTAINS(LOWER(u.email), r'@beemenergy\\.(com|fr)$')
        -- Optionnel : ne garder que des mesures récentes
        -- AND bld.last_known_measure_date >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 48 HOUR)
    )
    SELECT
      battery_id,
      serial_number,
      firstname,
      lastname,
      ROUND(
        CASE
          WHEN SAFE_CAST(soc_raw AS FLOAT64) IS NULL THEN NULL
          WHEN SAFE_CAST(soc_raw AS FLOAT64) <= 1 THEN SAFE_CAST(soc_raw AS FLOAT64) * 100
          ELSE SAFE_CAST(soc_raw AS FLOAT64)
        END
      , 1) AS soc
    FROM base
    WHERE
      SAFE_CAST(soc_raw AS FLOAT64) IS NOT NULL
      AND (
        -- si soc est en [0–1]
        SAFE_CAST(soc_raw AS FLOAT64) <= 1 AND SAFE_CAST(soc_raw AS FLOAT64) < 0.05
        OR
        -- si soc est déjà en %
        SAFE_CAST(soc_raw AS FLOAT64) > 1 AND SAFE_CAST(soc_raw AS FLOAT64) < 5
      )
    ORDER BY soc ASC, lastname ASC, firstname ASC
    """
    return client.query(query).to_dataframe()


st.divider()

# E) SOC < 5%
st.header("🪫 Batteries with SOC < 5%")
low_soc_df = load_low_soc_batteries()

if low_soc_df.empty:
    st.success("Aucune batterie avec SOC < 5% ✅")
else:
    st.caption(f"{len(low_soc_df)} lignes")
    st.dataframe(low_soc_df[[
        "lastname", "firstname", "battery_id", "serial_number", "soc"
    ]], use_container_width=True)
    st.download_button(
        "📥 Export CSV (SOC < 5%)",
        data=low_soc_df.to_csv(index=False).encode("utf-8"),
        file_name="low_soc_batteries_lt5.csv",
        mime="text/csv"
    )
