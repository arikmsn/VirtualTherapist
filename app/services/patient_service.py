"""Patient service - manages patient records with encryption"""

from typing import Optional, Dict, Any, List
from datetime import date
from sqlalchemy.orm import Session
from app.models.patient import Patient, PatientStatus
from app.security.encryption import encrypt_data, decrypt_data
from app.services.audit_service import AuditService
from loguru import logger


# Fields that must be encrypted before storage
ENCRYPTED_FIELDS = {
    "full_name": "full_name_encrypted",
    "phone": "phone_encrypted",
    "email": "email_encrypted",
    "primary_concerns": "primary_concerns",
    "diagnosis": "diagnosis",
}


class PatientService:
    """Service for managing patient records"""

    def __init__(self, db: Session):
        self.db = db
        self.audit_service = AuditService(db)

    async def create_patient(
        self,
        therapist_id: int,
        full_name: str,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        start_date: Optional[date] = None,
        primary_concerns: Optional[str] = None,
        diagnosis: Optional[str] = None,
        treatment_goals: Optional[List[str]] = None,
        preferred_contact_time: Optional[str] = None,
        allow_ai_contact: bool = True,
    ) -> Patient:
        """Create a new patient with encrypted personal data"""

        patient = Patient(
            therapist_id=therapist_id,
            full_name_encrypted=encrypt_data(full_name),
            phone_encrypted=encrypt_data(phone) if phone else None,
            email_encrypted=encrypt_data(email) if email else None,
            start_date=start_date,
            primary_concerns=(
                encrypt_data(primary_concerns)
                if primary_concerns else None
            ),
            diagnosis=(
                encrypt_data(diagnosis) if diagnosis else None
            ),
            treatment_goals=treatment_goals,
            preferred_contact_time=preferred_contact_time,
            allow_ai_contact=allow_ai_contact,
            status=PatientStatus.ACTIVE,
        )

        self.db.add(patient)
        self.db.commit()
        self.db.refresh(patient)

        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action="create",
            resource_type="patient",
            resource_id=patient.id,
            gdpr_relevant=True,
            data_category="personal",
        )

        logger.info(
            f"Created patient {patient.id} for therapist {therapist_id}"
        )
        return self._with_decrypted_fields(patient)

    async def get_patient(
        self,
        patient_id: int,
        therapist_id: int,
    ) -> Optional[Patient]:
        """Get a single patient by ID (ownership verified)"""

        patient = self.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.therapist_id == therapist_id,
        ).first()

        if not patient:
            return None

        return self._with_decrypted_fields(patient)

    async def get_therapist_patients(
        self,
        therapist_id: int,
        status: Optional[PatientStatus] = None,
    ) -> List[Patient]:
        """List all patients for a therapist"""

        query = self.db.query(Patient).filter(
            Patient.therapist_id == therapist_id,
        )

        if status:
            query = query.filter(Patient.status == status)

        patients = query.order_by(Patient.created_at.desc()).all()
        return [self._with_decrypted_fields(p) for p in patients]

    async def update_patient(
        self,
        patient_id: int,
        therapist_id: int,
        update_data: Dict[str, Any],
    ) -> Patient:
        """Update patient fields (re-encrypts sensitive data)"""

        patient = self.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.therapist_id == therapist_id,
        ).first()

        if not patient:
            raise ValueError("Patient not found")

        for field, value in update_data.items():
            if value is None:
                continue
            if field in ENCRYPTED_FIELDS:
                db_field = ENCRYPTED_FIELDS[field]
                setattr(patient, db_field, encrypt_data(value))
            elif hasattr(patient, field):
                setattr(patient, field, value)

        self.db.commit()
        self.db.refresh(patient)

        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action="update",
            resource_type="patient",
            resource_id=patient.id,
            action_details={"updated_fields": list(update_data.keys())},
            gdpr_relevant=True,
            data_category="personal",
        )

        logger.info(f"Updated patient {patient_id}")
        return self._with_decrypted_fields(patient)

    async def delete_patient(
        self,
        patient_id: int,
        therapist_id: int,
    ) -> None:
        """Delete patient and all related records (cascade)"""

        patient = self.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.therapist_id == therapist_id,
        ).first()

        if not patient:
            raise ValueError("Patient not found")

        self.db.delete(patient)
        self.db.commit()

        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action="delete",
            resource_type="patient",
            resource_id=patient_id,
            gdpr_relevant=True,
            data_category="personal",
        )

        logger.info(f"Deleted patient {patient_id}")

    def _with_decrypted_fields(self, patient: Patient) -> Patient:
        """Attach decrypted plain-text attributes to patient object"""
        patient.full_name = decrypt_data(patient.full_name_encrypted)
        patient.phone = (
            decrypt_data(patient.phone_encrypted)
            if patient.phone_encrypted else None
        )
        patient.email = (
            decrypt_data(patient.email_encrypted)
            if patient.email_encrypted else None
        )
        patient.primary_concerns_plain = (
            decrypt_data(patient.primary_concerns)
            if patient.primary_concerns else None
        )
        patient.diagnosis_plain = (
            decrypt_data(patient.diagnosis)
            if patient.diagnosis else None
        )
        return patient
