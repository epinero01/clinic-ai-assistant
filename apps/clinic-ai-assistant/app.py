import json
import uuid
from datetime import datetime

import streamlit as st
from openai import OpenAI
from databricks import sql


MODEL = "workspace.clinic_ai.clinic_ai_service_model"


# ============================================================
# PAGE
# ============================================================

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
# SLOT DEBUG
# ============================================================

DEBUG_SLOT = True


def debug_slot(label, value=None):

    if DEBUG_SLOT:

        if value is None:
            st.write(f"🔎 SLOT DEBUG: {label}")
        else:
            st.write(f"🔎 SLOT DEBUG: {label}", value)


# ============================================================
# PATIENT
# ============================================================

def find_patient(cursor, first_name, last_name, birth_date=None):

    query = """
        SELECT
            patient_id,
            first_name,
            last_name,
            birth_date
        FROM workspace.clinic_ai.patients
        WHERE active = true
          AND LOWER(first_name) = LOWER(%(first_name)s)
          AND LOWER(last_name) = LOWER(%(last_name)s)
    """

    params = {
        "first_name": first_name.strip(),
        "last_name": last_name.strip()
    }

    if birth_date:

        query += """
          AND birth_date = %(birth_date)s
        """

        params["birth_date"] = birth_date

    query += """
        ORDER BY birth_date
    """

    cursor.execute(
        query,
        params
    )

    rows = cursor.fetchall()

    if not rows:

        st.session_state.patient = None

        return {
            "status": "not_found",
            "message": "No active patient was found with those details."
        }

    if len(rows) > 1:

        st.session_state.patient = None

        return {
            "status": "multiple_matches",
            "patients": [
                {
                    "first_name": row[1],
                    "last_name": row[2],
                    "birth_date": str(row[3])
                }
                for row in rows
            ]
        }

    row = rows[0]

    patient = {
        "patient_id": row[0],
        "first_name": row[1],
        "last_name": row[2],
        "birth_date": str(row[3])
    }

    st.session_state.patient = patient

    return {
        "status": "found",
        "patient": patient
    }


# ============================================================
# SPECIALTIES
# ============================================================

def get_specialties(cursor):

    query = """
        SELECT
            specialty_id,
            specialty_name
        FROM workspace.clinic_ai.specialties
        WHERE active = true
        ORDER BY specialty_name
    """

    cursor.execute(query)

    rows = cursor.fetchall()

    result = [
        {
            "specialty_id": row[0],
            "specialty_name": row[1]
        }
        for row in rows
    ]

    return result


# ============================================================
# AVAILABLE SLOTS
# ============================================================

def get_available_slots(cursor, specialty_id):

    query = """
        SELECT
            d.doctor_id,
            d.first_name,
            d.last_name,
            ds.slot_id,
            ds.appointment_date,
            ds.start_time
        FROM workspace.clinic_ai.doctors d
        INNER JOIN workspace.clinic_ai.doctor_schedule ds
            ON d.doctor_id = ds.doctor_id
        WHERE d.specialty_id = %(specialty_id)s
          AND d.active = true
          AND ds.slot_status = 'AVAILABLE'
        ORDER BY
            ds.appointment_date,
            ds.start_time
        LIMIT 20
    """

    params = {
        "specialty_id": specialty_id
    }

    cursor.execute(
        query,
        params
    )

    rows = cursor.fetchall()

    result = [
        {
            "doctor_id": row[0],
            "doctor_name": f"{row[1]} {row[2]}",
            "slot_id": row[3],
            "appointment_date": str(row[4]),
            "start_time": row[5]
        }
        for row in rows
    ]

    st.session_state.available_slots = result

    return result


# ============================================================
# SELECT SLOT
# ============================================================

def select_slot(slot_id):

    debug_slot("select_slot() called")

    debug_slot(
        "slot_id received from model",
        repr(slot_id)
    )

    debug_slot(
        "available_slots",
        st.session_state.available_slots
    )

    for slot in st.session_state.available_slots:

        if slot["slot_id"] == slot_id:

            st.session_state.selected_slot = slot

            debug_slot(
                "✅ SLOT FOUND",
                slot
            )

            return {
                "status": "selected",
                "slot": slot
            }

    debug_slot(
        "❌ SLOT NOT FOUND",
        repr(slot_id)
    )

    return {
        "status": "not_found"
    }


# ============================================================
# CREATE APPOINTMENT
# ============================================================

def create_appointment(cursor):

    patient = st.session_state.patient
    slot = st.session_state.selected_slot

    if not patient:

        return {
            "status": "error",
            "message": "No patient has been identified."
        }

    if not slot:

        return {
            "status": "error",
            "message": "No appointment slot has been selected."
        }

    appointment_id = str(uuid.uuid4())

    now = datetime.now()

    params = {
        "appointment_id": appointment_id,
        "patient_id": patient["patient_id"],
        "slot_id": slot["slot_id"],
        "appointment_reason": None,
        "appointment_type": "STANDARD",
        "status": "CONFIRMED",
        "notes": None,
        "created_at": now,
        "updated_at": now
    }

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

    cursor.execute(
        query,
        params
    )

    result = {
        "status": "created",
        "appointment_id": appointment_id,
        "patient": {
            "first_name": patient["first_name"],
            "last_name": patient["last_name"]
        },
        "slot": slot
    }

    return result


# ============================================================
# TOOLS
# ============================================================

TOOLS = [

    {
        "type": "function",
        "function": {
            "name": "find_patient",
            "description": (
                "Find an active patient in the clinic database "
                "using first name and last name. "
                "If multiple patients have the same name, "
                "birth date can be used to identify the correct patient."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "first_name": {
                        "type": "string",
                        "description": "Patient's first name."
                    },
                    "last_name": {
                        "type": "string",
                        "description": "Patient's last name."
                    },
                    "birth_date": {
                        "type": "string",
                        "description": (
                            "Patient's birth date in YYYY-MM-DD format. "
                            "Only use when needed to distinguish "
                            "between multiple patients."
                        )
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
            "description": "Retrieve the catalog of medical specialties.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "get_available_slots",
            "description": (
                "Retrieve available appointment slots "
                "for a medical specialty."
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
                "Select one appointment slot from the slots "
                "previously returned to the user. "
                "The slot_id must be the internal slot_id "
                "returned by get_available_slots."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "slot_id": {
                        "type": "string",
                        "description": (
                            "Internal slot_id returned by "
                            "get_available_slots."
                        )
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
                "Create the appointment using the patient and "
                "slot already selected internally. "
                "Only call this after the user has explicitly "
                "confirmed the selected appointment."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]


# ============================================================
# TOOL EXECUTION
# ============================================================

def execute_tool(tool_call, cursor):

    function_name = tool_call.function.name

    arguments_raw = tool_call.function.arguments or "{}"

    if function_name == "select_slot":

        debug_slot(
            "MODEL TOOL CALL",
            {
                "function": function_name,
                "raw_arguments": arguments_raw
            }
        )

    arguments = json.loads(
        arguments_raw
    )

    if function_name == "find_patient":

        result = find_patient(
            cursor,
            arguments["first_name"],
            arguments["last_name"],
            arguments.get("birth_date")
        )

    elif function_name == "get_specialties":

        result = get_specialties(cursor)

    elif function_name == "get_available_slots":

        result = get_available_slots(
            cursor,
            arguments["specialty_id"]
        )

    elif function_name == "select_slot":

        result = select_slot(
            arguments["slot_id"]
        )

    elif function_name == "create_appointment":

        result = create_appointment(
            cursor
        )

    else:

        result = {
            "error": f"Unknown tool {function_name}"
        }

    if function_name == "select_slot":

        debug_slot(
            "MODEL RECEIVES TOOL RESULT",
            result
        )

    return result


# ============================================================
# CONNECTION PARAMETERS
# ============================================================

ai_token = st.text_input(
    "AI Token",
    type="password"
)

hostname = st.text_input(
    "SQL Hostname"
)

http_path = st.text_input(
    "SQL HTTP Path"
)

sql_token = st.text_input(
    "SQL Token",
    type="password"
)


# ============================================================
# CHAT HISTORY
# ============================================================

for msg in st.session_state.messages:

    if msg["role"] in ["user", "assistant"]:

        with st.chat_message(msg["role"]):
            st.write(msg["content"])


prompt = st.chat_input(
    "¿Cómo puedo ayudarte?"
)


# ============================================================
# MAIN AGENT LOOP
# ============================================================

if prompt and ai_token and hostname and http_path and sql_token:

    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt
        }
    )

    with st.chat_message("user"):
        st.write(prompt)

    try:

        client = OpenAI(
            api_key=ai_token,
            base_url=(
                "https://dbc-3bb54e54-c2b6.cloud.databricks.com/"
                "ai-gateway/mlflow/v1"
            )
        )

        conn = sql.connect(
            server_hostname=hostname,
            http_path=http_path,
            access_token=sql_token
        )

        cursor = conn.cursor()


        # ====================================================
        # SYSTEM PROMPT
        # ====================================================

        system_prompt = """
You are a medical appointment assistant.

The clinic database is the only source of truth.
Do not use external knowledge or external search.

PATIENT IDENTIFICATION:

1. Before helping the user search for an appointment,
   make sure the patient has been identified.

2. If the patient has not been identified,
   ask for first name and last name.

3. Once the user provides them, call find_patient.

4. If exactly one patient is found, consider the patient
   identified and continue.

5. If multiple patients are found with the same name,
   ask for the date of birth and call find_patient again.

6. If no patient is found, tell the user and ask them
   to check the information.

7. Never ask the user for patient_id.

APPOINTMENT SEARCH:

8. Once the patient is identified, use get_specialties.

9. Never invent specialties.

10. Use only specialties returned by the database.

11. Once the specialty is known, call get_available_slots.

12. Never invent appointment slots.

13. Use only slots returned by get_available_slots.

14. Present available appointments in Spanish.

15. Do not expose technical identifiers to the user.

SLOT SELECTION:

16. If the user chooses one of the available appointments,
    call select_slot using the exact internal slot_id
    returned by get_available_slots.

17. After select_slot succeeds, the slot is considered
    selected and remains selected until the user chooses
    a different slot or the appointment is created.

18. After select_slot succeeds, tell the user which
    appointment has been selected and ask explicitly
    whether they want to confirm the booking.

19. If a slot is already selected and the user explicitly
    confirms the booking, DO NOT call select_slot again.
    Call create_appointment directly.

20. A confirmation after a selected slot includes
    expressions such as:
    "sí", "si", "sí quiero", "confirmo", "adelante",
    "resérvala", "quiero esa", "de acuerdo", or
    equivalent wording.

21. When the user confirms an already selected slot,
    do not search for specialties again and do not
    search for available slots again unless the user
    explicitly asks to change the appointment.

22. Do not call create_appointment merely because the
    user selected a slot. The user must explicitly
    confirm the booking.

23. If the user says no, do not create an appointment.

24. If the user wants another appointment or asks to see
    more options, do not create the appointment. The user
    must select another slot first.

CREATING THE APPOINTMENT:

25. Only call create_appointment after the user has
    explicitly confirmed that they want to book the
    currently selected appointment.

26. The selected patient and slot are managed internally
    by the application. Never ask the user for their IDs.

27. After create_appointment succeeds, tell the user that
    the appointment has been booked and provide the
    relevant appointment details.

28. Never display tool calls, function names, JSON,
    or internal execution syntax to the user.
"""


        messages = [
            {
                "role": "system",
                "content": system_prompt
            }
        ]


        # ====================================================
        # CURRENT PATIENT CONTEXT
        # ====================================================

        if st.session_state.patient:

            patient = st.session_state.patient

            messages.append(
                {
                    "role": "system",
                    "content": (
                        "The currently identified patient is: "
                        f"{patient['first_name']} "
                        f"{patient['last_name']}, "
                        f"birth date {patient['birth_date']}. "
                        "The patient_id is internal and must "
                        "never be requested from the user."
                    )
                }
            )


        # ====================================================
        # CURRENT SELECTED SLOT CONTEXT
        # ====================================================

        if st.session_state.selected_slot:

            slot = st.session_state.selected_slot

            messages.append(
                {
                    "role": "system",
                    "content": (
                        "IMPORTANT: There is currently a selected "
                        "appointment slot. If the user confirms "
                        "the booking, call create_appointment "
                        "directly. Do not call select_slot again "
                        "for this already selected slot. "
                        f"The selected appointment is "
                        f"{slot['doctor_name']} on "
                        f"{slot['appointment_date']} at "
                        f"{slot['start_time']}. "
                        "The slot identifier is internal."
                    )
                }
            )


        # ====================================================
        # CONVERSATION HISTORY
        # ====================================================

        messages.extend(
            st.session_state.messages
        )


        # ====================================================
        # AGENT / TOOL LOOP
        # ====================================================

        while True:

            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto"
            )

            message = response.choices[0].message


            # ------------------------------------------------
            # NO TOOL CALL
            # ------------------------------------------------

            if not message.tool_calls:

                final_answer = message.content

                break


            # ------------------------------------------------
            # ASSISTANT TOOL CALL
            # ------------------------------------------------

            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in message.tool_calls
                    ]
                }
            )


            # ------------------------------------------------
            # EXECUTE TOOLS
            # ------------------------------------------------

            for tool_call in message.tool_calls:

                tool_result = execute_tool(
                    tool_call,
                    cursor
                )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(
                            tool_result,
                            ensure_ascii=False
                        )
                    }
                )


        # ====================================================
        # SAVE FINAL ANSWER
        # ====================================================

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": final_answer
            }
        )

        with st.chat_message("assistant"):
            st.write(final_answer)


    except Exception as e:

        st.error(type(e).__name__)
        st.error(str(e))
        
