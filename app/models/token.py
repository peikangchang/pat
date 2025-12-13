"""Token model."""
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, JSON, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.common.database import Base
from app.common.id_utils import generate_uuid7


class Token(Base):
    """PAT token model."""
    __tablename__ = "tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid7)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)  # SHA-256 hash
    token_prefix = Column(String(12), nullable=False, index=True)  # pat_ + first 8 chars
    scopes = Column(JSON, nullable=False, default=list)  # ["workspaces:read", "fcs:write", ...]
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    is_revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    # Relationships
    user = relationship("User", back_populates="tokens")
    audit_logs = relationship("AuditLog", back_populates="token", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Token(id={self.id}, name={self.name}, prefix={self.token_prefix})>"
