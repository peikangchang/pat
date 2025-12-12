"""Audit log model."""
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Integer, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.common.database import Base
from app.common.id_utils import generate_uuid7


class AuditLog(Base):
    """Audit log for token usage."""
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid7)
    token_id = Column(UUID(as_uuid=True), ForeignKey("tokens.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"), index=True)
    ip_address = Column(String(45), nullable=False)  # IPv6 compatible
    method = Column(String(10), nullable=False)  # GET, POST, etc.
    endpoint = Column(String(255), nullable=False)
    status_code = Column(Integer, nullable=False)
    authorized = Column(Boolean, nullable=False)
    reason = Column(String(255), nullable=True)  # Failure reason if not authorized

    # Relationships
    token = relationship("Token", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog(id={self.id}, token_id={self.token_id}, endpoint={self.endpoint})>"
