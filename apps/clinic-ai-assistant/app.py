import streamlit as st
import pandas as pd
import uuid

from databricks import sql

st.set_page_config(
    page_title="CityCare Clinic",
    page_icon="🏥",
    layout="wide"
)

st.title("🏥 CityCare Clinic")

# ==================================================
# CONEXIÓN
# ==================================================

hostname = st.text_input("Server Hostname")
http_path = st.text_input("HTTP Path")
token = st.text_input("PAT Token", type="password")

if hostname and http_path and token:

    try:

        conn = sql.connect(
            server_hostname=hostname,
            http_path=http_path,
            access_token=token
        )

        cursor = conn.cursor()

        st.success("✅ Conexión correcta")

        # ==================================================
        # ESPECIALIDADES
        # ==================================================

        cursor.execute("""
            SELECT
                specialty_id,
                specialty_name
            FROM clinic_ai.specialties
            ORDER BY specialty_name
        """)

        specialties = pd.DataFrame(
            cursor.fetchall(),
            columns=[
                "specialty_id",
                "specialty_name"
            ]
        )

        selected_specialty = st.selectbox(
            "Especialidad",
            specialties["specialty_name"]
        )

        specialty_id = specialties.loc[
            specialties["specialty_name"] == selected_specialty,
            "specialty_id"
        ].iloc[0]

        # ==================================================
        # MÉDICOS
        # ==================================================

        cursor.execute(f"""
            SELECT
                doctor_id,
                first_name,
                last_name,
                subspecialty
            FROM clinic_ai.doctors
            WHERE specialty_id = '{specialty_id}'
            ORDER BY last_name
        """)

        doctors = pd.DataFrame(
            cursor.fetchall(),
            columns=[
                "doctor_id",
                "first_name",
                "last_name",
                "subspecialty"
            ]
        )

        doctors["display_name"] = (
            doctors["first_name"]
            + " "
            + doctors["last_name"]
            + " - "
            + doctors["subspecialty"]
        )

        selected_doctor = st.selectbox(
            "Médico",
            doctors["display_name"]
        )

        doctor_id = doctors.loc[
            doctors["display_name"] == selected_doctor,
            "doctor_id"
        ].iloc[0]

        # ==================================================
        # SLOTS DISPONIBLES
        # ==================================================

        cursor.execute(f"""
            SELECT
                slot_id,
                appointment_date,
                start_time
            FROM clinic_ai.doctor_schedule
            WHERE doctor_id = '{doctor_id}'
              AND slot_status = 'AVAILABLE'
            ORDER BY appointment_date,
                     start_time
            LIMIT 20
        """)

        slots = pd.DataFrame(
            cursor.fetchall(),
            columns=[
                "slot_id",
                "appointment_date",
                "start_time"
            ]
        )

        if len(slots) == 0:

            st.warning("No hay huecos disponibles.")

        else:

            slots["display_slot"] = (
                slots["appointment_date"].astype(str)
                + " "
                + slots["start_time"]
            )

            selected_slot = st.selectbox(
                "Horario",
                slots["display_slot"]
            )

            slot_id = slots.loc[
                slots["display_slot"] == selected_slot,
                "slot_id"
            ].iloc[0]

            # ==================================================
            # PACIENTES
            # ==================================================

            cursor.execute("""
                SELECT
                    patient_id,
                    first_name,
                    last_name
                FROM clinic_ai.patients
                ORDER BY last_name
            """)

            patients = pd.DataFrame(
                cursor.fetchall(),
                columns=[
                    "patient_id",
                    "first_name",
                    "last_name"
                ]
            )

            patients["display_name"] = (
                patients["first_name"]
                + " "
                + patients["last_name"]
            )

            selected_patient = st.selectbox(
                "Paciente",
                patients["display_name"]
            )

            patient_id = patients.loc[
                patients["display_name"] == selected_patient,
                "patient_id"
            ].iloc[0]

            reason = st.text_area(
                "Motivo de la consulta"
            )

            # ==================================================
            # RESERVA
            # ==================================================

            if st.button("Reservar cita"):

                appointment_id = str(uuid.uuid4())

                try:

                    cursor.execute(f"""
                        INSERT INTO clinic_ai.appointments
                        VALUES (
                            '{appointment_id}',
                            '{patient_id}',
                            '{slot_id}',
                            '{reason}',
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
                            slot_status = 'BOOKED',
                            updated_at = current_timestamp()
                        WHERE slot_id = '{slot_id}'
                    """)

                    st.success("✅ Cita reservada correctamente")

                    st.json({
                        "appointment_id": appointment_id,
                        "patient_id": patient_id,
                        "doctor_id": doctor_id,
                        "slot_id": slot_id,
                        "status": "SCHEDULED"
                    })

                except Exception as booking_error:

                    st.error("Error al reservar la cita")
                    st.error(str(booking_error))

        # ==================================================
        # ÚLTIMAS CITAS
        # ==================================================

        st.divider()

        st.subheader("Últimas citas registradas")

        try:

            cursor.execute("""
                SELECT
                    appointment_id,
                    patient_id,
                    slot_id,
                    status
                FROM clinic_ai.appointments
                ORDER BY created_at DESC
                LIMIT 20
            """)

            appointments = pd.DataFrame(
                cursor.fetchall(),
                columns=[
                    "appointment_id",
                    "patient_id",
                    "slot_id",
                    "status"
                ]
            )

            st.dataframe(
                appointments,
                use_container_width=True
            )

        except:
            pass

    except Exception as e:

        st.error(type(e).__name__)
        st.error(str(e))
