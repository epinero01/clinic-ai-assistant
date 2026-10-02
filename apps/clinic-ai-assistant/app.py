import json
import streamlit as st

from openai import OpenAI
from databricks import sql

# =====================================================
# CONFIG
# =====================================================

st.set_page_config(
    page_title="🏥 CityCare Clinic AI",
    page_icon="🏥",
    layout="wide"
)

st.title("🏥 CityCare Clinic AI")

# =====================================================
# FUNCIONES
# =====================================================

def get_intent(client, prompt):

    system_prompt = """
You are a medical routing assistant.

Return ONLY valid JSON.

Supported intents:
- search_doctor

Specialty mappings:

cardiologo -> CARD
cardiólogo -> CARD

dermatologo -> DERM
dermatólogo -> DERM

pediatra -> PED

endocrino -> ENDO

Example:

{
  "intent":"search_doctor",
  "specialty":"CARD"
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
    "Pregúntame algo..."
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

        intent = get_intent(
            client,
            prompt
        )

        st.subheader("Intent detectada")
        st.json(intent)

        # -----------------------------------------
        # SQL
        # -----------------------------------------

        conn = sql.connect(
            server_hostname=hostname,
            http_path=http_path,
            access_token=sql_token
        )

        cursor = conn.cursor()

        # -----------------------------------------
        # SEARCH DOCTOR
        # -----------------------------------------

        if intent["intent"] == "search_doctor":

            specialty = intent["specialty"]

            cursor.execute(f"""
                SELECT
                    first_name,
                    last_name,
                    subspecialty
                FROM clinic_ai.doctors
                WHERE specialty_id = '{specialty}'
                ORDER BY last_name
            """)

            doctors = cursor.fetchall()

            if not doctors:

                st.warning(
                    "No se encontraron médicos."
                )

            else:

                response_text = (
                    "He encontrado los siguientes especialistas:\n\n"
                )

                for doctor in doctors:

                    response_text += (
                        f"• {doctor[0]} {doctor[1]} "
                        f"({doctor[2]})\n"
                    )

                with st.chat_message("assistant"):
                    st.write(response_text)

    except Exception as e:

        st.error(type(e).__name__)
        st.error(str(e))
        
