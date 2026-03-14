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


class EnrichedCompany(Company):
    resultats: list[EnrichedContact] = []


class SearchRequest(BaseModel):
    secteur: str
    localisation: str
    radius: int = 20
    prompt: Optional[str] = None  # Objectifs / remarques libres de l'utilisateur
    sectors: Optional[List[str]] = None  # Secteurs professionnels ciblés (ex: Restauration, Hôtellerie)


class SearchResponse(BaseModel):
    secteur: str
    localisation: str
    job_titles: list[str]
    maps_keywords: list[str] = []
    total: int
    entreprises: list[Company]


class CompanyRequest(BaseModel):
    nom: str
    site_web: Optional[str] = None
    adresse: Optional[str] = None
