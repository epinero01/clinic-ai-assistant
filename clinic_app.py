import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="CityCare Clinic",
    page_icon="🏥",
    layout="wide"
)

st.title("🏥 CityCare Clinic")
st.subheader("Appointment Management Demo")

# --------------------------------------------------
# DATOS MOCK TEMPORALES
# Sustituiremos esto por SQL más adelante
# --------------------------------------------------

specialties = pd.DataFrame([
    {"specialty_id": "CARD", "specialty_name": "Cardiology"},
    {"specialty_id": "DERM", "specialty_name": "Dermatology"},
    {"specialty_id": "PED", "specialty_name": "Pediatrics"},
])

doctors = pd.DataFrame([
    {
        "doctor_id": "D001",
        "doctor_name": "Laura Garcia",
        "specialty_id": "CARD",
        "patient_type": "ADULT"
    },
    {
        "doctor_id": "D002",
        "doctor_name": "Marta Perez",
        "specialty_id": "CARD",
        "patient_type": "PEDIATRIC"
    },
    {
        "doctor_id": "D004",
        "doctor_name": "Ana Sanchez",
        "specialty_id": "DERM",
        "patient_type": "ADULT"
    },
])

patients = pd.DataFrame([
    {"patient_id": "P001", "patient_name": "Elena Pinero"},
    {"patient_id": "P003", "patient_name": "Pablo Pinero"},
    {"patient_id": "P004", "patient_name": "Lucia Pinero"},
])

slots = pd.DataFrame([
    {
        "slot_id": "S001",
        "doctor_id": "D002",
        "appointment_date": "2026-10-01",
        "start_time": "09:00"
    },
    {
        "slot_id": "S002",
        "doctor_id": "D002",
        "appointment_date": "2026-10-01",
        "start_time": "09:30"
    },
    {
        "slot_id": "S003",
        "doctor_id": "D001",
        "appointment_date": "2026-10-01",
        "start_time": "10:00"
    }
])

# --------------------------------------------------
# ESPECIALIDAD
# --------------------------------------------------

selected_specialty = st.selectbox(
    "Medical Specialty",
    specialties["specialty_name"]
)

selected_specialty_id = specialties.loc[
    specialties["specialty_name"] == selected_specialty,
    "specialty_id"
].iloc[0]

# --------------------------------------------------
# MEDICOS
# --------------------------------------------------

filtered_doctors = doctors[
    doctors["specialty_id"] == selected_specialty_id
]

selected_doctor = st.selectbox(
    "Doctor",
    filtered_doctors["doctor_name"]
)

selected_doctor_id = filtered_doctors.loc[
    filtered_doctors["doctor_name"] == selected_doctor,
    "doctor_id"
].iloc[0]

# --------------------------------------------------
# DISPONIBILIDAD
# --------------------------------------------------

doctor_slots = slots[
    slots["doctor_id"] == selected_doctor_id
]

if len(doctor_slots) > 0:

    slot_options = (
        doctor_slots["appointment_date"]
        + " "
        + doctor_slots["start_time"]
    )

    selected_slot_display = st.selectbox(
        "Available Appointment",
        slot_options
    )

    selected_slot_id = doctor_slots.iloc[
        slot_options.tolist().index(selected_slot_display)
    ]["slot_id"]

else:

    st.warning("No available slots found.")
    selected_slot_id = None

# --------------------------------------------------
# PACIENTE
# --------------------------------------------------

selected_patient = st.selectbox(
    "Patient",
    patients["patient_name"]
)

selected_patient_id = patients.loc[
    patients["patient_name"] == selected_patient,
    "patient_id"
].iloc[0]

# --------------------------------------------------
# MOTIVO
# --------------------------------------------------

appointment_reason = st.text_area(
    "Appointment Reason",
    placeholder="Describe the reason for the visit..."
)

# --------------------------------------------------
# RESERVA
# --------------------------------------------------

if st.button("Book Appointment"):

    if not selected_slot_id:
        st.error("No slot selected.")

    else:

        st.success("Appointment booking request created.")

        st.json({
            "patient_id": selected_patient_id,
            "patient_name": selected_patient,
            "doctor": selected_doctor,
            "slot_id": selected_slot_id,
            "reason": appointment_reason
        })
