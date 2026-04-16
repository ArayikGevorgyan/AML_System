"""
Bulk Sanctions Screening CLI
==============================
Screens a CSV file of names/IDs against the sanctions database in bulk.
Useful for batch onboarding checks, periodic re-screening of all customers,
or one-off compliance reviews.

Usage:
    python scripts/bulk_screen.py --input customers.csv --output results.csv
    python scripts/bulk_screen.py --input names.csv --min-score 80 --max-results 5
    python scripts/bulk_screen.py --input data.csv --output hits.csv --entity-type Individual

Input CSV format (must have a 'name' column, 'id_number' column is optional):
    name,id_number,entity_type
    Osama bin Laden,,Individual
    IRISL,,Entity
    John Smith,P1234567,

Output CSV columns:
    input_name, matched_name, primary_name, score, score_label,
    list_name, entity_type, country, programs, fixed_ref
"""

import argparse
import csv
import sys
import os
from datetime import datetime

# Add the backend directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from services.sanctions_screener import sanctions_screener
from schemas.sanctions import SanctionsSearchRequest


def screen_row(row: dict, min_score: float, max_results: int, entity_type: str = None) -> list:
    """Screen a single CSV row and return list of result dicts."""
    name = row.get("name", "").strip()
    id_number = row.get("id_number", "").strip()
    row_entity_type = entity_type or row.get("entity_type", "").strip() or None

    if not name and not id_number:
        return []

    request = SanctionsSearchRequest(
        name=name or ".",
        id_number=id_number or None,
        min_score=min_score,
        max_results=max_results,
        entity_type=row_entity_type,
    )

    db = SessionLocal()
    try:
        response = sanctions_screener.search(request, db)
        results = []
        for r in response.results:
            results.append({
                "input_name":    name or id_number,
                "matched_name":  r.matched_name,
                "primary_name":  r.primary_name,
                "score":         r.score,
                "score_label":   r.score_label,
                "list_name":     r.list_name,
                "entity_type":   r.entity_type or "",
                "country":       r.country or "",
                "programs":      r.programs or "",
                "fixed_ref":     r.fixed_ref,
            })
        return results
    finally:
        db.close()


def run_bulk_screen(
    input_file: str,
    output_file: str,
    min_score: float,
    max_results: int,
    entity_type: str,
    hits_only: bool,
):
    start_time = datetime.now()
    print(f"[{start_time.strftime('%H:%M:%S')}] Starting bulk sanctions screening...")
    print(f"  Input:       {input_file}")
    print(f"  Output:      {output_file}")
    print(f"  Min score:   {min_score}")
    print(f"  Entity type: {entity_type or 'All'}")
    print()

    output_fields = [
        "input_name", "matched_name", "primary_name", "score",
        "score_label", "list_name", "entity_type", "country",
        "programs", "fixed_ref",
    ]

    total_rows = 0
    total_hits = 0
    rows_with_hits = 0

    with open(input_file, "r", encoding="utf-8") as infile, \
         open(output_file, "w", newline="", encoding="utf-8") as outfile:

        reader = csv.DictReader(infile)
        writer = csv.DictWriter(outfile, fieldnames=output_fields)
        writer.writeheader()

        for row in reader:
            total_rows += 1
            name = row.get("name", row.get("Name", "")).strip()

            results = screen_row(row, min_score, max_results, entity_type)

            if results:
                rows_with_hits += 1
                total_hits += len(results)
                for r in results:
                    writer.writerow(r)
                print(f"  ✗ HIT  [{total_rows:>5}] {name or '(id only)'} → {len(results)} match(es), top score: {results[0]['score']}")
            else:
                if not hits_only:
                    writer.writerow({
                        "input_name": name,
                        "matched_name": "", "primary_name": "",
                        "score": 0, "score_label": "NO MATCH",
                        "list_name": "", "entity_type": "",
                        "country": "", "programs": "", "fixed_ref": "",
                    })
                if total_rows % 50 == 0:
                    print(f"  ✓ OK   [{total_rows:>5}] {name} — no match")

    elapsed = (datetime.now() - start_time).total_seconds()
    print()
    print("=" * 55)
    print(f"  Completed in {elapsed:.1f}s")
    print(f"  Total rows screened:  {total_rows}")
    print(f"  Rows with hits:       {rows_with_hits}")
    print(f"  Total matches found:  {total_hits}")
    print(f"  Clean (no match):     {total_rows - rows_with_hits}")
    print(f"  Results saved to:     {output_file}")
    print("=" * 55)


def main():
    parser = argparse.ArgumentParser(
        description="Bulk sanctions screening — screen a CSV file against SDN/UN lists",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--input",  "-i", required=True, help="Input CSV file path")
    parser.add_argument("--output", "-o", default="screening_results.csv", help="Output CSV file path")
    parser.add_argument("--min-score", "-s", type=float, default=65.0, help="Minimum match score (default: 65)")
    parser.add_argument("--max-results", "-n", type=int, default=5, help="Max results per name (default: 5)")
    parser.add_argument("--entity-type", "-t", choices=["Individual", "Entity", "Vessel", "Aircraft"],
                        help="Filter by entity type")
    parser.add_argument("--hits-only", action="store_true",
                        help="Only write rows with matches to output (skip clean names)")

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found.")
        sys.exit(1)

    run_bulk_screen(
        input_file=args.input,
        output_file=args.output,
        min_score=args.min_score,
        max_results=args.max_results,
        entity_type=args.entity_type,
        hits_only=args.hits_only,
    )


if __name__ == "__main__":
    main()
