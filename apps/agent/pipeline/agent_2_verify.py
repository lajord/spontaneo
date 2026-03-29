# ──────────────────────────────────────────────────────────────────
# AGENT 2 — VERIFICATION DE PERTINENCE (optionnel)
#
# Role : Verifier que chaque candidat correspond bien a ce qu'on
#        cherche en crawlant son site web.
# Input : Liste de candidats bruts issus de la collecte.
# Output : Liste filtree avec un score de pertinence et les raisons.
#
# Cette etape est OPTIONNELLE. Elle peut etre skippee si la
# collecte est deja suffisamment precise ou si le budget est
# limite. Quand elle est active, elle crawle la homepage puis
# la page d'expertises pour confirmer la nature et la specialite
# de l'entreprise.
# ──────────────────────────────────────────────────────────────────

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Callable
    from domains.base import VerticalConfig, Subspecialty


def verify(
    vertical: VerticalConfig,
    candidates: list[dict],
    subspecialty: Subspecialty | None,
    log_callback: Callable | None = None,
) -> list[dict]:
    """Verifie la pertinence des candidats par crawl web.

    Args:
        vertical: Config de la verticale (criteres de rejet, pages a explorer...)
        candidates: Liste de candidats bruts depuis agent_1
        subspecialty: Sous-specialite a verifier
        log_callback: Callback pour le streaming d'events

    Returns:
        Liste de candidats verifies avec score et raison.
    """
    # TODO: Implementer avec crawl_url + save_verification
    return candidates
