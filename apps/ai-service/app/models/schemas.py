from pydantic import BaseModel
from typing import Optional


class Contact(BaseModel):
    nom: Optional[str] = None
    prenom: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    genre: Optional[str] = None   # "M" ou "F" — déduit du prénom par l'IA


class Company(BaseModel):
    nom: str
    adresse: Optional[str] = None
    site_web: Optional[str] = None
    telephone: Optional[str] = None
    source: Optional[str] = None    # "google_places"


class EnrichedCompany(Company):
    emails: list[str] = []
    dirigeant: Optional[Contact] = None
    rh: Optional[Contact] = None
    autres_contacts: list[Contact] = []


class SearchRequest(BaseModel):
    secteur: str
    localisation: str
    radius: int = 20
    prompt: Optional[str] = None  # Objectifs / remarques libres de l'utilisateur


class SearchResponse(BaseModel):
    secteur: str
    localisation: str
    keywords: list[str]
    total: int
    entreprises: list[Company]


class CompanyRequest(BaseModel):
    nom: str
    site_web: Optional[str] = None
    adresse: Optional[str] = None
