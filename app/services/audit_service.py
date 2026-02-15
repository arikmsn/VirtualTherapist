"""Audit service - comprehensive logging for compliance and security"""

from typing import Optional, Any, Dict
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.audit import AuditLog
from loguru import logger


class AuditService:
    """
    Comprehensive audit logging service
    Required for GDPR compliance and security
    """

    def __init__(self, db: Session):
        self.db = db

    async def log_action(
        self,
        action: str,
        resource_type: str,
        user_id: Optional[int] = None,
        user_type: str = "system",
        user_email: Optional[str] = None,
        resource_id: Optional[int] = None,
        action_details: Optional[Dict[str, Any]] = None,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        gdpr_relevant: bool = False,
        data_category: Optional[str] = None
    ) -> AuditLog:
        """
        Log an action to the audit trail

        Args:
            action: Action performed (create, read, update, delete, approve, etc.)
            resource_type: Type of resource (patient, message, session, etc.)
            user_id: ID of user performing action
            user_type: Type of user (therapist, patient, system, admin)
            user_email: Email of user
            resource_id: ID of resource affected
            action_details: Additional details about the action
            old_value: Previous value (for updates)
            new_value: New value (for updates)
            ip_address: IP address of user
            user_agent: User agent string
            success: Whether the action succeeded
            error_message: Error message if action failed
            gdpr_relevant: Whether this involves personal data
            data_category: Category of data (personal, medical, contact, etc.)

        Returns:
            Created audit log entry
        """

        audit_entry = AuditLog(
            user_id=user_id,
            user_type=user_type,
            user_email=user_email,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            timestamp=datetime.utcnow(),
            action_details=action_details,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error_message=error_message,
            gdpr_relevant=gdpr_relevant,
            data_category=data_category
        )

        self.db.add(audit_entry)
        self.db.commit()

        # Also log to file for redundancy
        logger.info(
            f"AUDIT: {user_type}:{user_id} performed {action} on {resource_type}:{resource_id}"
        )

        return audit_entry

    def get_user_audit_trail(
        self,
        user_id: int,
        user_type: str = "therapist",
        limit: int = 100
    ):
        """Get audit trail for a specific user"""

        return self.db.query(AuditLog).filter(
            AuditLog.user_id == user_id,
            AuditLog.user_type == user_type
        ).order_by(AuditLog.timestamp.desc()).limit(limit).all()

    def get_resource_audit_trail(
        self,
        resource_type: str,
        resource_id: int,
        limit: int = 100
    ):
        """Get audit trail for a specific resource"""

        return self.db.query(AuditLog).filter(
            AuditLog.resource_type == resource_type,
            AuditLog.resource_id == resource_id
        ).order_by(AuditLog.timestamp.desc()).limit(limit).all()

    def get_gdpr_relevant_logs(
        self,
        user_id: Optional[int] = None,
        resource_id: Optional[int] = None,
        limit: int = 1000
    ):
        """Get all GDPR-relevant logs for compliance reporting"""

        query = self.db.query(AuditLog).filter(AuditLog.gdpr_relevant == True)

        if user_id:
            query = query.filter(AuditLog.user_id == user_id)

        if resource_id:
            query = query.filter(AuditLog.resource_id == resource_id)

        return query.order_by(AuditLog.timestamp.desc()).limit(limit).all()
