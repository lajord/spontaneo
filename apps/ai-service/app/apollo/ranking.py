import json
import re
import logging

from app.models.schemas import EnrichedContact
from app.apollo.schemas import RankedContact
from app.utils.ai_caller import call_ai
from app.core.config import settings

logger = logging.getLogger(__name__)

RANKING_SYSTEM_PROMPT = """Tu es un expert en recrutement et en hiérarchie d'entreprise.
On te donne une liste de contacts trouvés pour une entreprise, avec leurs noms, prénoms et rôles.
Tu dois attribuer un score de 0 à 100 à chaque contact selon deux critères :

1. **Pertinence recrutement** (50%) : La personne est-elle liée au recrutement ?
   - DRH, Responsable RH, Talent Acquisition, Recruteur → score élevé
   - Gérant, PDG de petite entreprise (souvent gère les recrutements) → score moyen-élevé
   - Directeur général, CEO → score moyen
   - Rôles techniques sans lien RH → score bas

2. **Importance hiérarchique** (50%) : Quel est le niveau de décision de la personne ?
   - C-level (PDG, DG, CEO, CFO) → score élevé
   - Directeur, VP → score moyen-élevé
   - Manager, Responsable → score moyen
   - Employé, Assistant → score bas

Les contacts de type "generique" (emails comme contact@, info@) reçoivent un score de 15.

Réponds UNIQUEMENT avec un JSON valide au format :
{
  "rankings": [
    {"index": 0, "score": 85, "reason": "DRH, décideur direct du recrutement"},
    {"index": 1, "score": 60, "reason": "CEO petite entreprise, impliqué dans les embauches"}
  ]
}
L'index correspond à la position du contact dans la liste fournie (commence à 0).
Ne fournis aucun texte en dehors du JSON."""


def _build_ranking_prompt(
    contacts: list[EnrichedContact],
    company_name: str,
    job_title: str,
) -> str:
    lines = [f"Entreprise : {company_name}", f"Poste recherché : {job_title}", "", "Contacts trouvés :"]
    for i, c in enumerate(contacts):
        parts = [f"[{i}]", f"type={c.type}"]
        if c.prenom:
            parts.append(f"prénom={c.prenom}")
        if c.nom:
            parts.append(f"nom={c.nom}")
        if c.role:
            parts.append(f"rôle={c.role}")
        if c.mail:
            parts.append(f"mail={c.mail}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def _parse_ranking_response(raw: str, contact_count: int) -> list[dict]:
    """Parse la réponse JSON du ranking."""
    def _extract(data) -> list[dict]:
        if isinstance(data, dict):
            rankings = data.get("rankings")
            if isinstance(rankings, list):
                return rankings
        return []

    try:
        return _extract(json.loads(raw))
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if match:
        try:
            return _extract(json.loads(match.group(1)))
        except json.JSONDecodeError:
            pass

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return _extract(json.loads(match.group(0)))
        except json.JSONDecodeError:
            pass

    return []


async def rank_contacts(
    contacts: list[EnrichedContact],
    company_name: str,
    job_title: str = "",
) -> list[RankedContact]:
    """Envoie les contacts à Gemini pour scoring par pertinence recrutement.

    Retourne les contacts triés par score décroissant.
    En cas d'échec, retourne tous les contacts avec score=50.
    """
    if not contacts:
        return []

    prompt = _build_ranking_prompt(contacts, company_name, job_title)

    try:
        raw = await call_ai(
            model=settings.MODEL_RANKING,
            prompt=prompt,
            system_prompt=RANKING_SYSTEM_PROMPT,
            temperature=0.2,
        )
        rankings = _parse_ranking_response(raw, len(contacts))
    except Exception as e:
        logger.error(f"[RANKING] Échec Gemini pour {company_name}: {e}")
        rankings = []

    # Construire un mapping index → (score, reason)
    score_map: dict[int, tuple[int, str]] = {}
    for r in rankings:
        idx = r.get("index")
        score = r.get("score", 50)
        reason = r.get("reason", "")
        if isinstance(idx, int) and 0 <= idx < len(contacts):
            score_map[idx] = (score, reason)

    # Construire la liste finale
    ranked: list[RankedContact] = []
    for i, contact in enumerate(contacts):
        score, reason = score_map.get(i, (50, "Score par défaut"))
        ranked.append(RankedContact(contact=contact, score=score, reason=reason))

    # Tri décroissant par score
    ranked.sort(key=lambda r: r.score, reverse=True)

    logger.info(
        f"[RANKING] {company_name} → {len(ranked)} contacts classés, "
        f"top score={ranked[0].score if ranked else 'N/A'}"
    )

    return ranked
