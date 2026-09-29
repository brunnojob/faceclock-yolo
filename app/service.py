import json
from datetime import datetime, timezone

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models import AttendanceEvent, BiometricTemplate, Employee
from app.security import decrypt_embedding, encrypt_embedding, event_digest


class AttendanceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def enroll(self, external_id: str, display_name: str, embeddings: list[np.ndarray], model: str) -> Employee:
        employee = self.db.scalar(select(Employee).where(Employee.external_id == external_id))
        if employee is None:
            employee = Employee(
                external_id=external_id,
                display_name=display_name,
                consented_at=datetime.now(timezone.utc),
            )
            self.db.add(employee)
            self.db.flush()
        else:
            employee.display_name = display_name
            employee.active = True
        for embedding in embeddings:
            ciphertext, nonce = encrypt_embedding(embedding, employee.id)
            employee.templates.append(
                BiometricTemplate(ciphertext=ciphertext, nonce=nonce, model_version=model)
            )
        self.db.commit()
        self.db.refresh(employee)
        return employee

    def match(self, probe: np.ndarray) -> tuple[Employee | None, float]:
        employees = self.db.scalars(
            select(Employee).where(Employee.active.is_(True)).options(selectinload(Employee.templates))
        ).all()
        winner = None
        score = -1.0
        for employee in employees:
            for template in employee.templates:
                candidate = decrypt_embedding(template.ciphertext, template.nonce, employee.id)
                similarity = float(np.dot(probe, candidate))
                if similarity > score:
                    winner, score = employee, similarity
        return winner, score

    def record(self, employee: Employee | None, action: str, score: float, camera_id: str) -> AttendanceEvent:
        settings = get_settings()
        if employee is not None and score >= settings.match_threshold:
            decision, reason = "accepted", "Identity confidence met the attendance threshold"
        elif employee is not None and score >= settings.review_threshold:
            decision, reason = "review", "Identity confidence requires human verification"
        else:
            decision, reason = "rejected", "No enrolled identity met the review threshold"
        previous = self.db.scalar(select(AttendanceEvent).order_by(AttendanceEvent.occurred_at.desc()).limit(1))
        previous_hash = previous.event_hash if previous else "0" * 64
        event = AttendanceEvent(
            employee_id=employee.id if employee else None,
            action=action,
            decision=decision,
            similarity=f"{score:.8f}",
            camera_id=camera_id,
            reason=reason,
            previous_hash=previous_hash,
            event_hash="",
        )
        self.db.add(event)
        self.db.flush()
        payload = json.dumps(
            {
                "id": event.id,
                "employee_id": event.employee_id,
                "action": event.action,
                "decision": event.decision,
                "similarity": event.similarity,
                "camera_id": event.camera_id,
                "previous_hash": previous_hash,
            },
            sort_keys=True,
        )
        event.event_hash = event_digest(payload)
        self.db.commit()
        self.db.refresh(event)
        return event

