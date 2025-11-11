from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from bot.routers.admin.hint_viewer_router import hint_viewer_api_router

app = FastAPI(title="Backgammon Hint Viewer API", version="1.0.0")

# CORS middleware for web app integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="bot/static"), name="static")
templates = Jinja2Templates(directory="bot/templates")

# Include routers
app.include_router(hint_viewer_api_router, prefix="")