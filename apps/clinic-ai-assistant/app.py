import json
import streamlit as st

from openai import OpenAI
from databricks import sql


# ======================================================
# CONFIG
# ======================================================

MODEL = "workspace.clinic_ai.clinic_ai_service_model"

st.set_page_config(
    page_title="Clinic AI",
    page_icon="🏥"
)

st.title("🏥 Clinic AI")


# ======================================================
# SESSION
# ======================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "available_slots" not in st.session_state:
    st.session_state.available_slots = []

if "selected_slot" not in st.session_state:
    st.session_state.selected_slot = None


# ======================================================
# TOOLS
# ======================================================

def get_specialties(cursor):

    cursor.execute("""
        SELECT
            specialty_id,
            specialty_name
        FROM workspace.clinic_ai.specialties
        WHERE active = true
        ORDER BY specialty_name
    """)

    rows = cursor.fetchall()

    return [
        {
            "specialty_id": row[0],
            "specialty_name": row[1]
        }
        for row in rows
    ]


def get_available_slots(cursor, specialty_id):

    cursor.execute("""
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
    """, {
        "specialty_id": specialty_id
    })

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


def select_slot(slot_id):

    for slot in st.session_state.available_slots:

        if slot["slot_id"] == slot_id:

            st.session_state.selected_slot = slot

            return {
                "status": "selected",
                "slot": slot
            }

    return {
        "status": "not_found"
    }


# ======================================================
# TOOL DEFINITIONS
# ======================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_specialties",
            "description": (
                "Retrieve the catalog of medical specialties "
                "available in the clinic."
            ),
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
                "Retrieve appointment slots for a specialty. "
                "The specialty_id must come from get_specialties."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "specialty_id": {
                        "type": "string",
                        "description": (
                            "The specialty_id returned by "
                            "get_specialties."
                        )
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
                        "type": "string",
                        "description": (
                            "The slot_id returned by "
                            "get_available_slots."
                        )
                    }
                },
                "required": [
                    "slot_id"
                ]
            }
        }
    }
]


# ======================================================
# EXECUTE TOOL
# ======================================================

def execute_tool(tool_call, cursor):

    function_name = tool_call.function.name

    arguments = json.loads(
        tool_call.function.arguments or "{}"
    )

    if function_name == "get_specialties":

        return get_specialties(cursor)

    if function_name == "get_available_slots":

        return get_available_slots(
            cursor,
            arguments["specialty_id"]
        )

    if function_name == "select_slot":

        return select_slot(
            arguments["slot_id"]
        )

    return {
        "error": f"Unknown tool {function_name}"
    }


# ======================================================
# CONNECTIONS
# ======================================================

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


# ======================================================
# CHAT HISTORY
# ======================================================

for msg in st.session_state.messages:

    if msg["role"] in ["user", "assistant"]:

        with st.chat_message(msg["role"]):
            st.write(msg["content"])


# ======================================================
# INPUT
# ======================================================

prompt = st.chat_input(
    "¿Cómo puedo ayudarte?"
)


# ======================================================
# MAIN
# ======================================================

if (
    prompt
    and ai_token
    and hostname
    and http_path
    and sql_token
):

    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt
        }
    )

    with st.chat_message("user"):
        st.write(prompt)

    try:

        # ==============================================
        # OPENAI CLIENT
        # ==============================================

        client = OpenAI(
            api_key=ai_token,
            base_url=(
                "https://dbc-3bb54e54-c2b6.cloud.databricks.com/"
                "ai-gateway/mlflow/v1"
            )
        )

        # ==============================================
        # SQL CONNECTION
        # ==============================================

        conn = sql.connect(
            server_hostname=hostname,
            http_path=http_path,
            access_token=sql_token
        )

        cursor = conn.cursor()

        # ==============================================
        # SYSTEM PROMPT
        # ==============================================

        system_prompt = """
You are a medical appointment assistant.

All medical specialties and appointment availability must
come from the tools provided by this application.

Do not use external search or external knowledge to determine
which specialties or appointments are available.

The clinic database is the only source of truth.

Rules:

1. Never invent specialties.

2. Always call get_specialties first when the user needs
   to choose a medical specialty.

3. Use only specialties returned by get_specialties.

4. Then call get_available_slots using the specialty_id
   returned by get_specialties.

5. Present available appointments in Spanish.

6. Never invent slot identifiers.

7. Use only slot_id values returned by
   get_available_slots.

8. If the user chooses a specific appointment,
   call select_slot.

9. After selecting a slot, confirm which slot was selected
   and ask the user if they want to proceed.

10. Answer the user in Spanish.
"""

        # ==============================================
        # MESSAGES
        # ==============================================

        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            *st.session_state.messages
        ]

        # ==============================================
        # AGENT LOOP
        # ==============================================

        while True:

            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto"
            )

            message = response.choices[0].message

            # ------------------------------------------
            # No tool call -> final answer
            # ------------------------------------------

            if not message.tool_calls:

                final_answer = message.content
                break

            # ------------------------------------------
            # Add assistant tool call to conversation
            # ------------------------------------------

            messages.append(
                {
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": (
                                    tool_call.function.arguments
                                )
                            }
                        }
                        for tool_call in message.tool_calls
                    ]
                }
            )

            # ------------------------------------------
            # Execute tools
            # ------------------------------------------

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

        # ==============================================
        # ASSISTANT RESPONSE
        # ==============================================

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
