# ──────────────────────────────────────────────────────────────────
# AGENT 3 — ENRICHISSEMENT DES ENTREPRISES
#
# Role : Pour chaque entreprise, trouver les contacts decideurs
#        (noms, emails, titres, telephones, LinkedIn).
# Input : Liste d'entreprises collectees/verifiees.
# Output : Entreprises enrichies avec contacts.
#
# Processing : UN run d'agent ReAct par entreprise.
# L'agent est autonome : il decide quelles pages crawler, quand
# utiliser Perplexity, quand utiliser Apollo, quand verifier
# les emails avec NeverBounce.
#
# Outils : crawl_url, perplexity_search, apollo_people_search,
#           neverbounce_verify, save_enrichment, read_enrichment_summary
# ──────────────────────────────────────────────────────────────────

from __future__ import annotations

import csv
import os
from typing import TYPE_CHECKING

from langgraph.prebuilt import create_react_agent

from langchain_core.messages import ToolMessage

from config import AGENT3_RECURSION_LIMIT, AGENT3_TRIM_MAX_CHARS
from pipeline.engine import build_llm, emit, stream_agent, emit_csv_update
from pipeline.prompts import build_enrich_prompt, build_enrich_user_message
from tools.crawl4ai_tool import crawl_url
from tools.perplexity_search import perplexity_search
from tools.apollo_people import apollo_people_search
from tools.neverbounce_verify import neverbounce_verify
from tools.enrichment_store import save_enrichment, read_enrichment_summary, ENRICHED_CSV
from tools.buffer_store import save_to_buffer, evaluate_findings, cleanup_buffer

if TYPE_CHECKING:
    from typing import Callable
    from domains.base import VerticalConfig, Subspecialty


def _compact_messages(state: dict) -> list:
    """Compacte les vieux resultats de tools pour economiser drastiquement les tokens.

    Tous les ToolMessage qui ont deja ete lus et traites par une reponse IA
    (c'est-a-dire qu'un AIMessage apparait apres eux) voient leur contenu brut
    completement supprime. L'Agent se repose uniquement sur ses propres conclusions
    et sur les donnees du buffer.
    """
    messages = state["messages"]
    result = []

    # Trouver l'index du dernier AIMessage.
    # Tous les messages outils avant cet index ont deja ete vus et penses par l'IA.
    last_ai_idx = -1
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].type == "ai":
            last_ai_idx = i
            break

    for i, msg in enumerate(messages):
        if msg.type == "tool" and i < last_ai_idx:
            # Ce tool_message a deja ete "lu" par le LLM. On reduit a neant le contenu.
            result.append(ToolMessage(
                content="[CONTENU SUPPRIME POUR ECONOMISER LES TOKENS - L'agent a deja traite cette information a l'etape precedente.]",
                tool_call_id=msg.tool_call_id,
                name=msg.name if hasattr(msg, "name") else "",
            ))
        else:
            result.append(msg)

    try:
        with open("debug_prompt.txt", "a", encoding="utf-8") as f:
            f.write(f"\n{'-'*40}\nITERATION AGENT 3 (Appel LLM)\n{'-'*40}\n")
            for m in result:
                content = str(m.content)
                if len(content) > 1500:
                    content = content[:1500] + "\n... [TRONQUÉ POUR LE DEBUG]"
                f.write(f"[{m.type.upper()}]\n{content}\n\n")
    except Exception:
        pass

    return result


def _count_enriched() -> int:
    """Compte le nombre total de contacts dans enriched.csv."""
    if not os.path.exists(ENRICHED_CSV):
        return 0
    with open(ENRICHED_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        return sum(1 for _ in reader)


def _read_enriched_for_company(company_name: str) -> list[dict]:
    """Lit les contacts de enriched.csv pour une entreprise donnee."""
    if not os.path.exists(ENRICHED_CSV):
        return []
    normalized = company_name.lower().strip()
    with open(ENRICHED_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        return [
            r for r in reader
            if r.get("company_name", "").lower().strip() == normalized
        ]


def enrich(
    vertical: VerticalConfig,
    candidates: list[dict],
    log_callback: Callable | None = None,
    target_profile: str = "",
    subspecialty: "Subspecialty | None" = None,
) -> list[dict]:
    """Enrichit les entreprises avec les contacts decideurs.

    Itere sur chaque entreprise et lance un agent ReAct autonome
    qui crawle, cherche, et verifie les contacts.

    Args:
        vertical: Config de la verticale
        candidates: Entreprises a enrichir (issues de collect ou verify)
        log_callback: Callback pour le streaming d'events
        target_profile: Profil cible optionnel (ex: "Juriste Compliance")

    Returns:
        Liste des entreprises enrichies avec contacts trouves.
        Chaque dict contient les champs originaux + "contacts" + "contact_count".
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

    # Build LLM + tools (partages entre tous les runs)
    llm = build_llm()
    tools = [
        crawl_url,
        perplexity_search,
        apollo_people_search,
        neverbounce_verify,
        save_to_buffer,
        evaluate_findings,
        save_enrichment,
        read_enrichment_summary,
    ]
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=_compact_messages,
    )

    all_enriched = []

    for i, company in enumerate(candidates):
        company_name = company.get("name", "Inconnu")

        # Log du profil recherche
        search_target = target_profile if target_profile else "Decideurs generaux (associes, partners, DG, directeurs)"
        emit(
            {
                "type": "log",
                "phase": "ENRICHISSEMENT",
                "message": f"On cherche → {search_target}",
            },
            log_callback,
        )

        emit(
            {
                "type": "progress",
                "phase": "enrichissement",
                "current": i + 1,
                "target": len(candidates),
                "message": f"Enrichissement de {company_name} ({i + 1}/{len(candidates)})...",
            },
            log_callback,
        )

        # Build prompts specifiques a cette entreprise
        system_prompt = build_enrich_prompt(
            vertical=vertical,
            company=company,
            target_profile=target_profile,
            subspecialty=subspecialty,
        )
        user_message = build_enrich_user_message(company)

        # Run l'agent pour cette entreprise
        stream_agent(
            agent=agent,
            system_prompt=system_prompt,
            user_message=user_message,
            recursion_limit=AGENT3_RECURSION_LIMIT,
            phase_name="ENRICHISSEMENT",
            log_callback=log_callback,
        )

        # Nettoyer le buffer de cette entreprise
        cleanup_buffer(company_name)

        # Lire les contacts ajoutes pour cette entreprise
        company_contacts = _read_enriched_for_company(company_name)

        # Construire le dict enrichi (champs originaux + contacts)
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

    # Mise a jour CSV finale
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
