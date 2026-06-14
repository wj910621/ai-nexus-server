from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.database import engine, Base
from app.routes import auth, chat, knowledge, skills, files, sandbox
from app.websocket.manager import router as ws_router

@asynccontextmanager
async def lifespan(app):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title='Nexus AI Studio API', version='1.0.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
app.include_router(auth.router, prefix='/api/auth', tags=['Auth'])
app.include_router(chat.router, prefix='/api', tags=['Chat'])
app.include_router(knowledge.router, prefix='/api', tags=['Knowledge'])
app.include_router(skills.router, prefix='/api', tags=['Skills'])
app.include_router(files.router, prefix='/api', tags=['Files'])
app.include_router(sandbox.router, prefix='/api', tags=['Sandbox'])
app.include_router(ws_router, prefix='/ws', tags=['WebSocket'])

@app.get('/api/health')
def health():
    return {'status': 'ok', 'version': '1.0.0'}
