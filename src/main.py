import os
import asyncio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    async def _preload():
        from .websocket.handler import _get_pipeline
        await asyncio.to_thread(_get_pipeline)
    asyncio.create_task(_preload())
    yield


app = FastAPI(title="Smart Assistant", lifespan=lifespan)

from .websocket.handler import router

app.include_router(router)

static_dir = os.path.join(os.path.dirname(__file__), "static")


@app.get("/")
async def root():
    return FileResponse(os.path.join(static_dir, "index.html"))


@app.get("/health")
async def health():
    return {"status": "ok"}


if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
