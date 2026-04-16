import re
import unicodedata
from typing import List, Optional, Tuple, Dict

import jellyfish
from sqlalchemy.orm import Session
from sqlalchemy import or_

from models.sanctions import (
    SanctionsEntry, SanctionsAlias, SanctionsLocation, SanctionsIdentifier,
)
from schemas.sanctions import (
    SanctionsSearchRequest,
    SanctionsSearchResponse,
    SanctionsSearchResult,
    SanctionsAliasOut,
    SanctionsLocationOut,
)

# Only strip honorific titles that are NEVER part of a person's name.
# Arabic name particles (al, bin, abu, ibn, etc.) are significant parts of
# sanctioned entities' names and MUST NOT be removed.
NOISE_WORDS = {
    "mr", "mrs", "ms", "dr", "prof", "sir",
}


class SanctionsScreener:

    def search(
        self, request: SanctionsSearchRequest, db: Session
    ) -> SanctionsSearchResponse:
        query_name = request.name.strip()
        normalized_query = self._normalize(query_name)
        query_tokens = set(normalized_query.split()) if normalized_query else set()

        # If an ID number is supplied, search identifiers directly
        if request.id_number:
            id_entries = self._search_by_id(request.id_number, db)
        else:
            id_entries = {}

        # Only run name-based candidate search when a name is provided
        if normalized_query:
            candidates = self._get_candidates(normalized_query, query_tokens, request, db)
        else:
            candidates = []

        # Score every alias independently — one result row per alias, like OFAC.
        seen_alias: set = set()
        scored: List[Tuple] = []

        for entry, alias, location in candidates:
            key = (entry.id, alias.id)
            if key in seen_alias:
                continue
            seen_alias.add(key)

            normalized_alias = self._normalize(alias.alias_name)
            score = self._compute_score(normalized_query, query_tokens, normalized_alias)

            # Low-quality aliases get a slight penalty on FUZZY matches only.
            # Exact token matches (score == 100) are not penalised — OFAC
            # returns low-quality exact matches at full score too.
            if alias.low_quality and score < 100.0:
                score *= 0.97

            if score < request.min_score:
                continue

            scored.append((score, entry, alias, location))

        # Add ID-number matches at score 100
        id_entry_ids_seen: set = set()
        for eid, (entry, location) in id_entries.items():
            if eid in id_entry_ids_seen:
                continue
            id_entry_ids_seen.add(eid)
            primary_alias = (
                db.query(SanctionsAlias).filter(
                    SanctionsAlias.entry_id == eid,
                    SanctionsAlias.is_primary == True,
                ).first()
                or db.query(SanctionsAlias).filter(
                    SanctionsAlias.entry_id == eid
                ).first()
            )
            if primary_alias:
                scored.append((100.0, entry, primary_alias, location))

        # Pre-fetch all aliases per entry to avoid N+1 queries
        entry_ids_needed = {e.id for _, e, _, _ in scored}
        all_aliases_cache: Dict[int, List] = {}
        for eid in entry_ids_needed:
            all_aliases_cache[eid] = (
                db.query(SanctionsAlias).filter(SanctionsAlias.entry_id == eid).all()
            )

        results: List[SanctionsSearchResult] = []
        for score, entry, alias, location in scored:
            address_str = self._format_address(location)
            all_aliases = all_aliases_cache.get(entry.id, [])

            results.append(
                SanctionsSearchResult(
                    fixed_ref=entry.fixed_ref,
                    primary_name=entry.primary_name,
                    matched_name=alias.alias_name,
                    alias_type=alias.alias_type,
                    entity_type=entry.entity_type,
                    programs=entry.programs,
                    list_name=entry.list_name,
                    score=round(score, 2),
                    score_label=self._score_label(score),
                    country=location.country if location else None,
                    address=address_str,
                    aliases=[
                        SanctionsAliasOut(
                            alias_name=a.alias_name,
                            alias_type=a.alias_type,
                            is_primary=a.is_primary,
                        )
                        for a in all_aliases
                    ],
                )
            )

        # Sort: score desc, then alphabetically by matched name (like OFAC)
        results.sort(key=lambda r: (-r.score, r.matched_name))
        results = results[: request.max_results]

        return SanctionsSearchResponse(
            query=query_name,
            total_results=len(results),
            min_score_used=request.min_score,
            results=results,
        )

    # ---------------------------------------------------------------------- #
    # Candidate retrieval                                                      #
    # ---------------------------------------------------------------------- #

    def _get_candidates(
        self,
        normalized_query: str,
        query_tokens: set,
        request: SanctionsSearchRequest,
        db: Session,
    ) -> List[Tuple[SanctionsEntry, SanctionsAlias, Optional[SanctionsLocation]]]:

        # Base join — include ALL aliases (low-quality included, like OFAC does)
        alias_base = db.query(SanctionsAlias, SanctionsEntry).join(
            SanctionsEntry, SanctionsAlias.entry_id == SanctionsEntry.id
        )

        if request.entity_type:
            alias_base = alias_base.filter(
                SanctionsEntry.entity_type == request.entity_type
            )
        if request.list_name:
            alias_base = alias_base.filter(
                SanctionsEntry.list_name == request.list_name
            )
        if request.program:
            alias_base = alias_base.filter(
                SanctionsEntry.programs.contains(request.program)
            )

        # SQL ILIKE substring matching on the original alias_name.
        # Using tokens with 3+ characters avoids over-broad single/double char matches.
        tokens_for_sql = [t for t in query_tokens if len(t) >= 3]

        if tokens_for_sql:
            sql_filters = [
                SanctionsAlias.alias_name.ilike(f"%{token}%")
                for token in tokens_for_sql
            ]
            alias_base = alias_base.filter(or_(*sql_filters))
        elif normalized_query and len(normalized_query) >= 2:
            alias_base = alias_base.filter(
                SanctionsAlias.alias_name.ilike(f"%{normalized_query}%")
            )

        raw_results = alias_base.all()

        candidates = []
        seen = set()

        for alias_row, entry_row in raw_results:
            key = (entry_row.id, alias_row.id)
            if key in seen:
                continue
            seen.add(key)

            location = db.query(SanctionsLocation).filter(
                SanctionsLocation.entry_id == entry_row.id
            ).first()

            # Country filter
            if request.country:
                country_upper = request.country.upper()
                if location and location.country:
                    if country_upper not in location.country.upper():
                        continue
                elif request.country:
                    continue  # filter requires country but entry has none

            # City filter
            if request.city and location:
                if not location.city or request.city.lower() not in location.city.lower():
                    continue

            # State filter
            if request.state and location:
                if not location.state_province or request.state.lower() not in location.state_province.lower():
                    continue

            # Address filter
            if request.address and location:
                if not location.address or request.address.lower() not in location.address.lower():
                    continue

            candidates.append((entry_row, alias_row, location))

        return candidates

    def _search_by_id(
        self, id_number: str, db: Session
    ) -> Dict[int, Tuple]:
        """Return a dict of entry_id → (entry, location) matching the ID number."""
        rows = db.query(SanctionsIdentifier, SanctionsEntry).join(
            SanctionsEntry, SanctionsIdentifier.entry_id == SanctionsEntry.id
        ).filter(
            SanctionsIdentifier.id_value.ilike(f"%{id_number}%")
        ).all()

        result = {}
        for ident_row, entry_row in rows:
            if entry_row.id not in result:
                location = db.query(SanctionsLocation).filter(
                    SanctionsLocation.entry_id == entry_row.id
                ).first()
                result[entry_row.id] = (entry_row, location)
        return result

    # ---------------------------------------------------------------------- #
    # Scoring                                                                  #
    # ---------------------------------------------------------------------- #

    def _compute_score(
        self, query: str, query_tokens: set, candidate: str
    ) -> float:
        """
        Score 0-100. Designed to match OFAC's scoring convention:
          • Score 100  — all query tokens appear verbatim in the candidate
                         (OFAC "Minimum Name Score = 100" behaviour)
          • Score < 100 — fuzzy / partial match using Jaro-Winkler at the
                          token level, giving high scores for spelling
                          variants (Laden↔Ladin, Osama↔Usama)
        """
        if not query or not candidate:
            return 0.0
        if query == candidate:
            return 100.0

        cand_tokens = set(candidate.split())
        if not cand_tokens:
            return 0.0

        # ── OFAC exact-match rule ─────────────────────────────────────── #
        # All normalised query tokens are a subset of candidate tokens
        # → score 100 (same as OFAC "min score = 100").
        if query_tokens and query_tokens.issubset(cand_tokens):
            return 100.0

        # ── Fuzzy scoring ─────────────────────────────────────────────── #
        # For each query token find its best-matching candidate token
        # (Jaro-Winkler).  Average over all query tokens gives "token
        # recall": 1.0 when every query word fuzzy-matches some candidate
        # word — good for "Laden" finding "Ladin", "Osama" finding "Usama".
        per_token_best: List[float] = []
        for qt in query_tokens:
            best = max(
                (jellyfish.jaro_winkler_similarity(qt, ct) for ct in cand_tokens),
                default=0.0,
            )
            per_token_best.append(best)

        token_recall = sum(per_token_best) / len(per_token_best)

        # Full-string JW helps for nearly-identical strings
        jw_full = jellyfish.jaro_winkler_similarity(query, candidate)

        # Exact Jaccard — mild penalty when candidate has many unmatched tokens
        exact_inter = query_tokens & cand_tokens
        exact_union = query_tokens | cand_tokens
        jaccard = len(exact_inter) / len(exact_union) if exact_union else 0.0

        # Composite — token recall dominates
        composite = (
            token_recall * 0.60 +
            jw_full      * 0.25 +
            jaccard      * 0.15
        )

        # Cap just below 100 so exact-token hits clearly stand out
        return round(min(composite * 100, 99.9), 2)

    # ---------------------------------------------------------------------- #
    # Helpers                                                                  #
    # ---------------------------------------------------------------------- #

    def _normalize(self, name: str) -> str:
        if not name:
            return ""
        name = unicodedata.normalize("NFKD", name)
        name = name.encode("ascii", "ignore").decode("ascii")
        name = name.lower()
        name = re.sub(r"[^\w\s]", " ", name)
        tokens = [t for t in name.split() if t and t not in NOISE_WORDS]
        return " ".join(tokens).strip()

    def _score_label(self, score: float) -> str:
        if score >= 85:
            return "STRONG"
        elif score >= 70:
            return "POSSIBLE"
        else:
            return "WEAK"

    def _format_address(self, location: Optional[SanctionsLocation]) -> Optional[str]:
        if not location:
            return None
        parts = [
            location.address,
            location.city,
            location.state_province,
            location.postal_code,
            location.country,
        ]
        return ", ".join(p for p in parts if p) or None


sanctions_screener = SanctionsScreener()
