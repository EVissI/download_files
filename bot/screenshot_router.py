from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import asyncio
import aiohttp
from loguru import logger

screenshot_api_router = APIRouter()

class ScreenshotRequest(BaseModel):
    state: dict
    chat_id: str

