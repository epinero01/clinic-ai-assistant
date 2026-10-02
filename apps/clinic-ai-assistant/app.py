import streamlit as st
import pandas as pd
from databricks import sql

st.set_page_config(
    page_title="CityCare Clinic",
    page_icon="🏥",
    layout="wide"
)

st.title("🏥 CityCare Clinic")

hostname = st.text_input(
    "Server Hostname"
)

http_path = st.text_input(
    "HTTP Path"
)

token = st.text_input(
    "PAT Token",
    type="password"
)

if st.button("Conectar"):

    try:

        conn = sql.connect(
            server_hostname=hostname,
            http_path=http_path,
            access_token=token
        )

        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                specialty_id,
                specialty_name
            FROM clinic_ai.specialties
            ORDER BY specialty_name
        """)

        rows = cursor.fetchall()

        specialties_df = pd.DataFrame(
            rows,
            columns=[
                "specialty_id",
                "specialty_name"
            ]
        )

        st.success("✅ Conexión correcta")

        st.dataframe(
            specialties_df,
            use_container_width=True
        )

    except Exception as e:

        st.error(type(e).__name__)
        st.error(str(e))
        
