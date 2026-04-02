# ──────────────────────────────────────────────────────────────────
# AGENT 3 — ENRICHISSEMENT DES ENTREPRISES (4 sous-agents)
#
# Role : Pour chaque entreprise, trouver les contacts decideurs
#        (noms, prenoms, emails) et verifier leur pertinence.
# Input : Liste d'entreprises collectees.
# Output : Entreprises enrichies avec contacts qualifies.
#
# Pipeline : 4 sous-agents par entreprise :
#   3A  Crawl site web       → extraire noms/emails, deduire pattern
#   3B  Recherche web/Apollo → completer les contacts
#   3C  Verification emails  → generer/verifier avec NeverBounce
#   3D  Qualification + Save → filtrer vs brief, sauvegarder
#
# Etat partage : buffer JSONL par entreprise (tools/buffer_store.py)
# ──────────────────────────────────────────────────────────────────

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from langgraph.prebuilt import create_react_agent
from langchain_core.messages import ToolMessage

from config import (
    AGENT3A_RECURSION_LIMIT,
    AGENT3B_RECURSION_LIMIT,
    AGENT3C_RECURSION_LIMIT,
    AGENT3D_RECURSION_LIMIT,
)
from pipeline.engine import append_debug_prompt, build_llm, emit, stream_agent, emit_csv_update
from pipeline.prompts import (
    build_crawl_prompt, build_crawl_user_message,
    build_search_prompt, build_search_user_message,
    build_verify_prompt, build_verify_user_message,
    build_qualify_prompt, build_qualify_user_message,
)
from tools.crawl4ai_tool import crawl_url
from tools.perplexity_search import perplexity_search
from tools.apollo_people import apollo_people_search
from tools.neverbounce_verify import neverbounce_verify
from tools.enrichment_store import save_enrichment, read_enrichment_summary, get_enriched_rows
from tools.buffer_store import save_to_buffer, evaluate_findings, cleanup_buffer

if TYPE_CHECKING:
    from typing import Callable


# ── Helpers ────────────────────────────────────────────────────────

def _compact_messages(state: dict) -> list:
    """Compacte les vieux resultats de tools pour economiser les tokens."""
    messages = state["messages"]
    result = []

    last_ai_idx = -1
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].type == "ai":
            last_ai_idx = i
            break

    for i, msg in enumerate(messages):
        if msg.type == "tool" and i < last_ai_idx:
            result.append(ToolMessage(
                content="[SUPPRIME - deja traite]",
                tool_call_id=msg.tool_call_id,
                name=msg.name if hasattr(msg, "name") else "",
            ))
        else:
            result.append(msg)

    return result


def _read_enriched_for_company(company_name: str) -> list[dict]:
    """Lit les contacts enrichis pour une entreprise donnee."""
    normalized = company_name.lower().strip()
    return [
        row for row in get_enriched_rows()
        if row.get("company_name", "").lower().strip() == normalized
    ]


def _get_buffer_summary(company_name: str) -> str:
    """Appelle evaluate_findings pour obtenir le resume du buffer."""
    try:
        return evaluate_findings.invoke(company_name)
    except Exception:
        return "Buffer vide ou erreur de lecture."


_PATTERN_RE = re.compile(r"pattern[:\s]+([\w.]+@[\w.]+)", re.IGNORECASE)
_CRAWL_INACCESSIBLE_MARKERS = (
    "domaine ne semble pas accessible",
    "site inaccessible",
    "impossible d'acceder",
    "impossible d’accéder",
    "aucun contenu exploitable",
    "url inaccessible",
    "erreur http",
    "erreur crawl",
    "timeout",
)


def _extract_email_pattern(last_ai_text: str) -> str:
    """Extrait le pattern email du dernier message AI du sous-agent crawl."""
    if not last_ai_text:
        return ""
    match = _PATTERN_RE.search(last_ai_text)
    if match:
        return match.group(1)
    # Chercher des patterns courants mentionnes dans le texte
    for pattern in ["prenom.nom@", "p.nom@", "nom.prenom@", "firstname.lastname@"]:
        if pattern in last_ai_text.lower():
            return pattern
    return ""


def _should_skip_after_crawl(crawl_result: str, buffer_summary: str) -> bool:
    """Saute l'entreprise si 3A n'a rien trouve et conclut que le site est inaccessible."""
    crawl_text = (crawl_result or "").lower()
    buffer_text = (buffer_summary or "").lower()
    no_findings = (
        not buffer_text
        or "aucune trouvaille dans le buffer" in buffer_text
        or "buffer vide" in buffer_text
    )
    inaccessible = any(marker in crawl_text for marker in _CRAWL_INACCESSIBLE_MARKERS)
    return no_findings and inaccessible


# ── Orchestration principale ──────────────────────────────────────

def enrich(
    candidates: list[dict],
    log_callback: Callable | None = None,
    contact_brief: str = "",
    collect_brief: str = "",
    **kwargs,
) -> list[dict]:
    """Enrichit les entreprises avec les contacts decideurs.

    4 sous-agents par entreprise :
      3A (crawl) → 3B (search) → 3C (verify) → 3D (qualify & save)
    """
    emit(
        {"type": "phase", "name": "ENRICHISSEMENT", "message": "AGENT 3 — ENRICHISSEMENT"},
        log_callback,
    )

    if not candidates:
        emit(
            {"type": "log", "phase": "ENRICHISSEMENT", "message": "Aucune entreprise a enrichir."},
            log_callback,
        )
        return []

    llm = build_llm()

    # ── 4 agents specialises (crees une seule fois) ───────────
    crawl_agent = create_react_agent(
        model=llm,
        tools=[crawl_url, save_to_buffer],
        prompt=_compact_messages,
    )
    search_agent = create_react_agent(
        model=llm,
        tools=[perplexity_search, apollo_people_search, save_to_buffer],
        prompt=_compact_messages,
    )
    verify_agent = create_react_agent(
        model=llm,
        tools=[neverbounce_verify, save_to_buffer],
        prompt=_compact_messages,
    )
    qualify_agent = create_react_agent(
        model=llm,
        tools=[
            perplexity_search, evaluate_findings, save_to_buffer,
            save_enrichment, read_enrichment_summary,
        ],
        prompt=_compact_messages,
    )

    all_enriched = []

    for i, company in enumerate(candidates):
        company_name = company.get("name", "Inconnu")
        total = len(candidates)

        # ── 3A — Crawl du site web ────────────────────────────
        emit(
            {
                "type": "progress",
                "phase": "enrichissement",
                "current": i + 1,
                "target": total,
                "message": f"[3A] Crawl de {company_name} ({i + 1}/{total})...",
            },
            log_callback,
        )
        crawl_system_prompt = build_crawl_prompt(company, contact_brief, collect_brief)
        crawl_user_message = build_crawl_user_message(company)
        append_debug_prompt("ENRICHISSEMENT_3A", crawl_system_prompt, crawl_user_message)
        crawl_result = stream_agent(
            agent=crawl_agent,
            system_prompt=crawl_system_prompt,
            user_message=crawl_user_message,
            recursion_limit=AGENT3A_RECURSION_LIMIT,
            phase_name="ENRICHISSEMENT_3A",
            log_callback=log_callback,
        )

        # Extraire le pattern email du dernier message AI
        email_pattern = _extract_email_pattern(crawl_result or "")
        buffer_summary = _get_buffer_summary(company_name)

        crawl_fallback = ""
        if _should_skip_after_crawl(crawl_result or "", buffer_summary):
            crawl_fallback = (
                "Le crawl 3A n'a rien donne et le site initial semble inaccessible. "
                "Avant toute autre recherche, utilise Perplexity pour retrouver l'URL "
                "officielle correcte du cabinet/entreprise, puis sers-t'en pour continuer."
            )
            emit(
                {
                    "type": "log",
                    "phase": "ENRICHISSEMENT",
                    "message": (
                        f"{company_name}: site inaccessible detecte en 3A, "
                        "fallback 3B via Perplexity pour retrouver l'URL officielle."
                    ),
                },
                log_callback,
            )

        # ── 3B — Recherche web/Apollo ─────────────────────────
        emit(
            {
                "type": "progress",
                "phase": "enrichissement",
                "current": i + 1,
                "target": total,
                "message": f"[3B] Recherche contacts {company_name} ({i + 1}/{total})...",
            },
            log_callback,
        )
        search_system_prompt = build_search_prompt(
            company,
            contact_brief,
            buffer_summary,
            crawl_fallback,
        )
        search_user_message = build_search_user_message(company)
        append_debug_prompt("ENRICHISSEMENT_3B", search_system_prompt, search_user_message)
        stream_agent(
            agent=search_agent,
            system_prompt=search_system_prompt,
            user_message=search_user_message,
            recursion_limit=AGENT3B_RECURSION_LIMIT,
            phase_name="ENRICHISSEMENT_3B",
            log_callback=log_callback,
        )

        buffer_summary = _get_buffer_summary(company_name)

        # ── 3C — Verification emails ─────────────────────────
        emit(
            {
                "type": "progress",
                "phase": "enrichissement",
                "current": i + 1,
                "target": total,
                "message": f"[3C] Verification emails {company_name} ({i + 1}/{total})...",
            },
            log_callback,
        )
        verify_system_prompt = build_verify_prompt(company, buffer_summary, email_pattern)
        verify_user_message = build_verify_user_message(company)
        append_debug_prompt("ENRICHISSEMENT_3C", verify_system_prompt, verify_user_message)
        stream_agent(
            agent=verify_agent,
            system_prompt=verify_system_prompt,
            user_message=verify_user_message,
            recursion_limit=AGENT3C_RECURSION_LIMIT,
            phase_name="ENRICHISSEMENT_3C",
            log_callback=log_callback,
        )

        buffer_summary = _get_buffer_summary(company_name)

        # ── 3D — Qualification et sauvegarde ──────────────────
        emit(
            {
                "type": "progress",
                "phase": "enrichissement",
                "current": i + 1,
                "target": total,
                "message": f"[3D] Qualification contacts {company_name} ({i + 1}/{total})...",
            },
            log_callback,
        )
        qualify_system_prompt = build_qualify_prompt(company, contact_brief, buffer_summary)
        qualify_user_message = build_qualify_user_message(company)
        append_debug_prompt("ENRICHISSEMENT_3D", qualify_system_prompt, qualify_user_message)
        stream_agent(
            agent=qualify_agent,
            system_prompt=qualify_system_prompt,
            user_message=qualify_user_message,
            recursion_limit=AGENT3D_RECURSION_LIMIT,
            phase_name="ENRICHISSEMENT_3D",
            log_callback=log_callback,
        )

        # ── Nettoyage et lecture resultats ─────────────────────
        cleanup_buffer(company_name)

        company_contacts = _read_enriched_for_company(company_name)

        enriched_company = dict(company)
        enriched_company["contacts"] = company_contacts
        enriched_company["contact_count"] = len(company_contacts)
        all_enriched.append(enriched_company)

        emit(
            {
                "type": "log",
                "phase": "ENRICHISSEMENT",
                "message": f"{company_name}: {len(company_contacts)} contacts trouves.",
            },
            log_callback,
        )

    emit_csv_update(log_callback, "enriched")

    total_contacts = sum(c.get("contact_count", 0) for c in all_enriched)
    emit(
        {
            "type": "progress",
            "phase": "enrichissement",
            "current": len(candidates),
            "target": len(candidates),
            "message": f"Enrichissement termine : {total_contacts} contacts pour {len(candidates)} entreprises.",
        },
        log_callback,
    )

    return all_enriched
