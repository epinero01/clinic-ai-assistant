import streamlit as st

st.title("🏥 CityCare Clinic")

try:
    df = spark.sql("""
        SELECT *
        FROM clinic_ai.specialties
        ORDER BY specialty_name
    """).toPandas()

    st.success("Conexión OK")
    st.dataframe(df)

except Exception as e:
    st.error(str(e))
