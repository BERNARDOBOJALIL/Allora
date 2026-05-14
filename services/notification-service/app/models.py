from sqlalchemy import Column, String, Boolean, DateTime, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from app.db import Base
import uuid
from datetime import datetime

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    type = Column(String(50), nullable=False)      # signal_sent, match_created, user_registered, message_sent
    title = Column(String(255), nullable=False)
    body = Column(String(500), nullable=False)
    extra_data = Column(JSON, nullable=True)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_user_read_created", "user_id", "read", "created_at"),
    )