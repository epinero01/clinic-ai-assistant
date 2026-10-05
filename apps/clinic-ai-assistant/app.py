import json
import uuid
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
# SESSION STATE
# =====================================================

if "step" not in st.session_state:
    st.session_state.step = "search"

if "available_slots" not in st.session_state:
    st.session_state.available_slots = []

if "selected_slot" not in st.session_state:
    st.session_state.selected_slot = None

# =====================================================
# LLM
# =====================================================

def get_intent(client, prompt):

    system_prompt = """
You are a medical booking assistant.

Return ONLY JSON.

Possible outputs:

{
  "intent":"search_doctor",
  "specialty":"CARD"
}

{
  "intent":"select_slot",
  "option":1
}

{
  "intent":"confirm_booking"
}

{
  "intent":"cancel_booking"
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
# CONNECTION DATA
# =====================================================

ai_token = st.text_input(
    "Databricks AI Token",
    type="password"
)

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

prompt = st.chat_input(
    "¿Cómo puedo ayudarte?"
)

# =====================================================
# MAIN
# =====================================================

if (
    prompt
    and ai_token
    and hostname
    and http_path
    and sql_token
):

    try:

        client = OpenAI(
            api_key=ai_token,
            base_url="https://dbc-3bb54e54-c2b6.cloud.databricks.com/ai-gateway/mlflow/v1"
        )

        conn = sql.connect(
            server_hostname=hostname,
            http_path=http_path,
            access_token=sql_token
        )

        cursor = conn.cursor()

        intent = get_intent(client, prompt)

        # =============================================
        # STEP 1
        # SEARCH
        # =============================================

        if (
            st.session_state.step == "search"
            and intent["intent"] == "search_doctor"
        ):

            specialty = intent["specialty"]

            cursor.execute(f"""
                SELECT
                    d.doctor_id,
                    d.first_name,
                    d.last_name,
                    ds.slot_id,
                    ds.appointment_date,
                    ds.start_time
                FROM clinic_ai.doctors d
                INNER JOIN clinic_ai.doctor_schedule ds
                    ON d.doctor_id = ds.doctor_id
                WHERE d.specialty_id = '{specialty}'
                  AND ds.slot_status = 'AVAILABLE'
                ORDER BY
                    ds.appointment_date,
                    ds.start_time
                LIMIT 10
            """)

            slots = cursor.fetchall()

            if len(slots) == 0:

                st.warning(
                    "No hay disponibilidad."
                )

            else:

                st.session_state.available_slots = slots
                st.session_state.step = "choose_slot"

                answer = (
                    "He encontrado estas citas:\n\n"
                )

                for i, slot in enumerate(slots, start=1):

                    answer += (
                        f"{i}. "
                        f"{slot[1]} {slot[2]} | "
                        f"{slot[4]} | "
                        f"{slot[5]}\n"
                    )

                answer += (
                    "\nIndica el número de la opción."
                )

                st.write(answer)

        # =============================================
        # STEP 2
        # SELECT SLOT
        # =============================================

        elif st.session_state.step == "choose_slot":

            try:

                option = int(prompt)

                selected = (
                    st.session_state.available_slots[
                        option - 1
                    ]
                )

                st.session_state.selected_slot = selected
                st.session_state.step = "confirm"

                st.write(
                    f"""
Has seleccionado:

Doctor:
{selected[1]} {selected[2]}

Fecha:
{selected[4]}

Hora:
{selected[5]}

¿Confirmas la reserva? (sí/no)
"""
                )

            except:

                st.warning(
                    "Escribe el número de una opción."
                )

        # =============================================
        # STEP 3
        # CONFIRM
        # =============================================

        elif st.session_state.step == "confirm":

            if prompt.lower() in [
                "si",
                "sí",
                "yes",
                "confirmar"
            \]:

                selected = st.session_state.selected_slot

                appointment_id = str(
                    uuid.uuid4()
                )

                # Para PoC
                patient_id = "PAT001"

                cursor.execute(f"""
                    INSERT INTO clinic_ai.appointments
                    VALUES (
                        '{appointment_id}',
                        '{patient_id}',
                        '{selected[3]}',
                        'Appointment booked from AI assistant',
                        'IN_PERSON',
                        'SCHEDULED',
                        NULL,
                        current_timestamp(),
                        current_timestamp()
                    )
                """)

                cursor.execute(f"""
                    UPDATE clinic_ai.doctor_schedule
                    SET
                        slot_status='BOOKED',
                        updated_at=current_timestamp()
                    WHERE slot_id='{selected[3]}'
                """)

                st.success(
                    "✅ Cita reservada correctamente"
                )

                st.session_state.step = "search"
                st.session_state.available_slots = []
                st.session_state.selected_slot = None

            else:

                st.info(
                    "Reserva cancelada."
                )

                st.session_state.step = "search"
                st.session_state.available_slots = []
                st.session_state.selected_slot = None

    except Exception as e:

        st.error(type(e).__name__)
        st.error(str(e))
