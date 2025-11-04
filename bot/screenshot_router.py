from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import asyncio
import aiohttp
from loguru import logger

screenshot_api_router = APIRouter()

class ScreenshotRequest(BaseModel):
    state: dict
    chat_id: str

@screenshot_api_router.post("/api/screenshot")
async def take_screenshot(request: ScreenshotRequest):
    """
    Принимает состояние игры и chat_id, делает скриншот через Next.js API и отправляет в Telegram.
    """
    try:
        # Отправляем запрос на Next.js API
        async with aiohttp.ClientSession() as session:
            payload = {
                "state": request.state,
                "chat_id": request.chat_id
            }
            async with session.post("http://localhost:3000/api/screenshot", json=payload) as resp:
                if resp.status != 200:
                    raise HTTPException(status_code=500, detail="Failed to generate screenshot")
                result = await resp.json()
                return result
    except Exception as e:
        logger.error(f"Error taking screenshot: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")