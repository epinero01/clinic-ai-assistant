import streamlit as st
from databricks import sql

st.title("🏥 CityCare Clinic")

st.write("Intentando conectar...")

HOSTNAME = "AQUI_TU_HOSTNAME"
HTTP_PATH = "AQUI_TU_HTTP_PATH"
TOKEN = "AQUI_TU_TOKEN"

try:

    conn = sql.connect(
        server_hostname=HOSTNAME,
        http_path=HTTP_PATH,
        access_token=TOKEN
    )

    st.success("Conexión realizada")

    cursor = conn.cursor()

    cursor.execute("SELECT current_timestamp()")

    result = cursor.fetchall()

    st.write(result)

except Exception as e:

    st.error(type(e).__name__)
    st.error(str(e))
  
