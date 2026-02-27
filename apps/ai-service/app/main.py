import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.creation_campagne.router import router as creation_campagne_router
from app.recuperation_data.router import router as recuperation_data_router
from app.enrichissement.router import router as enrichissement_router
from app.generation_mail.router import router as generation_mail_router

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
# Couper les logs verbeux des librairies tierces
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

app = FastAPI(
    title="Spontaneo AI Service",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    creation_campagne_router,
    prefix="/api/v1/creation-campagne",
    tags=["creation-campagne"],
)
app.include_router(
    recuperation_data_router,
    prefix="/api/v1/recuperation-data",
    tags=["recuperation-data"],
)
app.include_router(
    enrichissement_router,
    prefix="/api/v1/enrichissement",
    tags=["enrichissement"],
)
app.include_router(
    generation_mail_router,
    prefix="/api/v1/generation-mail",
    tags=["generation-mail"],
)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "spontaneo-ai"}
