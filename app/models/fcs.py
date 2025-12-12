"""FCS file models."""
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.common.database import Base
from app.common.id_utils import generate_uuid7


class FCSFile(Base):
    """FCS file metadata."""
    __tablename__ = "fcs_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid7)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    file_id = Column(String(50), unique=True, nullable=False, index=True)  # Short ID for API
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)  # Path to stored file
    total_events = Column(Integer, nullable=False)
    total_parameters = Column(Integer, nullable=False)
    uploaded_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    # Relationships
    user = relationship("User", back_populates="fcs_files")
    parameters = relationship("FCSParameter", back_populates="file", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<FCSFile(id={self.id}, file_id={self.file_id}, filename={self.filename})>"


class FCSParameter(Base):
    """FCS file parameter metadata."""
    __tablename__ = "fcs_parameters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid7)
    file_id = Column(UUID(as_uuid=True), ForeignKey("fcs_files.id", ondelete="CASCADE"), nullable=False)
    index = Column(Integer, nullable=False)  # Parameter index (1, 2, 3, ...)
    pnn = Column(String(100), nullable=False)  # Parameter name (e.g., "FSC-H")
    pns = Column(String(100), nullable=False)  # Parameter short name (e.g., "FSC-H")
    range = Column(Integer, nullable=False)  # Parameter range
    display = Column(String(10), nullable=False)  # Display type: LIN or LOG

    # Relationships
    file = relationship("FCSFile", back_populates="parameters")

    def __repr__(self):
        return f"<FCSParameter(id={self.id}, pnn={self.pnn}, index={self.index})>"
