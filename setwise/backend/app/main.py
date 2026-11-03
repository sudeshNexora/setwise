from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import auth, grading, papers, uploads

app = FastAPI(title="Setwise API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(uploads.router)
app.include_router(papers.router)
app.include_router(grading.router)


@app.on_event("startup")
def startup() -> None:
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.export_dir).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)


@app.get("/api/health")
def health():
    # ai_configured tells you at a glance whether GEMINI_API_KEY was picked up
    return {"status": "ok", "ai_configured": bool(settings.gemini_api_key), "ai_model": settings.gemini_model}
