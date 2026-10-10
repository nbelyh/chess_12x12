"""Веб-сервер: отдаёт страницу и картинки, переносит JSON между WebSocket и Hub."""

import asyncio
import contextlib
import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from web.hub import Connection, Hub

SRC_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = SRC_DIR / 'web' / 'static'
IMAGES_DIR = SRC_DIR / 'images'
MAX_MESSAGE = 4096

hub = Hub()


async def garbage_collector():
    while True:
        await asyncio.sleep(60)
        hub.collect_garbage()


@contextlib.asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(garbage_collector())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')
app.mount('/images', StaticFiles(directory=IMAGES_DIR), name='images')


@app.get('/')
async def index():
    return FileResponse(STATIC_DIR / 'index.html', headers={'Cache-Control': 'no-cache'})


@app.get('/health')
async def health():
    return {'ok': True, 'rooms': len(hub.rooms), 'connections': len(hub.conns)}


@app.websocket('/ws')
async def websocket(ws: WebSocket):
    await ws.accept()
    conn = Connection(ws.send_json)
    await hub.connect(conn)
    try:
        while True:
            text = await ws.receive_text()
            if len(text) > MAX_MESSAGE:
                continue
            try:
                msg = json.loads(text)
            except ValueError:
                continue
            await hub.handle(conn, msg)
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(conn)
