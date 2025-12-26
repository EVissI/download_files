from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response

from starlette.middleware.wsgi import WSGIMiddleware

try:
    from bot.flask_admin.appbuilder_main import create_app_for_flask_cli

    flask_app = create_app_for_flask_cli()
except Exception:
    flask_app = None

from bot.routers.hint_viewer_router import hint_viewer_api_router
from bot.routers.short_board import short_board_api_router


class NoCacheStaticFiles(StaticFiles):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


app = FastAPI(title="Backgammon Hint Viewer API", version="1.0.0")

# CORS middleware for web app integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", NoCacheStaticFiles(directory="bot/static"), name="static")
templates = Jinja2Templates(directory="bot/templates")

# Include routers
app.include_router(hint_viewer_api_router, prefix="")
app.include_router(short_board_api_router, prefix="")

# Mount Flask admin under /admin (WSGI) if available
if flask_app is not None:
    app.mount("/admin", WSGIMiddleware(flask_app), name="admin")
