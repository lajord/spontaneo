from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import generation

app = FastAPI(
    title="Spontaneo AI Service",
    description="Service IA pour la génération de candidatures spontanées",
    version="0.1.0",
)

# CORS — autoriser le frontend Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(generation.router, prefix="/api/v1/generation", tags=["generation"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "spontaneo-ai"}
