from dataclasses import dataclass, field


@dataclass(frozen=True)
class Subspecialty:
    """Une sous-specialite (optionnelle) au sein d'une verticale."""

    id: int
    name: str


@dataclass(frozen=True)
class VerticalConfig:
    """Configuration d'une verticale de recherche.

    C'est simple : un id, un label, et les prompts pour chaque agent.
    Toute l'intelligence metier est DANS les prompts, pas dans des champs structures.
    """

    id: str                     # "cabinets", "banques", "fonds"
    domain: str                 # "droit"
    label_fr: str               # "Cabinets d'avocats"

    # Prompt metier pour l'agent de collecte (Agent 1)
    # Contient : quels outils utiliser, comment, dans quel ordre, avec quels termes
    collect_prompt: str

    # Prompt metier pour l'agent de verification (Agent 2) — pour plus tard
    verify_prompt: str = ""

    # Prompt metier pour l'agent d'enrichissement (Agent 3)
    # Contient : types de decideurs, pages a crawler, patterns d'emails, strategie de fallback
    enrich_prompt: str = ""

    # Si True, n'envoie pas la sous-specialite a l'agent de collecte (Agent 1)
    # car la verticale doit chercher TOUTES les entites (ex: banques) et utiliser la specialite uniquement en Agent 3
    ignore_subspecialty_in_collect: bool = False

    # Sous-specialites (optionnelles)
    subspecialties: dict[int, Subspecialty] = field(default_factory=dict)
