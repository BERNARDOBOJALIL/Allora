from fastapi import APIRouter, Depends, HTTPException, Query
from uuid import UUID
from app.services.notification_service import NotificationService
from app.schemas import NotificationResponse, MarkReadRequest

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.get("/{user_id}", response_model=list[NotificationResponse])
async def get_notifications(
    user_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    # TODO: user_id debera validarse 
    return await NotificationService.get_user_notifications(user_id, limit, offset)

@router.patch("/read")
async def mark_notification_read(request: MarkReadRequest):
    await NotificationService.mark_as_read(request.notification_id)
    return {"message": "Notification marked as read"}