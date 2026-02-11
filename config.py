from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data_mvp"
ASSETS_DIR = BASE_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "logo.png"

APPOINTMENTS_FILE = DATA_DIR / "appointments.csv"
EVENTS_LOG_FILE = DATA_DIR / "events_log.csv"
PROCEDURES_FILE = DATA_DIR / "reference_procedures.csv"

# Roles shown in UI
ROLES = ["Recepción", "Facturación", "Enfermería (solo lectura)", "Analítica"]

# Appointment attendance status (stored in appointments.csv)
ATTENDANCE_STATUSES = ["PROGRAMADA", "ASISTIÓ", "NO ASISTIÓ", "CANCELADA", "REPROGRAMADA"]

# Reasons used when billing returns a case
CORRECTION_REASONS = [
    "Datos del paciente incorrectos",
    "Autorización faltante o inválida",
    "Problema de elegibilidad EPS / régimen",
    "Copago incorrecto / no coincide",
    "Soportes ilegibles o incompletos",
    "Otro",
]

SERVICE_TYPES = ["Consulta", "Imagenología", "Terapias", "Otros"]
DOCUMENT_TYPES = ["CC", "TI", "CE", "PA"]

# Required fields at intake (Reception)
REQUIRED_FIELDS = [
    "document_type",
    "document_number",
    "first_name",
    "first_surname",
    "date_of_birth",
    "eps_name",
    "service_type",
    "procedure_name",
    "appointment_datetime",
]
