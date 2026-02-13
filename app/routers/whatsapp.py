from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.dependencies import get_current_user
from app.models import User
from app.whatsapp_service import send_whatsapp_text

router = APIRouter(prefix="/api/whatsapp", tags=["WhatsApp"])


class SendTextRequest(BaseModel):
    to: str
    message: str


@router.post("/send-text")
async def send_text(
    body: SendTextRequest,
    user: User = Depends(get_current_user),
):
    """Send a WhatsApp text message (JWT-protected)."""
    try:
        result = await send_whatsapp_text(body.to, body.message)
        return {"status": "sent", "whatsapp_response": result}
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"WhatsApp API error: {e}")
