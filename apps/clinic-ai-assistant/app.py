import json
import streamlit as st

from openai import OpenAI
from databricks import sql

# =====================================================
# CONFIG
# =====================================================

st.set_page_config(
    page_title="CityCare Clinic AI",
    page_icon="🏥",
    layout="wide"
)

st.title("🏥 CityCare Clinic AI")

# =====================================================
# FUNCIONES
# =====================================================

def get_intent(client, prompt):

    system_prompt = """
You are an appointment assistant.

Return ONLY JSON.

Examples:

User:
Necesito un cardiólogo

Response:
{
  "intent":"search_doctor",
  "specialty":"CARD"
}

User:
Busco un dermatólogo

Response:
{
  "intent":"search_doctor",
  "specialty":"DERM"
}

User:
Quiero un pediatra

Response:
{
  "intent":"search_doctor",
  "specialty":"PED"
}
"""

    response = client.responses.create(
        model="workspace.clinic_ai.clinic_ai_service_model",
        max_output_tokens=200,
        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": system_prompt
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": prompt
                    }
                ]
            }
        ]
    )

    return json.loads(response.output_text)


def create_answer(client, user_request, doctors):

    doctors_text = ""

    for d in doctors:

        doctors_text += (
            f"Doctor: {d[0]} {d[1]}\n"
            f"Date: {d[2]}\n"
            f"Time: {d[3]}\n\n"
        )

    prompt = f"""
User request:

{user_request}

Available appointments:

{doctors_text}

Respond naturally in Spanish.

Offer the available appointments and ask the user which one they prefer.
"""

    response = client.responses.create(
        model="workspace.clinic_ai.clinic_ai_service_model",
        max_output_tokens=400,
        input=prompt
    )

    return response.output_text


# =====================================================
# CONEXION IA
# =====================================================

ai_token = st.text_input(
    "Databricks AI Token",
    type="password"
)

# =====================================================
# CONEXION SQL
# =====================================================

hostname = st.text_input(
    "SQL Server Hostname"
)

http_path = st.text_input(
    "SQL HTTP Path"
)

sql_token = st.text_input(
    "SQL PAT Token",
    type="password"
)

# =====================================================
# CHAT
# =====================================================

prompt = st.chat_input(
    "¿Cómo puedo ayudarte?"
)

if (
    prompt
    and ai_token
    and hostname
    and http_path
    and sql_token
):

    try:

        # -----------------------------------------
        # LLM
        # -----------------------------------------

        client = OpenAI(
            api_key=ai_token,
            base_url="https://dbc-3bb54e54-c2b6.cloud.databricks.com/ai-gateway/mlflow/v1"
        )

        # -----------------------------------------
        # INTENCION
        # -----------------------------------------

        intent = get_intent(
            client,
            prompt
        )

        # -----------------------------------------
        # SQL
        # -----------------------------------------

        conn = sql.connect(
            server_hostname=hostname,
            http_path=http_path,
            access_token=sql_token
        )

        cursor = conn.cursor()

        if intent["intent"] == "search_doctor":

            specialty = intent["specialty"]

            cursor.execute(f"""
                SELECT
                    d.first_name,
                    d.last_name,
                    ds.appointment_date,
                    ds.start_time
                FROM clinic_ai.doctors d
                INNER JOIN clinic_ai.doctor_schedule ds
                    ON d.doctor_id = ds.doctor_id
                WHERE d.specialty_id = '{specialty}'
                  AND ds.slot_status = 'AVAILABLE'
                ORDER BY ds.appointment_date,
                         ds.start_time
                LIMIT 20
            """)
