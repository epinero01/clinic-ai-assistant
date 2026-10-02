import streamlit as st
from databricks import sql

st.title("🏥 CityCare Clinic prueba conexion")

hostname = st.text_input("Hostname")
http_path = st.text_input("HTTP Path")
token = st.text_input("PAT Token", type="password")

if st.button("Conectar"):

    try:

        conn = sql.connect(
            server_hostname=hostname,
            http_path=http_path,
            access_token=token
        )

        cursor = conn.cursor()

        cursor.execute("SELECT current_timestamp()")

        result = cursor.fetchall()

        st.success("Conexión correcta")
        st.write(result)

    except Exception as e:
        st.error(str(e))
