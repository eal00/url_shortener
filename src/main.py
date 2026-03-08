import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from src.auth import router as auth_router
from src.background_tasks import run_background_tasks
from src.database import close_db, init_db
from src.links import router as links_router
from src.redirect import router as redirect_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    task = asyncio.create_task(run_background_tasks())

    yield

    task.cancel()
    with suppress(asyncio.CancelledError):
        await task

    await close_db()


app = FastAPI(title="URL shortener", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return RedirectResponse(url="/docs")


app.include_router(auth_router)
app.include_router(links_router)
app.include_router(redirect_router)
