from sqlmodel import Session, select
from typing import List, Optional
from ...domain.entities.audit import RuntimeAudit


class AuditRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, audit: RuntimeAudit) -> RuntimeAudit:
        self.session.add(audit)
        self.session.commit()
        self.session.refresh(audit)
        return audit

    def get_by_id(self, audit_id: str) -> Optional[RuntimeAudit]:
        return self.session.get(RuntimeAudit, audit_id)

    def list_for_run(self, run_id: str) -> List[RuntimeAudit]:
        statement = (
            select(RuntimeAudit)
            .where(RuntimeAudit.run_id == run_id)
            .order_by(RuntimeAudit.timestamp)
        )
        return list(self.session.exec(statement).all())
