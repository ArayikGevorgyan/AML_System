from pydantic import BaseModel
from typing import Optional, List


class SanctionsSearchRequest(BaseModel):
    name: str = ""
    entity_type: Optional[str] = None      # Individual, Entity, Vessel, Aircraft
    country: Optional[str] = None          # ISO-2 code or country name fragment
    city: Optional[str] = None
    state: Optional[str] = None
    address: Optional[str] = None
    id_number: Optional[str] = None        # Passport / ID / Digital Currency Address
    list_name: Optional[str] = None        # SDN or UN
    program: Optional[str] = None
    min_score: float = 65.0
    max_results: int = 20


class SanctionsAliasOut(BaseModel):
    alias_name: str
    alias_type: Optional[str]
    is_primary: bool

    class Config:
        from_attributes = True


class SanctionsLocationOut(BaseModel):
    country: Optional[str]
    city: Optional[str]
    address: Optional[str]

    class Config:
        from_attributes = True


class SanctionsSearchResult(BaseModel):
    fixed_ref: str
    primary_name: str
    matched_name: str
    alias_type: Optional[str]
    entity_type: Optional[str]
    programs: Optional[str]
    list_name: str
    score: float
    score_label: str        # STRONG, POSSIBLE, WEAK
    country: Optional[str]
    address: Optional[str]
    aliases: List[SanctionsAliasOut]


class SanctionsSearchResponse(BaseModel):
    query: str
    total_results: int
    min_score_used: float
    results: List[SanctionsSearchResult]


class SanctionsEntryOut(BaseModel):
    id: int
    fixed_ref: str
    primary_name: str
    entity_type: Optional[str]
    programs: Optional[str]
    list_name: str

    class Config:
        from_attributes = True
