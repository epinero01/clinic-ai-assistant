import json
import uuid
import streamlit as st

from openai import OpenAI
from databricks import sql

# =========================================================
# CONFIG
# =========================================================

st.set_page_config(
    page_title="🏥 CityCare Clinic AI",
    page_icon="🏥",
    layout="wide"
)

st.title("🏥 CityCare Clinic AI")

# =========================================================
# SESSION
# =========================================================

if "candidate_slots" not in st.session_state:
    st.session_state.candidate_slots = []

if "selected_slot" not in st.session_state:
    st.session_state.selected_slot = None

# =========================================================
# TOOLS
# =========================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "find_slots",
            "description": "Find available appointment slots for a medical specialty",
            "parameters": {
                "type": "object",
                "properties": {
                    "specialty": {
                        "type": "string",
                        "description": "Medical specialty code"
                    }
                },
                "required": ["specialty"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "select_slot",
            "description": "Select one of the displayed appointment options",
            "parameters": {
                "type": "object",
                "properties": {
                    "option": {
                        "type": "integer"
                    }
                },
                "required": ["option"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Confirm and book the selected appointment",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]

# =========================================================
# CONNECTION
# =========================================================

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

# =========================================================
# MAIN
# =========================================================

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

        response = client.chat.completions.create(
            model="workspace.clinic_ai.clinic_ai_service_model",
            messages=[
                {
                    "role": "system",
                    "content": """
You are a medical appointment assistant.

Available actions:

1. find_slots
2. select_slot
3. book_appointment

If the user asks for a specialty,
call find_slots.

If the user chooses an option,
call select_slot.

If the user confirms,
call book_appointment.
"""
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            tools=TOOLS
        )

        message = response.choices[0].message

        if not message.tool_calls:

            st.write(message.content)

        else:

            tool_call = message.tool_calls[0]

            tool_name = tool_call.function.name
            args = json.loads(
                tool_call.function.arguments
            )

            # =====================================================
            # FIND SLOTS
            # =====================================================

            if tool_name == "find_slots":

                specialty = args["specialty"]
                st.write("Especialidad detectada:", specialty)

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

                rows = cursor.fetchall()

                st.session_state.candidate_slots = rows

                if len(rows) == 0:

                    st.warning(
                        "No hay disponibilidad."
                    )

                else:

                    answer = "Citas disponibles:\n\n"

                    for i, row in enumerate(rows, start=1):

                        answer += (
                            f"{i}. "
                            f"{row[1]} {row[2]} | "
                            f"{row[4]} | "
                            f"{row[5]}\n"
                        )

                    answer += (
                        "\nIndica el número de la opción."
                    )

                    st.write(answer)

            # =====================================================
            # SELECT SLOT
            # =====================================================

            elif tool_name == "select_slot":

                option = args["option"]

                selected = (
                    st.session_state.candidate_slots[
                        option - 1
                    ]
                )

                st.session_state.selected_slot = selected

                st.write(
                    f"""
Has seleccionado:

Doctor:
{selected[1]} {selected[2]}

Fecha:
{selected[4]}

Hora:
{selected[5]}

¿Confirmas la reserva?
"""
                )

            # =====================================================
            # BOOK
            # =====================================================

            elif tool_name == "book_appointment":

                slot = st.session_state.selected_slot

                if slot is None:

                    st.warning(
                        "No hay cita seleccionada."
                    )

                else:

                    appointment_id = str(
                        uuid.uuid4()
                    )

                    patient_id = "PAT001"

                    cursor.execute(f"""
                        INSERT INTO clinic_ai.appointments
                        VALUES (
                            '{appointment_id}',
                            '{patient_id}',
                            '{slot[3]}',
                            'Appointment booked by AI',
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
                        WHERE slot_id='{slot[3]}'
                    """)

                    st.success(
                        "✅ Cita reservada correctamente"
                    )

    except Exception as e:

        st.error(type(e).__name__)
        st.error(str(e))
        
