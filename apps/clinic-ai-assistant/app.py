import json
import uuid
from datetime import datetime

import streamlit as st
from openai import OpenAI
from databricks import sql


# ============================================================
# CONFIG
# ============================================================

MODEL = "workspace.clinic_ai.clinic_ai_service_model"

st.set_page_config(
    page_title="Clinic AI",
    page_icon="🏥"
)

st.title("🏥 Clinic AI")


# ============================================================
# SESSION STATE
# ============================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "available_slots" not in st.session_state:
    st.session_state.available_slots = []

if "selected_slot" not in st.session_state:
    st.session_state.selected_slot = None

if "patient" not in st.session_state:
    st.session_state.patient = None


# ============================================================
# DEBUG
# ============================================================

DEBUG_SLOT = True


def debug_slot(label, value=None):
    if DEBUG_SLOT:
        if value is None:
            st.write(f"🔎 SLOT DEBUG: {label}")
        else:
            st.write(f"🔎 SLOT DEBUG: {label}", value)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_sql_connection():
    return sql.connect(
        server_hostname=st.session_state.sql_hostname,
        http_path=st.session_state.sql_http_path,
        access_token=st.session_state.sql_token
    )


# ============================================================
# TOOL 1 - FIND PATIENT
# ============================================================

def find_patient(first_name, last_name, birth_date=None):

    query = """
        SELECT
            patient_id,
            first_name,
            last_name,
            birth_date,
            gender,
            email,
            phone,
            preferred_language,
            insurance_id
        FROM workspace.clinic_ai.patients
        WHERE LOWER(first_name) = LOWER(%(first_name)s)
          AND LOWER(last_name) = LOWER(%(last_name)s)
          AND active = true
    """

    params = {
        "first_name": first_name,
        "last_name": last_name
    }

    if birth_date:
        query += """
          AND birth_date = %(birth_date)s
        """
        params["birth_date"] = birth_date

    query += """
        ORDER BY birth_date
    """

    conn = get_sql_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params)

            rows = cursor.fetchall()

            columns = [
                "patient_id",
                "first_name",
                "last_name",
                "birth_date",
                "gender",
                "email",
                "phone",
                "preferred_language",
                "insurance_id"
            ]

            patients = [
                dict(zip(columns, row))
                for row in rows
            ]

            if len(patients) == 1:
                st.session_state.patient = patients[0]

            return {
                "count": len(patients),
                "patients": patients
            }

    finally:
        conn.close()


# ============================================================
# TOOL 2 - GET SPECIALTIES
# ============================================================

def get_specialties():

    query = """
        SELECT
            specialty_id,
            specialty_name,
            description
        FROM workspace.clinic_ai.specialties
        WHERE active = true
        ORDER BY specialty_name
    """

    conn = get_sql_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute(query)

            rows = cursor.fetchall()

            columns = [
                "specialty_id",
                "specialty_name",
                "description"
            ]

            specialties = [
                dict(zip(columns, row))
                for row in rows
            ]

            return {
                "count": len(specialties),
                "specialties": specialties
            }

    finally:
        conn.close()


# ============================================================
# TOOL 3 - GET AVAILABLE SLOTS
# ============================================================

def get_available_slots(specialty_id):

    debug_slot("get_available_slots() called")
    debug_slot("specialty_id received", repr(specialty_id))
    debug_slot("specialty_id type", type(specialty_id).__name__)

    specialty_id = str(specialty_id).strip()

    # Workaround temporal para evitar el problema de binding
    # que tuvimos con valores como CARD.
    specialty_id_sql = specialty_id.replace("'", "''")

    query = f"""
        SELECT
            d.doctor_id,
            d.first_name,
            d.last_name,
            d.specialty_id,
            ds.slot_id,
            ds.appointment_date,
            ds.start_time,
            ds.end_time
        FROM workspace.clinic_ai.doctors d
        INNER JOIN workspace.clinic_ai.doctor_schedule ds
            ON d.doctor_id = ds.doctor_id
        WHERE d.specialty_id = '{specialty_id_sql}'
          AND d.active = true
          AND ds.slot_status = 'AVAILABLE'
        ORDER BY
            ds.appointment_date,
            ds.start_time,
            d.last_name,
            d.first_name
    """

    debug_slot("get_available_slots SQL", query)

    conn = get_sql_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute(query)

            rows = cursor.fetchall()

            columns = [
                "doctor_id",
                "first_name",
                "last_name",
                "specialty_id",
                "slot_id",
                "appointment_date",
                "start_time",
                "end_time"
            ]

            slots = [
                dict(zip(columns, row))
                for row in rows
            ]

            st.session_state.available_slots = slots

            debug_slot(
                "available_slots returned",
                slots
            )

            return {
                "count": len(slots),
                "slots": slots
            }

    finally:
        conn.close()


# ============================================================
# TOOL 4 - SELECT SLOT
# ============================================================

def select_slot(slot_id):

    debug_slot("select_slot() called")
    debug_slot("slot_id received", repr(slot_id))
    debug_slot("slot_id type", type(slot_id).__name__)
    debug_slot(
        "available_slots before selection",
        st.session_state.available_slots
    )

    try:
        option_number = int(str(slot_id).strip())
    except (TypeError, ValueError):
        option_number = None

    # --------------------------------------------------------
    # User selected the numbered option shown by the agent
    # --------------------------------------------------------

    if option_number is not None:

        index = option_number - 1

        if 0 <= index < len(st.session_state.available_slots):

            selected = st.session_state.available_slots[index]

            st.session_state.selected_slot = selected

            debug_slot(
                "OPTION NUMBER MAPPED TO SLOT",
                {
                    "option_number": option_number,
                    "slot": selected
                }
            )

            return {
                "status": "selected",
                "slot": selected
            }

        debug_slot(
            "OPTION NUMBER OUT OF RANGE",
            option_number
        )

        return {
            "status": "not_found",
            "message": "The selected option is not valid."
        }

    # --------------------------------------------------------
    # Internal slot_id
    # --------------------------------------------------------

    for slot in st.session_state.available_slots:

        if slot["slot_id"] == slot_id:

            st.session_state.selected_slot = slot

            debug_slot(
                "INTERNAL SLOT ID FOUND",
                slot
            )

            return {
                "status": "selected",
                "slot": slot
            }

    debug_slot(
        "slot NOT FOUND",
        repr(slot_id)
    )

    return {
        "status": "not_found"
    }


# ============================================================
# TOOL 5 - CREATE APPOINTMENT
# ============================================================

def create_appointment(
    appointment_reason=None,
    appointment_type=None,
    notes=None
):

    patient = st.session_state.patient
    selected_slot = st.session_state.selected_slot

    if not patient:
        return {
            "status": "error",
            "message": "No patient has been identified."
        }

    if not selected_slot:
        return {
            "status": "error",
            "message": "No appointment slot has been selected."
        }

    appointment_id = str(uuid.uuid4())

    now = datetime.now()

    query = """
        INSERT INTO workspace.clinic_ai.appointments (
            appointment_id,
            patient_id,
            slot_id,
            appointment_reason,
            appointment_type,
            status,
            notes,
            created_at,
            updated_at
        )
        VALUES (
            %(appointment_id)s,
            %(patient_id)s,
            %(slot_id)s,
            %(appointment_reason)s,
            %(appointment_type)s,
            %(status)s,
            %(notes)s,
            %(created_at)s,
            %(updated_at)s
        )
    """

    params = {
        "appointment_id": appointment_id,
        "patient_id": patient["patient_id"],
        "slot_id": selected_slot["slot_id"],
        "appointment_reason": appointment_reason,
        "appointment_type": appointment_type,
        "status": "CONFIRMED",
        "notes": notes,
        "created_at": now,
        "updated_at": now
    }

    conn = get_sql_connection()

    try:

        with conn.cursor() as cursor:
            cursor.execute(query, params)

        return {
            "status": "confirmed",
            "appointment": {
                "appointment_id": appointment_id,
                "patient": {
                    "first_name": patient["first_name"],
                    "last_name": patient["last_name"]
                },
                "doctor": {
                    "first_name": selected_slot["first_name"],
                    "last_name": selected_slot["last_name"]
                },
                "appointment_date": selected_slot["appointment_date"],
                "start_time": selected_slot["start_time"],
                "end_time": selected_slot["end_time"],
                "slot_id": selected_slot["slot_id"]
            }
        }

    finally:
        conn.close()


# ============================================================
# TOOL DEFINITIONS
# ============================================================

TOOLS = [

    {
        "type": "function",
        "function": {
            "name": "find_patient",
            "description": (
                "Find a patient using first name, last name "
                "and optionally date of birth."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "first_name": {
                        "type": "string"
                    },
                    "last_name": {
                        "type": "string"
                    },
                    "birth_date": {
                        "type": "string",
                        "description": "YYYY-MM-DD"
                    }
                },
                "required": [
                    "first_name",
                    "last_name"
                ]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "get_specialties",
            "description": (
                "Return the medical specialties available "
                "in the clinic."
            ),
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "get_available_slots",
            "description": (
                "Return available appointment slots for a "
                "given specialty_id."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "specialty_id": {
                        "type": "string"
                    }
                },
                "required": [
                    "specialty_id"
                ]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "select_slot",
            "description": (
                "Select an appointment slot. The slot_id argument "
                "should normally be the numeric option number shown "
                "to the user, such as '1', '2', or '3'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "slot_id": {
                        "type": "string"
                    }
                },
                "required": [
                    "slot_id"
                ]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "create_appointment",
            "description": (
                "Create and confirm the appointment for the "
                "currently identified patient and currently "
                "selected slot. Only call this after the user "
                "has explicitly confirmed the booking."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_reason": {
                        "type": "string"
                    },
                    "appointment_type": {
                        "type": "string"
                    },
                    "notes": {
                        "type": "string"
                    }
                }
            }
        }
    }
]


# ============================================================
# TOOL EXECUTION
# ============================================================

def execute_tool(name, arguments):

    args = json.loads(arguments) if isinstance(arguments, str) else arguments

    if name == "find_patient":
        return find_patient(**args)

    if name == "get_specialties":
        return get_specialties()

    if name == "get_available_slots":
        return get_available_slots(**args)

    if name == "select_slot":
        return select_slot(**args)

    if name == "create_appointment":
        return create_appointment(**args)

    return {
        "status": "error",
        "message": f"Unknown tool: {name}"
    }


# ============================================================
# SIDEBAR - CONNECTION
# ============================================================

with st.sidebar:

    st.header("Databricks connection")

    ai_token = st.text_input(
        "AI Token",
        type="password"
    )

    sql_hostname = st.text_input(
        "SQL Hostname"
    )

    sql_http_path = st.text_input(
        "SQL HTTP Path"
    )

    sql_token = st.text_input(
        "SQL Token",
        type="password"
    )

    st.session_state.sql_hostname = sql_hostname
    st.session_state.sql_http_path = sql_http_path
    st.session_state.sql_token = sql_token


# ============================================================
# OPENAI CLIENT
# ============================================================

client = OpenAI(
    api_key=ai_token,
    base_url=(
        "https://dbc-3bb54e54-c2b6.cloud.databricks.com/"
        "ai-gateway/mlflow/v1"
    )
)


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are a medical appointment assistant.

LANGUAGE:
Always communicate with the user in Spanish.
All user-facing messages must be in Spanish.
Do not switch to English unless the user explicitly asks to communicate in English.

The clinic database is the only source of truth.
Do not use external knowledge or external search.

PATIENT IDENTIFICATION:
1. Before helping the user search for an appointment, make sure the patient has been identified.
2. If the patient has not been identified, ask for first name and last name.
3. Once the user provides them, call find_patient.
4. If exactly one patient is found, consider the patient identified and continue.
5. If multiple patients have the same name, ask for the date of birth and call find_patient again.
6. If no patient is found, tell the user and ask them to check the information.
7. Never ask the user for patient_id.

APPOINTMENT SEARCH:
8. Once the patient is identified, use get_specialties.
9. Never invent specialties.
10. Use only specialties returned by the database.
11. Once the specialty is known, call get_available_slots.
12. Never invent appointment slots.
13. Use only slots returned by get_available_slots.
14. Present available appointments in Spanish.
15. When presenting available appointments, number them sequentially starting at 1.

SLOT SELECTION:
16. If the user chooses an appointment by its displayed option number, call select_slot using that exact option number as slot_id.
17. Do not convert the option number into an internal slot identifier yourself.
18. After select_slot succeeds, the slot is considered selected and remains selected until the user chooses a different slot or the appointment is created.
19. After select_slot succeeds, tell the user which appointment has been selected and ask explicitly whether they want to confirm the booking.
20. If a slot is already selected and the user explicitly confirms the booking, DO NOT call select_slot again. Call create_appointment directly.
21. A confirmation includes expressions such as: "sí", "si", "sí quiero", "confirmo", "adelante", "resérvala", "quiero esa", "de acuerdo", or equivalent wording.
22. When the user confirms an already selected slot, do not search for specialties again and do not search for available slots again unless the user explicitly asks to change the appointment.
23. Do not call create_appointment merely because the user selected a slot. The user must explicitly confirm the booking.
24. If the user says no, do not create the appointment.
25. If the user wants another appointment or asks to see more options, do not create the appointment.

CREATING THE APPOINTMENT:
26. Only call create_appointment after the user has explicitly confirmed that they want to book the currently selected appointment.
27. The selected patient and slot are managed internally by the application. Never ask the user for their IDs.
28. After create_appointment succeeds, tell the user that the appointment has been booked and provide the relevant appointment details.
29. Never display tool calls, function names, JSON, or internal execution syntax to the user.
"""


# ============================================================
# BUILD MESSAGES
# ============================================================

messages = [
    {
        "role": "system",
        "content": SYSTEM_PROMPT
    }
]


# Current patient context
if st.session_state.patient:

    patient = st.session_state.patient

    messages.append({
        "role": "system",
        "content": f"""
The currently identified patient is:
- First name: {patient["first_name"]}
- Last name: {patient["last_name"]}
- Birth date: {patient["birth_date"]}

The patient_id is internal and must never be requested from the user.
"""
    })


# Current selected slot context
if st.session_state.selected_slot:

    slot = st.session_state.selected_slot

    messages.append({
        "role": "system",
        "content": f"""
IMPORTANT:
There is currently a selected appointment slot.

If the user confirms the booking, call create_appointment directly.
Do not call select_slot again for this already selected slot.

The selected appointment is:
- Doctor: {slot["first_name"]} {slot["last_name"]}
- Date: {slot["appointment_date"]}
- Start time: {slot["start_time"]}
- End time: {slot["end_time"]}

The slot identifier is internal.
"""
    })


messages.extend(st.session_state.messages)


# ============================================================
# CHAT INPUT
# ============================================================

user_input = st.chat_input("¿En qué puedo ayudarte?")


# ============================================================
# PROCESS MESSAGE
# ============================================================

if user_input:

    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })

    messages.append({
        "role": "user",
        "content": user_input
    })

    try:

        while True:

            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto"
            )

            assistant_message = response.choices[0].message

            # ------------------------------------------------
            # No more tools -> final answer
            # ------------------------------------------------

            if not assistant_message.tool_calls:

                final_answer = assistant_message.content or ""

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": final_answer
                })

                st.chat_message("assistant").write(
                    final_answer
                )

                break

            # ------------------------------------------------
            # Assistant requested tools
            # ------------------------------------------------

            tool_calls_for_message = []

            for tool_call in assistant_message.tool_calls:

                tool_calls_for_message.append({
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments
                    }
                })

            messages.append({
                "role": "assistant",
                "content": assistant_message.content,
                "tool_calls": tool_calls_for_message
            })

            # ------------------------------------------------
            # Execute tools
            # ------------------------------------------------

            for tool_call in assistant_message.tool_calls:

                tool_name = tool_call.function.name
                raw_arguments = tool_call.function.arguments

                if DEBUG_SLOT and tool_name == "select_slot":

                    debug_slot(
                        "MODEL TOOL CALL",
                        {
                            "function": tool_name,
                            "raw_arguments": raw_arguments
                        }
                    )

                result = execute_tool(
                    tool_name,
                    raw_arguments
                )

                if DEBUG_SLOT and tool_name == "select_slot":

                    debug_slot(
                        "MODEL RECEIVES TOOL RESULT",
                        result
                    )

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(
                        result,
                        default=str,
                        ensure_ascii=False
                    )
                })

    except Exception as e:

        st.error(
            f"{type(e).__name__}: {str(e)}"
        )
