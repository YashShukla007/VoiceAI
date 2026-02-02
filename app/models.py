import enum
from sqlalchemy import Column, String, Integer, Float, ForeignKey, Text, UniqueConstraint, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .db import Base


class CallState(str, enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    PROCESSING_AI = "PROCESSING_AI"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"


class Call(Base):
    __tablename__ = "calls"

    id = Column(String, primary_key=True)
    state = Column(String, nullable=False, default=CallState.IN_PROGRESS.value)
    last_sequence = Column(Integer, nullable=True)
    transcript = Column(Text, nullable=True)
    sentiment = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    packets = relationship("Packet", back_populates="call")


class Packet(Base):
    __tablename__ = "packets"
    __table_args__ = (UniqueConstraint("call_id", "sequence", name="uq_call_sequence"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    call_id = Column(String, ForeignKey("calls.id", ondelete="CASCADE"), index=True)
    sequence = Column(Integer, nullable=False)
    data = Column(Text, nullable=False)
    timestamp = Column(Float, nullable=False)

    call = relationship("Call", back_populates="packets")