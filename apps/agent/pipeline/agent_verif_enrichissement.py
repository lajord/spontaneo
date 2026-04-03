# ──────────────────────────────────────────────────────────────────
# AGENT 3 — ENRICHISSEMENT DES ENTREPRISES (4 sous-agents)
#
# Role : Pour chaque entreprise, trouver les contacts decideurs
#        (noms, prenoms, emails) et verifier leur pertinence.
# Input : Liste d'entreprises collectees.
# Output : Entreprises enrichies avec contacts qualifies.
#
# Pipeline : 4 sous-agents par entreprise :
#   3A  Crawl site web       → extraire noms/emails
#   3B  Recherche web/Apollo → completer les contacts
#   3C  Verification emails  → generer/verifier avec NeverBounce
#   3D  Qualification + Save → filtrer vs brief, sauvegarder
#
# Etat partage : buffer JSONL par entreprise (tools/buffer_store.py)
# ──────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
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
from tools.enrichment_store import save_enrichment, get_enriched_rows
from tools.contact_draft_store import (
    save_contact_drafts,
    get_contact_draft_rows,
    get_pending_personal_drafts,
    get_personal_drafts,
    get_personal_drafts_without_email,
)
from tools.buffer_store import save_to_buffer, cleanup_buffer, _read_buffer

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


def _sync_drafts_to_buffer(company: dict) -> None:
    """Bridge temporaire: repousse les drafts DB vers le buffer pour 3D."""
    company_name = company.get("name", "Inconnu")
    candidate_id = str(company.get("id", "") or "")
    if not company_name or not candidate_id:
        return

    draft_rows = get_contact_draft_rows(candidate_id)
    existing_entries = _read_buffer(company_name)
    cleanup_buffer(company_name)
    if not draft_rows:
        return

    entries = []
    for draft in draft_rows:
        matching_entry = None
        for item in existing_entries:
            if draft.get("email") and item.get("email") == draft.get("email"):
                matching_entry = item
                break
            if item.get("name") == draft.get("name"):
                matching_entry = item
                break

        entries.append({
            "name": draft.get("name", ""),
            "title": draft.get("title", "") or draft.get("specialty", ""),
            "email": draft.get("email", ""),
            "city": draft.get("city", ""),
            "source": draft.get("sourceTool", "") or draft.get("sourceStage", "") or "draft",
            "email_status": (matching_entry or {}).get("email_status", ""),
        })

    try:
        save_to_buffer.invoke({
            "company_name": company_name,
            "findings_json": json.dumps(entries, ensure_ascii=False),
        })
    except Exception:
        pass

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
def _should_skip_after_crawl(crawl_result: str, drafts_count: int) -> bool:
    """Saute l'entreprise si 3A n'a rien trouve et conclut que le site est inaccessible."""
    crawl_text = (crawl_result or "").lower()
    no_findings = drafts_count == 0
    inaccessible = any(marker in crawl_text for marker in _CRAWL_INACCESSIBLE_MARKERS)
    return no_findings and inaccessible


def _parse_json_object(text: str) -> dict:
    payload = (text or "").strip()
    if not payload:
        return {}
    try:
        return json.loads(payload)
    except Exception:
        start = payload.find("{")
        end = payload.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(payload[start : end + 1])
            except Exception:
                return {}
    return {}


def _parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "oui"}
    return bool(value)


def _normalize_city(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _city_conflicts(target_city: str, draft_city: str) -> bool:
    target = _normalize_city(target_city)
    draft = _normalize_city(draft_city)
    if not target or not draft:
        return False
    return target != draft and target not in draft and draft not in target


def _verify_final_contact_email(draft: dict) -> tuple[bool, str]:
    email = str(draft.get("email", "") or "").strip()
    if not email:
        return False, "missing"

    if bool(draft.get("isTested", False)):
        return True, "already_tested"

    result_text = neverbounce_verify.invoke({"email": email})
    payload = _parse_json_object(result_text)
    status = str(payload.get("email_status") or payload.get("result") or "unknown").lower()

    if status in {"valid", "catchall"}:
        try:
            save_contact_drafts.invoke({
                "drafts_json": json.dumps([
                    {
                        "agentCandidateId": draft.get("agentCandidateId", ""),
                        "name": draft.get("name", ""),
                        "firstName": draft.get("firstName", ""),
                        "lastName": draft.get("lastName", ""),
                        "email": email,
                        "contactType": draft.get("contactType", "personal") or "personal",
                        "isTested": True,
                        "sourceStage": "3D",
                        "sourceTool": "neverbounce_verify",
                        "sourceUrl": draft.get("sourceUrl", "") or "",
                    }
                ], ensure_ascii=False)
            })
        except Exception:
            pass
        return True, status

    return False, status


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
        tools=[crawl_url, perplexity_search, save_contact_drafts],
        prompt=_compact_messages,
    )
    search_agent = create_react_agent(
        model=llm,
        tools=[perplexity_search, apollo_people_search, save_contact_drafts],
        prompt=_compact_messages,
    )
    verify_agent = create_react_agent(
        model=llm,
        tools=[neverbounce_verify, save_contact_drafts],
        prompt=_compact_messages,
    )
    qualify_agent = create_react_agent(
        model=llm,
        tools=[perplexity_search],
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

        candidate_id = str(company.get("id", "") or "")
        drafts_after_crawl = get_contact_draft_rows(candidate_id)

        crawl_fallback = ""
        if _should_skip_after_crawl(crawl_result or "", len(drafts_after_crawl)):
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
        pending_drafts = get_pending_personal_drafts(str(company.get("id", "") or ""))
        if not pending_drafts:
            emit(
                {
                    "type": "log",
                    "phase": "ENRICHISSEMENT",
                    "message": f"{company_name}: aucun draft personnel incomplet a traiter en 3B.",
                },
                log_callback,
            )
        else:
            for draft in pending_drafts:
                search_system_prompt = build_search_prompt(
                    company,
                    draft=draft,
                    crawl_fallback=crawl_fallback,
                )
                search_user_message = build_search_user_message(company, draft=draft)
                append_debug_prompt("ENRICHISSEMENT_3B", search_system_prompt, search_user_message)
                stream_agent(
                    agent=search_agent,
                    system_prompt=search_system_prompt,
                    user_message=search_user_message,
                    recursion_limit=AGENT3B_RECURSION_LIMIT,
                    phase_name="ENRICHISSEMENT_3B",
                    log_callback=log_callback,
                )

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
        pending_email_drafts = get_personal_drafts_without_email(str(company.get("id", "") or ""))

        if not pending_email_drafts:
            emit(
                {
                    "type": "log",
                    "phase": "ENRICHISSEMENT",
                    "message": f"{company_name}: aucun draft personnel sans email a traiter en 3C.",
                },
                log_callback,
            )
        else:
            for draft in pending_email_drafts:
                current_personal_drafts = get_personal_drafts(str(company.get("id", "") or ""))
                current_known_emails = [
                    f"- {item.get('name', 'Inconnu')} | {item.get('email', '')}"
                    for item in current_personal_drafts
                    if item.get("email")
                ]
                current_known_emails_text = (
                    "\n".join(current_known_emails)
                    if current_known_emails
                    else "Aucun email connu dans les drafts."
                )
                verify_system_prompt = build_verify_prompt(
                    company,
                    draft=draft,
                    known_emails=current_known_emails_text,
                )
                verify_user_message = build_verify_user_message(company, draft=draft)
                append_debug_prompt("ENRICHISSEMENT_3C", verify_system_prompt, verify_user_message)
                stream_agent(
                    agent=verify_agent,
                    system_prompt=verify_system_prompt,
                    user_message=verify_user_message,
                    recursion_limit=AGENT3C_RECURSION_LIMIT,
                    phase_name="ENRICHISSEMENT_3C",
                    log_callback=log_callback,
                )

        _sync_drafts_to_buffer(company)
        buffer_entries = _read_buffer(company_name)
        email_status_by_key: dict[str, str] = {}
        for entry in buffer_entries:
            email = str(entry.get("email", "") or "").strip().lower()
            status = str(entry.get("email_status", "") or "").strip().lower()
            if email and status:
                email_status_by_key[f"email:{email}"] = status
            name = str(entry.get("name", "") or "").strip().lower()
            if name and status:
                email_status_by_key[f"name:{name}"] = status

        drafts_for_company: list[dict] = []
        for draft in get_personal_drafts(candidate_id):
            email = str(draft.get("email", "") or "").strip()
            if not email:
                drafts_for_company.append(draft)
                continue
            if bool(draft.get("isTested", False)):
                drafts_for_company.append(draft)
                continue

            verified, verified_status = _verify_final_contact_email(draft)
            if not verified:
                emit(
                    {
                        "type": "log",
                        "phase": "ENRICHISSEMENT",
                        "message": (
                            f"{company_name}: draft supprime avant 3D car email invalide - "
                            f"{draft.get('name', 'Inconnu')} ({verified_status})."
                        ),
                    },
                    log_callback,
                )
                continue

            updated_draft = dict(draft)
            updated_draft["isTested"] = True
            email_status_by_key[f"email:{email.lower()}"] = verified_status
            email_status_by_key[f"name:{str(draft.get('name', '') or '').strip().lower()}"] = verified_status
            drafts_for_company.append(updated_draft)

        qualified_rows: list[dict] = []

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
        for draft in drafts_for_company:
            email = str(draft.get("email", "") or "").strip()
            if not email:
                continue

            if _city_conflicts(company.get("city", ""), draft.get("city", "")):
                emit(
                    {
                        "type": "log",
                        "phase": "ENRICHISSEMENT",
                        "message": (
                            f"{company_name}: contact ignore hors ville cible - "
                            f"{draft.get('name', 'Inconnu')} ({draft.get('city', '')})."
                        ),
                    },
                    log_callback,
                )
                continue

            qualify_system_prompt = build_qualify_prompt(
                company,
                contact_brief=contact_brief,
                draft=draft,
            )
            qualify_user_message = build_qualify_user_message(company, draft=draft)
            append_debug_prompt("ENRICHISSEMENT_3D", qualify_system_prompt, qualify_user_message)
            qualify_result = stream_agent(
                agent=qualify_agent,
                system_prompt=qualify_system_prompt,
                user_message=qualify_user_message,
                recursion_limit=AGENT3D_RECURSION_LIMIT,
                phase_name="ENRICHISSEMENT_3D",
                log_callback=log_callback,
            )

            payload = _parse_json_object(qualify_result)
            if not payload:
                emit(
                    {
                        "type": "log",
                        "phase": "ENRICHISSEMENT",
                        "message": (
                            f"{company_name}: qualification ignoree pour "
                            f"{draft.get('name', 'Inconnu')} (JSON invalide)."
                        ),
                    },
                    log_callback,
                )
                continue

            if _parse_bool(payload.get("discard", False)):
                continue

            try:
                score = float(payload.get("score", 0) or 0)
            except (TypeError, ValueError):
                score = 0.0

            email_status = (
                email_status_by_key.get(f"email:{email.lower()}")
                or email_status_by_key.get(f"name:{str(draft.get('name', '') or '').strip().lower()}")
                or ""
            )

            qualified_rows.append(
                {
                    "company_name": company.get("name", ""),
                    "company_domain": company.get("domain", ""),
                    "company_url": company.get("websiteUrl", ""),
                    "contact_name": draft.get("name", ""),
                    "contact_first_name": draft.get("firstName", ""),
                    "contact_last_name": draft.get("lastName", ""),
                    "contact_email": email,
                    "contact_title": draft.get("title", ""),
                    "email_status": email_status,
                    "source": draft.get("sourceTool", "") or draft.get("sourceStage", "") or "3D",
                    "quality_score": score,
                    "quality_reason": str(payload.get("reason", "") or "").strip(),
                    "is_decision_maker": _parse_bool(payload.get("isDecisionMaker", False)),
                    "contact_city": draft.get("city", ""),
                }
            )

        qualified_rows.sort(key=lambda row: float(row.get("quality_score", 0) or 0), reverse=True)

        selected_contacts: list[dict] = []
        selected_keys: set[str] = set()

        for row in qualified_rows:
            if float(row.get("quality_score", 0) or 0) <= 0.8:
                continue
            key = str(row.get("contact_email", "") or row.get("contact_name", "")).strip().lower()
            if not key or key in selected_keys:
                continue
            selected_contacts.append(row)
            selected_keys.add(key)

        if len(selected_contacts) < 3:
            for row in qualified_rows:
                key = str(row.get("contact_email", "") or row.get("contact_name", "")).strip().lower()
                if not key or key in selected_keys:
                    continue
                selected_contacts.append(row)
                selected_keys.add(key)
                if len(selected_contacts) >= 3:
                    break

        if selected_contacts:
            selected_names = ", ".join(
                row.get("contact_name", "Inconnu") for row in selected_contacts[:3]
            )
            emit(
                {
                    "type": "log",
                    "phase": "ENRICHISSEMENT",
                    "message": (
                        f"{company_name}: enregistrement final de {len(selected_contacts)} contact(s) "
                        f"dans AgentContact ({selected_names})."
                    ),
                },
                log_callback,
            )
            save_result = save_enrichment.invoke({
                "contacts_json": json.dumps(selected_contacts, ensure_ascii=False),
            })
            emit_csv_update(log_callback, "enriched")
            emit(
                {
                    "type": "log",
                    "phase": "ENRICHISSEMENT",
                    "message": f"{company_name}: {save_result}",
                },
                log_callback,
            )
        else:
            emit(
                {
                    "type": "log",
                    "phase": "ENRICHISSEMENT",
                    "message": f"{company_name}: aucun contact final retenu en 3D.",
                },
                log_callback,
            )

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
