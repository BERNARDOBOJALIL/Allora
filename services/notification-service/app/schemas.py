from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, Dict, Any

class NotificationResponse(BaseModel):
    id: UUID
    user_id: UUID
    type: str
    title: str
    body: str
    extra_data: Optional[Dict[str, Any]] = None
    read: bool
    created_at: datetime

class MarkReadRequest(BaseModel):
    notification_id: UUID