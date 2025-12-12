"""User model."""
from sqlalchemy import Column, String, DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.common.database import Base
from app.common.id_utils import generate_uuid7


class User(Base):
    """User model for authentication."""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid7)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))

    # Relationships
    tokens = relationship("Token", back_populates="user", cascade="all, delete-orphan")
    fcs_files = relationship("FCSFile", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username})>"
