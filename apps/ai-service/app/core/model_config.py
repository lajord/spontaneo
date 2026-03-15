"""
Lecture dynamique des modeles IA depuis la table AppConfig (PostgreSQL).
Cache TTL de 30 secondes pour eviter de requeter la DB a chaque appel IA.
Fallback sur les valeurs de settings si la DB est inaccessible.
"""

import time
import logging
from dataclasses import dataclass

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Dataclass retournee par get_models() ─────────────────────────────────────

@dataclass
class ModelConfig:
    MODEL_ENRICHISSEMENT: str
    MODEL_ENRICHISSEMENT_2: str
    MODEL_CREATION_MAIL: str
    MODEL_CREATION_LM: str
    MODEL_KEYWORDS: str
    MODEL_CV_READER: str
    MODEL_RANKING: str
    MODEL_FILTER: str


# ── Cache interne ────────────────────────────────────────────────────────────

_cache: dict = {"config": None, "ts": 0.0}
_TTL = 30  # secondes


def _defaults() -> ModelConfig:
    """Fallback : valeurs de settings (elles-memes issues du .env ou defaults)."""
    return ModelConfig(
        MODEL_ENRICHISSEMENT=settings.MODEL_ENRICHISSEMENT,
        MODEL_ENRICHISSEMENT_2=settings.MODEL_ENRICHISSEMENT_2,
        MODEL_CREATION_MAIL=settings.MODEL_CREATION_MAIL,
        MODEL_CREATION_LM=settings.MODEL_CREATION_LM,
        MODEL_KEYWORDS=settings.MODEL_KEYWORDS,
        MODEL_CV_READER=settings.MODEL_CV_READER,
        MODEL_RANKING=settings.MODEL_RANKING,
        MODEL_FILTER=settings.MODEL_FILTER,
    )


# Mapping colonnes DB (camelCase Prisma) → attributs ModelConfig
_DB_TO_ATTR = {
    "modelEnrichissement": "MODEL_ENRICHISSEMENT",
    "modelEnrichissement2": "MODEL_ENRICHISSEMENT_2",
    "modelCreationMail": "MODEL_CREATION_MAIL",
    "modelCreationLm": "MODEL_CREATION_LM",
    "modelKeywords": "MODEL_KEYWORDS",
    "modelCvReader": "MODEL_CV_READER",
    "modelRanking": "MODEL_RANKING",
    "modelFilter": "MODEL_FILTER",
}


async def _fetch_from_db() -> ModelConfig | None:
    """Requete directe PostgreSQL via httpx + la connection string Supabase."""
    if not settings.DATABASE_URL:
        return None

    try:
        # On utilise asyncpg pour une requete simple
        import asyncpg  # type: ignore

        conn = await asyncpg.connect(settings.DATABASE_URL)
        try:
            row = await conn.fetchrow(
                'SELECT * FROM "AppConfig" WHERE id = $1', "singleton"
            )
        finally:
            await conn.close()

        if not row:
            return None

        defaults = _defaults()
        kwargs = {}
        for db_col, attr in _DB_TO_ATTR.items():
            val = row[db_col] if db_col in row.keys() else None
            kwargs[attr] = val if val else getattr(defaults, attr)

        config = ModelConfig(**kwargs)
        logger.info(
            f"[MODEL_CONFIG] Chargé depuis DB : "
            f"mail={config.MODEL_CREATION_MAIL}, "
            f"lm={config.MODEL_CREATION_LM}, "
            f"keywords={config.MODEL_KEYWORDS}, "
            f"ranking={config.MODEL_RANKING}"
        )
        return config

    except Exception as e:
        logger.warning(f"[MODEL_CONFIG] DB read failed, using defaults: {e}")
        return None


async def get_models() -> ModelConfig:
    """
    Retourne la config des modeles IA.
    Lit depuis la DB avec cache TTL de 30s. Fallback sur settings si erreur.
    """
    now = time.time()
    if _cache["config"] is not None and (now - _cache["ts"]) < _TTL:
        return _cache["config"]

    db_config = await _fetch_from_db()
    if db_config:
        _cache["config"] = db_config
        _cache["ts"] = now
        return db_config

    defaults = _defaults()
    _cache["config"] = defaults
    _cache["ts"] = now
    return defaults
