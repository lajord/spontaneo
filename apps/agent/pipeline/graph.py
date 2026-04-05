# ──────────────────────────────────────────────────────────────────
# GRAPH — PIPELINE PRINCIPAL
#
# Orchestre les agents en 3 etapes :
#
#   ┌──────────┐    ┌──────────┐    ┌──────────────────┐
#   │ AGENT 0  │───▶│ AGENT 1  │───▶│     AGENT 3      │
#   │ Planning │    │ Collecte │    │  Enrichissement   │
#   └──────────┘    └──────────┘    └──────────────────┘
#
# Agent 0 analyse le job title et produit 2 briefs :
#   - collect_brief  → guide la recherche d'entreprises
#   - contact_brief  → guide le ciblage de contacts
# ──────────────────────────────────────────────────────────────────

from __future__ import annotations
from typing import TYPE_CHECKING

from pipeline.agent_0_plan import plan
from pipeline.agent_deep_search import collect
from pipeline.agent_verif_enrichissement import enrich
from tools.candidate_store import set_agent_context, get_candidates_rows

if TYPE_CHECKING:
    from typing import Callable


# ── Helpers pour persister les briefs dans le job payload ────

import os
import requests


def _web_url() -> str:
    return os.getenv("WEB_URL", "http://web:3000")


def _headers() -> dict:
    token = os.getenv("AGENT_INTERNAL_API_TOKEN") or os.getenv("CRON_SECRET")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {"X-Agent-Dev-Internal": "1"}


def _save_briefs(job_id: str, collect_brief: str, contact_brief: str) -> None:
    """Persiste les briefs dans le payload du job (pour la phase enrich)."""
    if not job_id:
        return
    try:
        requests.patch(
            f"{_web_url()}/api/agent/job/{job_id}/payload",
            json={
                "collect_brief": collect_brief,
                "contact_brief": contact_brief,
            },
            headers=_headers(),
            timeout=10,
        )
    except Exception:
        pass


def _load_briefs(job_id: str) -> tuple[str, str]:
    """Charge collect_brief et contact_brief depuis le payload du job."""
    if not job_id:
        return "", ""
    try:
        resp = requests.get(
            f"{_web_url()}/api/agent/job/{job_id}/payload",
            headers=_headers(),
            timeout=10,
        )
        if resp.ok:
            data = resp.json()
            return data.get("collect_brief", ""), data.get("contact_brief", "")
    except Exception:
        pass
    return "", ""


def run_pipeline(
    secteur: str,
    query: str,
    job_title: str = "",
    target_count: int = 50,
    log_callback: Callable | None = None,
    user_id: str = "anonymous",
    job_id: str | None = None,
    campaign_id: str | None = None,
    location: str = "",
    mode: str = "full",
) -> list[dict]:
    """Pipeline principal — supporte 3 modes :

    - "full"    : plan → collect → enrich (comportement original)
    - "collect" : plan → collect → sauvegarde contact_brief → stop
    - "enrich"  : charge candidates depuis DB + contact_brief → enrich

    Args:
        secteur: ID du secteur (cabinets, banques, fonds)
        query: Requete utilisateur (ville, precisions...)
        job_title: Poste vise par l'utilisateur
        target_count: Nombre d'entreprises a trouver
        log_callback: Callback pour le streaming SSE
        user_id: ID de l'utilisateur (pour la BDD)
        job_id: ID du job en cours
        campaign_id: ID de la campagne (optionnel)
        location: Ville / zone de la recherche (pour tracabilite BDD)
        mode: "full" | "collect" | "enrich"

    Returns:
        Liste finale d'entreprises (enrichies en mode full/enrich,
        collectees en mode collect).
    """
    # — Etape 0 : Injection du contexte utilisateur (pour la BDD) —
    set_agent_context(
        user_id=user_id,
        job_id=job_id,
        campaign_id=campaign_id,
        secteur=secteur,
        job_title=job_title,
        location=location,
        target_count=target_count,
    )

    # ── MODE ENRICH : charger les données depuis la DB ──────────────
    if mode == "enrich":
        collect_brief, contact_brief = _load_briefs(job_id or "")

        # Charger les candidates (status=pending) depuis la DB via l'API web
        rows = get_candidates_rows()
        candidates = [
            {
                "id": r.get("id", ""),
                "name": r.get("name", ""),
                "websiteUrl": r.get("websiteUrl", ""),
                "domain": r.get("domain", ""),
                "city": r.get("city", ""),
                "description": r.get("description", ""),
                "source": r.get("source", ""),
            }
            for r in rows
            if r.get("status") == "pending"
        ]

        return enrich(
            candidates=candidates,
            log_callback=log_callback,
            contact_brief=contact_brief,
            collect_brief=collect_brief,
        )

    # ── MODE COLLECT ou FULL : plan + collect ───────────────────────

    # — Etape 1 : Planning (analyse du job title) —
    collect_brief, contact_brief = plan(
        secteur=secteur,
        job_title=job_title,
        location=query,
        log_callback=log_callback,
    )

    # — Etape 2 : Collecte —
    candidates = collect(
        query=query,
        collect_brief=collect_brief,
        log_callback=log_callback,
        batch_size=target_count,
        secteur=secteur,
    )

    if mode == "collect":
        # Persister les briefs pour la phase enrich ulterieure
        _save_briefs(job_id or "", collect_brief, contact_brief)
        return candidates

    # ── MODE FULL : enchainer avec l'enrichissement ─────────────────

    # — Etape 3 : Enrichissement —
    enriched = enrich(
        candidates=candidates,
        log_callback=log_callback,
        contact_brief=contact_brief,
        collect_brief=collect_brief,
    )

    return enriched
