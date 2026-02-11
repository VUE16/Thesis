import uuid
from datetime import datetime, date
from pathlib import Path

import pandas as pd
import streamlit as st

from config import (
    DATA_DIR, APPOINTMENTS_FILE, EVENTS_LOG_FILE, PROCEDURES_FILE,
    ROLES, CORRECTION_REASONS, SERVICE_TYPES, DOCUMENT_TYPES, REQUIRED_FIELDS
)

# -----------------------------
# Branding (logo + colores)
# -----------------------------
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
LOGO_PATH = ASSETS_DIR / "logo.png"

# Colores (muy cercanos al logo; si quieres, luego los afinamos)
BRAND_BLUE = "#2E69A3"
BRAND_GREEN = "#3A8B4A"
BRAND_YELLOW = "#E6C300"
BRAND_BG = "#F6F9FC"
CARD_BG = "#FFFFFF"
TEXT_DARK = "#0F172A"
TEXT_MUTED = "#475569"

def inject_brand_css():
    st.markdown(f"""
<style>
/* Primary button */
div.stButton > button {{
    background: {BRAND_BLUE} !important;
    color: #FFFFFF !important;
    border: 1px solid {BRAND_BLUE} !important;
    border-radius: 12px !important;
    padding: 0.55rem 1rem !important;
    font-weight: 700 !important;
}}

div.stButton > button:hover {{
    background: {BRAND_GREEN} !important;
    border-color: {BRAND_GREEN} !important;
    color: #FFFFFF !important;
}}
</style>
""", unsafe_allow_html=True)


def render_sidebar_header():
    if LOGO_PATH.exists():
        st.sidebar.image(str(LOGO_PATH), use_container_width=True)

        # Barras de color (más “branding” sin duplicar el logo)
        st.sidebar.markdown(
            f"""
            <div style="height:10px"></div>
            <div style="height:6px;background:{BRAND_BLUE};border-radius:999px;margin:8px 0;"></div>
            <div style="height:6px;background:{BRAND_GREEN};border-radius:999px;margin:8px 0;"></div>
            <div style="height:6px;background:{BRAND_YELLOW};border-radius:999px;margin:8px 0;"></div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.sidebar.warning("Logo no encontrado. Revisa assets/logo.png")

    st.sidebar.markdown(
        f"""
        <div style="font-weight:900; color:{BRAND_BLUE}; font-size:16px; margin-top:8px;">
            Centro Clínico Santiago
        </div>
        <div style="color:{TEXT_MUTED}; font-size:12px;">
            MVP — Consulta externa
        </div>
        """,
        unsafe_allow_html=True
    )
    st.sidebar.markdown("---")

# -----------------------------
# Etiquetas UI (Español)
# -----------------------------
FIELD_LABELS_ES = {
    "document_type": "Tipo de documento",
    "document_number": "Número de documento",
    "first_name": "Primer nombre",
    "first_surname": "Primer apellido",
    "date_of_birth": "Fecha de nacimiento",
    "eps_name": "EPS",
    "regime": "Régimen",
    "service_type": "Tipo de servicio",
    "procedure_name": "Procedimiento",
    "appointment_datetime": "Fecha y hora",
}

FLAG_REASON_LABELS = {
    "DOC_NOT_NUMERIC": "Documento: debe ser numérico",
    "DOC_LENGTH_UNUSUAL": "Documento: longitud inusual para este tipo",
    "DOB_PLAUSIBILITY": "Fecha de nacimiento: no parece válida",
    "DOB_MISSING_OR_INVALID": "Fecha de nacimiento: faltante o inválida",
    "MISSING_AUTHORIZATION_FOR_PROCEDURE": "Falta autorización para el procedimiento",
    "COPAY_NEGATIVE": "Copago: no puede ser negativo",
    "COPAY_NOT_NUMERIC": "Copago: debe ser numérico",
}

# -----------------------------
# Utilities: archivos + IO seguro
# -----------------------------
def ensure_data_folder():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

def safe_read_csv(path: Path, columns=None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=columns or [])
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame(columns=columns or [])

def append_row_csv(path: Path, row: dict):
    df = pd.DataFrame([row])
    header = not path.exists()
    df.to_csv(path, mode="a", header=header, index=False)

def now_iso():
    return datetime.now().isoformat(timespec="seconds")

def log_event(
    event_type: str,
    appointment_id: str | None,
    user_role: str,
    user_id: str,
    flagged: bool | None = None,
    flag_reason: str | None = None,
    review_decision: str | None = None,
    correction_reason: str | None = None,
    previous_status: str | None = None,
    new_status: str | None = None
):
    event = {
        "event_id": str(uuid.uuid4()),
        "timestamp": now_iso(),
        "appointment_id": appointment_id if appointment_id else "",
        "event_type": event_type,
        "user_role": user_role,
        "user_id": user_id,
        "flagged": flagged if flagged is not None else "",
        "flag_reason": flag_reason if flag_reason else "",
        "review_decision": review_decision if review_decision else "",
        "correction_reason": correction_reason if correction_reason else "",
        "previous_status": previous_status if previous_status else "",
        "new_status": new_status if new_status else "",
    }
    append_row_csv(EVENTS_LOG_FILE, event)

# -----------------------------
# Procedimientos
# -----------------------------
def load_procedures() -> pd.DataFrame:
    cols = ["procedure_name", "authorization_required"]
    df = safe_read_csv(PROCEDURES_FILE, columns=cols)

    if df.empty:
        starter = pd.DataFrame([
            {"procedure_name": "Consulta general", "authorization_required": False},
            {"procedure_name": "Consulta especialista", "authorization_required": False},
            {"procedure_name": "Rayos X", "authorization_required": True},
            {"procedure_name": "Ecografía", "authorization_required": True},
            {"procedure_name": "Terapia física", "authorization_required": True},
        ])
        starter.to_csv(PROCEDURES_FILE, index=False)
        df = starter

    if df["authorization_required"].dtype != bool:
        df["authorization_required"] = df["authorization_required"].astype(str).str.lower().isin(
            ["true", "1", "yes", "y", "si", "sí"]
        )
    return df

def authorization_required_for(proc_name: str, procedures_df: pd.DataFrame) -> bool:
    match = procedures_df[
        procedures_df["procedure_name"].astype(str).str.strip().str.lower()
        == str(proc_name).strip().lower()
    ]
    if match.empty:
        return False
    return bool(match.iloc[0]["authorization_required"])

# -----------------------------
# Reglas de validación (devuelven CÓDIGOS)
# -----------------------------
def rule_checks(form: dict, procedures_df: pd.DataFrame) -> list[str]:
    reasons = []

    doc = str(form.get("document_number", "")).strip()
    doc_type = form.get("document_type", "")
    if not doc.isdigit():
        reasons.append("DOC_NOT_NUMERIC")
    else:
        if doc_type in ["CC", "TI"] and not (6 <= len(doc) <= 12):
            reasons.append("DOC_LENGTH_UNUSUAL")
        if doc_type in ["CE", "PA"] and not (6 <= len(doc) <= 15):
            reasons.append("DOC_LENGTH_UNUSUAL")

    dob = form.get("date_of_birth")
    if isinstance(dob, date):
        age = (date.today() - dob).days / 365.25
        if age < 0 or age > 110:
            reasons.append("DOB_PLAUSIBILITY")
    else:
        reasons.append("DOB_MISSING_OR_INVALID")

    proc = form.get("procedure_name", "")
    needs_auth = authorization_required_for(proc, procedures_df)
    if needs_auth and not str(form.get("authorization_number", "")).strip():
        reasons.append("MISSING_AUTHORIZATION_FOR_PROCEDURE")

    copay = form.get("copay_amount")
    if copay not in [None, ""]:
        try:
            if float(copay) < 0:
                reasons.append("COPAY_NEGATIVE")
        except Exception:
            reasons.append("COPAY_NOT_NUMERIC")

    return reasons

def missing_required_fields(form: dict) -> list[str]:
    missing = []
    for f in REQUIRED_FIELDS:
        v = form.get(f)
        if v is None:
            missing.append(f)
        elif isinstance(v, str) and not v.strip():
            missing.append(f)
    return missing

def get_flag_reasons(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty or "event_type" not in events.columns:
        return pd.DataFrame(columns=["appointment_id", "flag_reason"])
    flags = events[events["event_type"] == "FLAGGED_RULE"].copy()
    if flags.empty:
        return pd.DataFrame(columns=["appointment_id", "flag_reason"])
    return flags[["appointment_id", "flag_reason"]]

# -----------------------------
# Páginas
# -----------------------------
def page_reception(user_id: str):
    st.header("Recepción — Agendamiento e ingreso")

    procedures_df = load_procedures()
    procedure_options = sorted(procedures_df["procedure_name"].astype(str).tolist())

    with st.form("intake_form"):
        col1, col2 = st.columns(2)

        with col1:
            document_type = st.selectbox("Tipo de documento", DOCUMENT_TYPES, index=0)
            document_number = st.text_input("Número de documento")
            first_name = st.text_input("Primer nombre")
            first_surname = st.text_input("Primer apellido")
            date_of_birth = st.date_input(
    "Fecha de nacimiento",
    value=date(1990, 1, 1),
    min_value=date(1900, 1, 1),
    max_value=date.today(),  # or date(2026, 12, 31)
)


        with col2:
            eps_name = st.text_input("EPS")
            regime = st.selectbox("Régimen", ["Contributivo", "Subsidiado", "Otro"], index=0)
            service_type = st.selectbox("Tipo de servicio", SERVICE_TYPES, index=0)
            procedure_name = st.selectbox("Procedimiento", procedure_options)
            appointment_datetime = st.text_input(
                "Fecha y hora (YYYY-MM-DD HH:MM)",
                value=f"{date.today().isoformat()} 08:00"
            )

        st.subheader("Autorización / copago (si aplica)")
        authorization_number = st.text_input("Número de autorización (si aplica)")
        copay_amount = st.text_input("Copago (si aplica)")

        submit = st.form_submit_button("Guardar cita")

    if submit:
        form = {
            "document_type": document_type,
            "document_number": document_number.strip(),
            "first_name": first_name.strip(),
            "first_surname": first_surname.strip(),
            "date_of_birth": date_of_birth,
            "eps_name": eps_name.strip(),
            "regime": regime,
            "service_type": service_type,
            "procedure_name": procedure_name,
            "appointment_datetime": appointment_datetime.strip(),
            "authorization_number": authorization_number.strip(),
            "copay_amount": copay_amount.strip(),
        }

        log_event("SAVE_ATTEMPT", None, "Recepción", user_id)

        missing = missing_required_fields(form)
        if missing:
            missing_labels = [FIELD_LABELS_ES.get(f, f) for f in missing]
            log_event("BLOCKED_MISSING_FIELD", None, "Recepción", user_id, flagged=True,
                      flag_reason="FALTAN_CAMPOS: " + ", ".join(missing))
            st.error(f"Faltan campos obligatorios: {', '.join(missing_labels)}")
            return

        appointment_id = str(uuid.uuid4())

        appt_row = {
            "appointment_id": appointment_id,
            "created_at": now_iso(),
            "created_by_user_id": user_id,
            "document_type": form["document_type"],
            "document_number": form["document_number"],
            "first_name": form["first_name"],
            "first_surname": form["first_surname"],
            "date_of_birth": form["date_of_birth"].isoformat(),
            "eps_name": form["eps_name"],
            "regime": form["regime"],
            "service_type": form["service_type"],
            "procedure_name": form["procedure_name"],
            "appointment_datetime": form["appointment_datetime"],
            "attendance_status": "PROGRAMADA",
            "status_updated_at": now_iso(),
            "status_updated_by_user_id": user_id,
        }

        append_row_csv(APPOINTMENTS_FILE, appt_row)
        log_event("INTAKE_SAVED", appointment_id, "Recepción", user_id)

        reasons = rule_checks(form, procedures_df)
        if reasons:
            for r in reasons:
                log_event("FLAGGED_RULE", appointment_id, "Recepción", user_id, flagged=True, flag_reason=r)
            log_event("SENT_TO_REVIEW", appointment_id, "Recepción", user_id)

            reasons_es = [FLAG_REASON_LABELS.get(r, r) for r in reasons]
            st.warning("Cita guardada, pero enviada a revisión de Facturación. Motivos: " + ", ".join(reasons_es))
        else:
            st.success("Cita guardada y lista (sin banderas).")

    st.divider()
    st.subheader("Catálogo de procedimientos (autorización requerida)")
    st.caption("Edita esto para que la regla de autorización sea realista.")
    proc_edit = st.data_editor(load_procedures(), num_rows="dynamic", use_container_width=True)
    if st.button("Guardar catálogo"):
        proc_edit.to_csv(PROCEDURES_FILE, index=False)
        st.success("Catálogo guardado.")

def page_billing(user_id: str):
    st.header("Facturación — Cola de revisión (HITL)")

    appointments = safe_read_csv(APPOINTMENTS_FILE)
    events = safe_read_csv(EVENTS_LOG_FILE)

    if appointments.empty:
        st.info("No hay citas todavía.")
        return

    flags = get_flag_reasons(events)
    if flags.empty:
        st.success("No hay casos marcados para revisar.")
        return

    flag_summary = (
        flags.groupby("appointment_id")["flag_reason"]
        .apply(lambda x: ", ".join(sorted(set(map(str, x)))))
        .reset_index()
    )

    merged = appointments.merge(flag_summary, on="appointment_id", how="inner")

    def format_flag_reason_cell(cell: str) -> str:
        parts = [p.strip() for p in str(cell).split(",")]
        parts_es = [FLAG_REASON_LABELS.get(p, p) for p in parts if p]
        return ", ".join(parts_es)

    merged_display = merged.copy()
    merged_display["flag_reason"] = merged_display["flag_reason"].apply(format_flag_reason_cell)

    st.subheader("Casos para revisión")
    st.dataframe(
        merged_display[[
            "appointment_id", "document_type", "document_number",
            "first_name", "first_surname", "eps_name",
            "service_type", "procedure_name", "appointment_datetime",
            "flag_reason"
        ]],
        use_container_width=True
    )

    st.divider()
    st.subheader("Registrar decisión")

    appt_ids = merged["appointment_id"].tolist()
    selected_id = st.selectbox("Selecciona un appointment_id", appt_ids)

    decision_label = st.radio("Decisión", ["Aprobar", "Devolver para corrección"], horizontal=True)
    decision = "APROBAR" if decision_label == "Aprobar" else "DEVOLVER_PARA_CORRECCION"

    correction_reason = ""
    if decision == "DEVOLVER_PARA_CORRECCION":
        correction_reason = st.selectbox("Motivo de devolución", CORRECTION_REASONS)

    if st.button("Guardar decisión"):
        log_event("REVIEW_DECISION_RECORDED", selected_id, "Facturación", user_id,
                  review_decision=decision, correction_reason=correction_reason)
        st.success("Decisión registrada.")

def page_analytics():
    st.header("Analítica — Métricas automáticas del MVP")

    appointments = safe_read_csv(APPOINTMENTS_FILE)
    events = safe_read_csv(EVENTS_LOG_FILE)

    if appointments.empty:
        st.info("Aún no hay citas registradas.")
        return

    total_appts = appointments["appointment_id"].nunique()

    flagged = events[events["event_type"] == "FLAGGED_RULE"].copy() if not events.empty else pd.DataFrame()
    flagged_appts = flagged["appointment_id"].nunique() if not flagged.empty else 0
    pct_flagged = (flagged_appts / total_appts) * 100 if total_appts else 0

    top_reasons = (
        flagged["flag_reason"].value_counts().reset_index()
        .rename(columns={"index": "Motivo", "flag_reason": "Cantidad"})
        if not flagged.empty else pd.DataFrame(columns=["Motivo", "Cantidad"])
    )
    if not top_reasons.empty:
        top_reasons["Motivo"] = top_reasons["Motivo"].apply(lambda x: FLAG_REASON_LABELS.get(str(x), str(x)))

    decisions = events[events["event_type"] == "REVIEW_DECISION_RECORDED"].copy() if not events.empty else pd.DataFrame()
    total_reviewed = decisions["appointment_id"].nunique() if not decisions.empty else 0

    returned = decisions[decisions["review_decision"] == "DEVOLVER_PARA_CORRECCION"] if not decisions.empty else pd.DataFrame()
    returned_count = returned["appointment_id"].nunique() if not returned.empty else 0
    pct_returned = (returned_count / total_reviewed) * 100 if total_reviewed else 0

    approved = decisions[decisions["review_decision"] == "APROBAR"] if not decisions.empty else pd.DataFrame()
    approved_count = approved["appointment_id"].nunique() if not approved.empty else 0
    first_pass_yield = (approved_count / total_reviewed) * 100 if total_reviewed else 0

    intake = events[events["event_type"] == "INTAKE_SAVED"].copy() if not events.empty else pd.DataFrame()
    avg_mins = None
    if not intake.empty and not decisions.empty:
        intake["timestamp"] = pd.to_datetime(intake["timestamp"], errors="coerce")
        decisions["timestamp"] = pd.to_datetime(decisions["timestamp"], errors="coerce")

        last_intake = intake.sort_values("timestamp").groupby("appointment_id", as_index=False).tail(1)
        last_decision = decisions.sort_values("timestamp").groupby("appointment_id", as_index=False).tail(1)

        t = last_intake.merge(last_decision, on="appointment_id", suffixes=("_intake", "_decision"))
        if not t.empty:
            t["mins"] = (t["timestamp_decision"] - t["timestamp_intake"]).dt.total_seconds() / 60
            avg_mins = float(t["mins"].dropna().mean()) if t["mins"].notna().any() else None

    c1, c2, c3 = st.columns(3)
    c1.metric("% citas marcadas en recepción", f"{pct_flagged:.1f}%")
    c2.metric("% devueltas por facturación", f"{pct_returned:.1f}%")
    c3.metric("First-pass yield (aprobadas)", f"{first_pass_yield:.1f}%")

    st.divider()

    c4, c5 = st.columns(2)
    c4.metric("Tiempo promedio ingreso → decisión", "N/A" if avg_mins is None else f"{avg_mins:.1f} min")
    c5.metric("Total citas registradas", f"{total_appts}")

    st.divider()
    st.subheader("Top motivos de bandera (recepción)")
    if top_reasons.empty:
        st.write("No hay banderas todavía.")
    else:
        st.dataframe(top_reasons, use_container_width=True)

    st.subheader("Eventos (log) — últimos 50")
    st.dataframe(events.tail(50) if not events.empty else pd.DataFrame(), use_container_width=True)

# -----------------------------
# Main
# -----------------------------
def main():
    st.set_page_config(page_title="Centro Clínico Santiago — MVP", layout="wide")

    # ✅ CSS FIRST so labels/buttons render correctly
    inject_brand_css()

    # ✅ Data folder
    ensure_data_folder()

    # ✅ Sidebar (logo + color bars)
    render_sidebar_header()

    # ✅ Main title
    st.title("MVP — Consulta Externa + Revisión en Facturación (HITL)")

    # ✅ Sidebar controls
    st.sidebar.header("Rol y usuario")
    role = st.sidebar.selectbox("Selecciona el rol", ROLES)

    default_user = "REC_01"
    if role == "Facturación":
        default_user = "FAC_01"
    elif role == "Analítica":
        default_user = "ANA_01"
    elif role == "Enfermería (solo lectura)":
        default_user = "ENF_01"

    user_id = st.sidebar.text_input("ID de usuario (ej: REC_01 / FAC_01)", value=default_user)

    st.sidebar.markdown("---")
    pantalla = st.sidebar.radio("Pantalla", ["Recepción", "Facturación", "Analítica"], index=0)

    # ✅ Route to pages
    if pantalla == "Recepción":
        page_reception(user_id)
    elif pantalla == "Facturación":
        page_billing(user_id)
    else:
        page_analytics()


if __name__ == "__main__":
    main()
