"""Domaine Droit — enregistre les 3 verticales au chargement du module."""

from domains.registry import register_vertical
from domains.droit.cabinets import CABINETS
from domains.droit.banques import BANQUES
from domains.droit.fonds import FONDS

register_vertical(CABINETS)
register_vertical(BANQUES)
register_vertical(FONDS)
