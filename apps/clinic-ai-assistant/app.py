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
# DEBUG
# ============================================================

DEBUG = True


def debug(label, value=None):

    if DEBUG:

        if value is None:
            st.write(f"🔎 DEBUG: {label}")
        else:
            st.write(f"🔎 DEBUG: {label}", value)


# ============================================================
# PATIENT
# ============================================================

def find_patient(cursor, first_name, last_name, birth_date=None):

    debug("find_patient() called")

    debug("first_name", repr(first_name))
    debug("last_name", repr(last_name))
    debug("birth_date", repr(birth_date))

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

    debug("find_patient SQL", query)
    debug("find_patient params", params)

    try:

        cursor.execute(
            query,
            params
        )

        debug("find_patient SQL execute: OK")

    except Exception as e:

        debug(
            "find_patient SQL execute: ERROR",
            f"{type(e).__name__}: {str(e)}"
        )

        raise

    try:

        rows = cursor.fetchall()

        debug("find_patient rows", rows)

    except Exception as e:

        debug(
            "find_patient fetchall: ERROR",
            f"{type(e).__name__}: {str(e)}"
        )

        raise

    if not rows:

        debug("find_patient: no rows found")

        st.session_state.patient = None

        return {
            "status": "not_found",
            "message": "No active patient was found with those details."
        }

    if len(rows) > 1:

        debug(
            "find_patient: multiple rows found",
            len(rows)
        )

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

    debug("find_patient selected row", row)

    patient = {
        "patient_id": row[0],
        "first_name": row[1],
        "last_name": row[2],
        "birth_date": str(row[3])
    }

    debug("patient object", patient)

    st.session_state.patient = patient

    debug(
        "session_state.patient after find_patient",
        st.session_state.patient
    )

    return {
        "status": "found",
        "patient": patient
    }


# ============================================================
# SPECIALTIES
# ============================================================

def get_specialties(cursor):

    debug("get_specialties() called")

    query = """
        SELECT
            specialty_id,
            specialty_name
        FROM workspace.clinic_ai.specialties
        WHERE active = true
        ORDER BY specialty_name
    """

    debug("get_specialties SQL", query)

    try:

        cursor.execute(query)

        debug("get_specialties SQL execute: OK")

    except Exception as e:

        debug(
            "get_specialties SQL execute: ERROR",
            f"{type(e).__name__}: {str(e)}"
        )

        raise

    try:

        rows = cursor.fetchall()

        debug("get_specialties rows", rows)

    except Exception as e:

        debug(
            "get_specialties fetchall: ERROR",
            f"{type(e).__name__}: {str(e)}"
        )

        raise

    result = [
        {
            "specialty_id": row[0],
            "specialty_name": row[1]
        }
        for row in rows
    ]

    debug("get_specialties result", result)

    return result


# ============================================================
# AVAILABLE SLOTS
# ============================================================

def get_available_slots(cursor, specialty_id):

    debug("get_available_slots() called")

    debug(
        "specialty_id",
        repr(specialty_id)
    )

    debug(
        "specialty_id type",
        type(specialty_id).__name__
    )

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

    debug(
        "get_available_slots SQL",
        query
    )

    debug(
        "get_available_slots params",
        params
    )

    try:

        cursor.execute(
            query,
            params
        )

        debug(
            "get_available_slots SQL execute: OK"
        )

    except Exception as e:

        debug(
            "get_available_slots SQL execute: ERROR",
            f"{type(e).__name__}: {str(e)}"
        )

        raise

    try:

        rows = cursor.fetchall()

        debug(
            "get_available_slots rows",
            rows
        )

    except Exception as e:

        debug(
            "get_available_slots fetchall: ERROR",
            f"{type(e).__name__}: {str(e)}"
        )

        raise

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

    debug(
        "get_available_slots result",
        result
    )

    st.session_state.available_slots = result

    debug(
        "session_state.available_slots",
        st.session_state.available_slots
    )

    return result


# ============================================================
# SELECT SLOT
# ============================================================

def select_slot(slot_id):

    debug("select_slot() called")

    debug(
        "slot_id received",
        repr(slot_id)
    )

    debug(
        "slot_id type",
        type(slot_id).__name__
    )

    debug(
        "available_slots before selection",
        st.session_state.available_slots
    )

    for slot in st.session_state.available_slots:

        if slot["slot_id"] == slot_id:

            st.session_state.selected_slot = slot

            debug(
                "slot FOUND and selected",
                slot
            )

            debug(
                "session_state.selected_slot",
                st.session_state.selected_slot
            )

            return {
                "status": "selected",
                "slot": slot
            }

    debug(
        "slot NOT FOUND",
        repr(slot_id)
    )

    return {
        "status": "not_found"
    }


# ============================================================
# CREATE APPOINTMENT
# ============================================================

def create_appointment(cursor):

    debug("create_appointment() called")

    patient = st.session_state.patient
    slot = st.session_state.selected_slot

    debug(
        "patient from session_state",
        patient
    )

    debug(
        "selected_slot from session_state",
        slot
    )

    if patient:

        debug(
            "patient_id",
            repr(patient.get("patient_id"))
        )

        debug(
            "patient_id type",
            type(patient.get("patient_id")).__name__
        )

    if slot:

        debug(
            "slot_id",
            repr(slot.get("slot_id"))
        )

        debug(
            "slot_id type",
            type(slot.get("slot_id")).__name__
        )

    if not patient:

        debug(
            "create_appointment STOP: no patient"
        )

        return {
            "status": "error",
            "message": "No patient has been identified."
        }

    if not slot:

        debug(
            "create_appointment STOP: no slot"
        )

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

    debug(
        "create_appointment params",
        params
    )

    debug(
        "create_appointment parameter types",
        {
            key: type(value).__name__
            for key, value in params.items()
        }
    )

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

    debug(
        "create_appointment SQL",
        query
    )

    try:

        cursor.execute(
            query,
            params
        )

        debug(
            "create_appointment SQL execute: OK"
        )

    except Exception as e:

        debug(
            "create_appointment SQL execute: ERROR",
            f"{type(e).__name__}: {str(e)}"
        )

        raise

    result = {
        "status": "created",
        "appointment_id": appointment_id,
        "patient": {
            "first_name": patient["first_name"],
            "last_name": patient["last_name"]
        },
        "slot": slot
    }

    debug(
        "create_appointment result",
        result
    )

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
                "previously returned to the user."
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
                "Create the appointment after the patient has "
                "selected a slot and explicitly confirmed that "
                "they want to book it. "
                "The patient and selected slot are maintained "
                "internally by the application."
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

    debug(
        "TOOL CALL",
        function_name
    )

    debug(
        "TOOL CALL raw arguments",
        arguments_raw
    )

    try:

        arguments = json.loads(
            arguments_raw
        )

    except Exception as e:

        debug(
            "TOOL ARGUMENT JSON ERROR",
            f"{type(e).__name__}: {str(e)}"
        )

        raise

    debug(
        "TOOL CALL parsed arguments",
        arguments
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

    debug(
        f"TOOL RESULT: {function_name}",
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

        debug(
            "NEW USER PROMPT",
            prompt
        )

        debug(
            "SESSION STATE BEFORE AGENT",
            {
                "patient": st.session_state.patient,
                "selected_slot": st.session_state.selected_slot,
                "available_slots_count": len(
                    st.session_state.available_slots
                ),
                "messages_count": len(
                    st.session_state.messages
                )
            }
        )

        client = OpenAI(
            api_key=ai_token,
            base_url=(
                "https://dbc-3bb54e54-c2b6.cloud.databricks.com/"
                "ai-gateway/mlflow/v1"
            )
        )

        debug(
            "OpenAI client created"
        )

        conn = sql.connect(
            server_hostname=hostname,
            http_path=http_path,
            access_token=sql_token
        )

        debug(
            "SQL connection created"
        )

        cursor = conn.cursor()

        debug(
            "SQL cursor created"
        )


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

15. Do not expose technical identifiers unless necessary.

SLOT SELECTION:

16. If the user chooses an available appointment,
    call select_slot.

17. After select_slot, tell the user which appointment
    has been selected and ask explicitly whether they
    want to confirm the booking.

CREATING THE APPOINTMENT:

18. Only call create_appointment after the user has
    explicitly confirmed that they want to book the
    selected appointment.

19. A positive confirmation includes expressions such as:
    "sí", "si", "sí quiero", "confirmo", "adelante",
    "resérvala", "quiero esa", or equivalent wording.

20. Do not call create_appointment merely because the
    user selected a slot.

21. If the user says no, do not create an appointment.

22. If the user wants another appointment or asks to see
    more options, do not create the appointment.

23. The selected patient and slot are managed internally
    by the application. Never invent their identifiers.

24. After create_appointment succeeds, tell the user that
    the appointment has been booked and provide the
    relevant appointment details.

25. Never display tool calls, function names, JSON,
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

            debug(
                "PATIENT CONTEXT SENT TO MODEL",
                {
                    "first_name": patient["first_name"],
                    "last_name": patient["last_name"],
                    "birth_date": patient["birth_date"]
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
                        "There is currently a selected appointment "
                        "slot: "
                        f"{slot['doctor_name']} on "
                        f"{slot['appointment_date']} at "
                        f"{slot['start_time']}. "
                        "The slot identifier is internal."
                    )
                }
            )

            debug(
                "SELECTED SLOT CONTEXT SENT TO MODEL",
                {
                    "doctor_name": slot["doctor_name"],
                    "appointment_date": slot["appointment_date"],
                    "start_time": slot["start_time"]
                }
            )


        # ====================================================
        # CONVERSATION HISTORY
        # ====================================================

        messages.extend(
            st.session_state.messages
        )

        debug(
            "MESSAGES SENT TO MODEL",
            messages
        )


        # ====================================================
        # AGENT / TOOL LOOP
        # ====================================================

        loop_number = 0

        while True:

            loop_number += 1

            debug(
                f"AGENT LOOP #{loop_number}"
            )

            debug(
                "CALLING MODEL"
            )

            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto"
            )

            debug(
                "MODEL RESPONSE RECEIVED"
            )

            message = response.choices[0].message

            debug(
                "MODEL MESSAGE CONTENT",
                message.content
            )

            debug(
                "MODEL TOOL CALL COUNT",
                len(message.tool_calls or [])
            )


            # ------------------------------------------------
            # NO TOOL CALL
            # ------------------------------------------------

            if not message.tool_calls:

                final_answer = message.content

                debug(
                    "FINAL MODEL ANSWER",
                    final_answer
                )

                break


            # ------------------------------------------------
            # ASSISTANT TOOL CALL
            # ------------------------------------------------

            debug(
                "MODEL REQUESTED TOOLS",
                [
                    {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                    for tc in message.tool_calls
                ]
            )

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

                debug(
                    "EXECUTING TOOL",
                    tool_call.function.name
                )

                tool_result = execute_tool(
                    tool_call,
                    cursor
                )

                debug(
                    "TOOL RESULT TO MODEL",
                    tool_result
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

                debug(
                    "TOOL RESULT APPENDED TO MODEL MESSAGES"
                )


        # ====================================================
        # FINAL STATE
        # ====================================================

        debug(
            "FINAL SESSION STATE",
            {
                "patient": st.session_state.patient,
                "selected_slot": st.session_state.selected_slot,
                "available_slots_count": len(
                    st.session_state.available_slots
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

        debug(
            "GLOBAL ERROR TYPE",
            type(e).__name__
        )

        debug(
            "GLOBAL ERROR MESSAGE",
            str(e)
        )

        st.error(type(e).__name__)
        st.error(str(e))
        
