import streamlit as st
from openai import OpenAI

st.title("🏥 CityCare Clinic AI")

token = st.text_input(
    "Databricks AI Token",
    type="password"
)

prompt = st.chat_input(
    "¿Cómo puedo ayudarte?"
)

if token and prompt:

    try:

        client = OpenAI(
            api_key=token,
            base_url="https://dbc-3bb54e54-c2b6.cloud.databricks.com/ai-gateway/mlflow/v1"
        )

        response = client.responses.create(
            model="workspace.clinic_ai.clinic_ai_service_model",
            max_output_tokens=256,
            input=[
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

        st.write(response.output_text)

    except Exception as e:

        st.error(str(e))
