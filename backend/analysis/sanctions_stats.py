"""
Sanctions List Statistics & Analysis
========================================
Provides deep analytics on the sanctions database — entity breakdowns,
program distributions, geographic coverage, and screening performance
metrics. Used for compliance reporting and understanding the scope of
the sanctions lists being screened against.

Usage:
    from database import SessionLocal
    from analysis.sanctions_stats import SanctionsAnalyzer

    db = SessionLocal()
    analyzer = SanctionsAnalyzer(db)

    print(analyzer.list_overview())
    print(analyzer.top_programs(limit=20))
    print(analyzer.entity_type_breakdown())
"""

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional


class SanctionsAnalyzer:
    """
    Analytics engine for the sanctions database.
    Provides aggregate statistics for compliance dashboards and reports.
    """

    def __init__(self, db):
        self.db = db

    # ── Overview ──────────────────────────────────────────────────────

    def list_overview(self) -> Dict[str, Any]:
        """
        High-level overview of all sanctions lists in the database.
        Shows entry counts per list and total coverage.
        """
        from models.sanctions import SanctionsEntry, SanctionsAlias
        from sqlalchemy import func

        total_entries = self.db.query(func.count(SanctionsEntry.id)).scalar() or 0
        total_aliases = self.db.query(func.count(SanctionsAlias.id)).scalar() or 0

        by_list = (
            self.db.query(
                SanctionsEntry.list_name,
                func.count(SanctionsEntry.id).label("count"),
            )
            .group_by(SanctionsEntry.list_name)
            .all()
        )

        avg_aliases_per_entry = round(total_aliases / total_entries, 2) if total_entries else 0

        return {
            "total_entries":          total_entries,
            "total_aliases":          total_aliases,
            "avg_aliases_per_entry":  avg_aliases_per_entry,
            "by_list": {
                row.list_name: row.count
                for row in by_list
                if row.list_name
            },
        }

    # ── Entity Type ───────────────────────────────────────────────────

    def entity_type_breakdown(self) -> List[Dict[str, Any]]:
        """
        Count of entries by entity type (Individual, Entity, Vessel, Aircraft).
        Across all lists combined and per-list breakdown.
        """
        from models.sanctions import SanctionsEntry
        from sqlalchemy import func

        rows = (
            self.db.query(
                SanctionsEntry.entity_type,
                SanctionsEntry.list_name,
                func.count(SanctionsEntry.id).label("count"),
            )
            .group_by(SanctionsEntry.entity_type, SanctionsEntry.list_name)
            .order_by(func.count(SanctionsEntry.id).desc())
            .all()
        )

        # Aggregate by entity type
        totals: Dict[str, int] = {}
        by_list: Dict[str, Dict[str, int]] = {}

        for row in rows:
            etype = row.entity_type or "Unknown"
            lname = row.list_name or "Unknown"

            totals[etype] = totals.get(etype, 0) + row.count
            if etype not in by_list:
                by_list[etype] = {}
            by_list[etype][lname] = row.count

        total_all = sum(totals.values())

        return [
            {
                "entity_type": etype,
                "count":       count,
                "pct":         round(count / total_all * 100, 2) if total_all else 0,
                "by_list":     by_list.get(etype, {}),
            }
            for etype, count in sorted(totals.items(), key=lambda x: x[1], reverse=True)
        ]

    # ── Programs ──────────────────────────────────────────────────────

    def top_programs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Top N sanctions programs by entry count.
        Shows which programs (IRAN, DPRK, SDGT, etc.) have the most designations.
        """
        import json
        from models.sanctions import SanctionsEntry

        program_counts: Dict[str, int] = {}
        entries = self.db.query(
            SanctionsEntry.programs
        ).filter(SanctionsEntry.programs.isnot(None)).all()

        for (programs_json,) in entries:
            try:
                programs = json.loads(programs_json)
                if isinstance(programs, list):
                    for p in programs:
                        if p:
                            program_counts[p] = program_counts.get(p, 0) + 1
                elif isinstance(programs, str) and programs:
                    program_counts[programs] = program_counts.get(programs, 0) + 1
            except (json.JSONDecodeError, TypeError):
                if programs_json:
                    program_counts[programs_json] = program_counts.get(programs_json, 0) + 1

        sorted_programs = sorted(program_counts.items(), key=lambda x: x[1], reverse=True)
        total = sum(program_counts.values())

        return [
            {
                "program": name,
                "count":   count,
                "pct":     round(count / total * 100, 2) if total else 0,
            }
            for name, count in sorted_programs[:limit]
        ]

    # ── Geographic Coverage ────────────────────────────────────────────

    def geographic_coverage(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Top N countries by number of sanctioned entities located there.
        Shows where sanctioned entities are most concentrated geographically.
        """
        from models.sanctions import SanctionsLocation, SanctionsEntry
        from sqlalchemy import func

        rows = (
            self.db.query(
                SanctionsLocation.country,
                func.count(SanctionsLocation.id).label("count"),
            )
            .filter(SanctionsLocation.country.isnot(None))
            .group_by(SanctionsLocation.country)
            .order_by(func.count(SanctionsLocation.id).desc())
            .limit(limit)
            .all()
        )

        total = sum(row.count for row in rows)

        return [
            {
                "country": row.country,
                "count":   row.count,
                "pct":     round(row.count / total * 100, 2) if total else 0,
            }
            for row in rows
        ]

    # ── Alias Quality ─────────────────────────────────────────────────

    def alias_quality_stats(self) -> Dict[str, Any]:
        """
        Statistics on alias quality — how many aliases are low-quality,
        how many entries have only one alias vs multiple, etc.
        Affects screening accuracy and false-positive rates.
        """
        from models.sanctions import SanctionsAlias, SanctionsEntry
        from sqlalchemy import func

        total_aliases = self.db.query(func.count(SanctionsAlias.id)).scalar() or 0
        low_quality   = self.db.query(func.count(SanctionsAlias.id)).filter(
            SanctionsAlias.low_quality == True
        ).scalar() or 0
        primary_count = self.db.query(func.count(SanctionsAlias.id)).filter(
            SanctionsAlias.is_primary == True
        ).scalar() or 0

        alias_type_counts = (
            self.db.query(
                SanctionsAlias.alias_type,
                func.count(SanctionsAlias.id).label("count"),
            )
            .group_by(SanctionsAlias.alias_type)
            .order_by(func.count(SanctionsAlias.id).desc())
            .all()
        )

        return {
            "total_aliases":       total_aliases,
            "primary_aliases":     primary_count,
            "low_quality_aliases": low_quality,
            "low_quality_pct":     round(low_quality / total_aliases * 100, 2) if total_aliases else 0,
            "by_alias_type": {
                (row.alias_type or "Unknown"): row.count
                for row in alias_type_counts
            },
        }

    # ── Screening Performance ─────────────────────────────────────────

    def screening_difficulty_estimate(self) -> Dict[str, Any]:
        """
        Estimates screening complexity based on:
        - Average aliases per entry (more aliases = more comparisons per search)
        - Low-quality alias ratio (affects false positive rate)
        - Entries with no location (reduces geographic filtering effectiveness)

        Returns complexity indicators useful for performance tuning.
        """
        from models.sanctions import SanctionsEntry, SanctionsAlias, SanctionsLocation
        from sqlalchemy import func

        total_entries  = self.db.query(func.count(SanctionsEntry.id)).scalar() or 1
        total_aliases  = self.db.query(func.count(SanctionsAlias.id)).scalar() or 0
        entries_w_loc  = self.db.query(func.count(SanctionsLocation.entry_id.distinct())).scalar() or 0
        low_q_aliases  = self.db.query(func.count(SanctionsAlias.id)).filter(
            SanctionsAlias.low_quality == True
        ).scalar() or 0

        avg_aliases = total_aliases / total_entries
        loc_coverage = entries_w_loc / total_entries * 100
        low_q_pct    = low_q_aliases / total_aliases * 100 if total_aliases else 0

        # Complexity score: higher = harder to screen (more false positives / slower)
        complexity = round(avg_aliases * 2 + low_q_pct * 0.5, 1)

        return {
            "total_entries":       total_entries,
            "total_aliases":       total_aliases,
            "avg_aliases_per_entry": round(avg_aliases, 2),
            "location_coverage_pct": round(loc_coverage, 2),
            "low_quality_alias_pct": round(low_q_pct, 2),
            "complexity_score":    complexity,
            "complexity_label": (
                "Low" if complexity < 10
                else "Medium" if complexity < 20
                else "High"
            ),
        }

    # ── Full Report ────────────────────────────────────────────────────

    def full_report(self) -> Dict[str, Any]:
        """Generate complete sanctions analytics report."""
        return {
            "generated_at":          datetime.now(timezone.utc).isoformat(),
            "overview":              self.list_overview(),
            "entity_types":          self.entity_type_breakdown(),
            "top_programs":          self.top_programs(),
            "geographic_coverage":   self.geographic_coverage(),
            "alias_quality":         self.alias_quality_stats(),
            "screening_difficulty":  self.screening_difficulty_estimate(),
        }
