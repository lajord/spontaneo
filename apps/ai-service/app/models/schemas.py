from pydantic import BaseModel
from typing import Optional, Literal, List


class EnrichedContact(BaseModel):
    type: Literal["generique", "specialise"]
    nom: Optional[str] = None
    prenom: Optional[str] = None
    role: Optional[str] = None
    mail: Optional[str] = None
    genre: Optional[str] = None   # "M" ou "F" — déduit du prénom par l'IA


class Company(BaseModel):
    nom: str
    adresse: Optional[str] = None
    site_web: Optional[str] = None
    telephone: Optional[str] = None
    source: Optional[str] = None
    type_activite: Optional[str] = None  # categoryName Google Maps ou secteur Apollo
    score: Optional[int] = None          # score de pertinence 0-100 (après ranking)


class EnrichedCompany(Company):
    resultats: list[EnrichedContact] = []


class SearchRequest(BaseModel):
    secteur: str
    localisation: str
    radius: int = 20
    prompt: Optional[str] = None  # Objectifs / remarques libres de l'utilisateur
    sectors: Optional[List[str]] = None  # Sous-secteurs ciblés (ex: agence web, cabinet d'avocats)
    categories: Optional[List[str]] = None  # Catégories principales (ex: Technologie & Numérique, Finance)


class SearchResponse(BaseModel):
    secteur: str
    localisation: str
    job_titles: list[str]
    maps_keywords: list[str] = []
    apollo_keywords: list[str] = []
    total: int
    entreprises: list[Company]


class CompanyRequest(BaseModel):
    nom: str
    site_web: Optional[str] = None
    adresse: Optional[str] = None
