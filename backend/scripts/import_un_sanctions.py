"""
UN Security Council Consolidated Sanctions List Import
=======================================================
Parses the UN CONSOLIDATED_LIST XML and appends entries to the same
sanctions tables used by the OFAC SDN import.

UN XML root element: <CONSOLIDATED_LIST>
  <INDIVIDUALS>
    <INDIVIDUAL>
      <DATAID>              — unique ID
      <FIRST_NAME>          — first (or full entity) name
      <SECOND_NAME>, <THIRD_NAME>, <FOURTH_NAME> — additional name parts
      <UN_LIST_TYPE>        — Taliban / Al-Qaida / Sudan / Iran …
      <REFERENCE_NUMBER>    — e.g. QDi.335, SDi.007
      <INDIVIDUAL_ALIAS>    — <QUALITY> (Good/Low) + <ALIAS_NAME>
      <INDIVIDUAL_ADDRESS>  — <COUNTRY>, <CITY>, <STATE_PROVINCE>, <NOTE>
      <INDIVIDUAL_DOCUMENT> — <TYPE_OF_DOCUMENT>, <NUMBER>, <ISSUING_COUNTRY>
      <NATIONALITY>         — <VALUE> …
  <ENTITIES>
    <ENTITY> — same structure; name is in <FIRST_NAME>
               entity aliases in <ENTITY_ALIAS>
               addresses   in <ENTITY_ADDRESS>

Run from backend/:  python scripts/import_un_sanctions.py
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lxml import etree
from database import SessionLocal, create_tables
from models.sanctions import (
    SanctionsEntry, SanctionsAlias, SanctionsLocation, SanctionsIdentifier,
)
from config import settings

LIST_NAME = "UN"


def _text(elem, tag: str) -> str:
    child = elem.find(tag)
    return (child.text or "").strip() if child is not None else ""


def import_un_list(xml_path: str, db) -> int:
    print(f"[UN-IMPORT] Parsing {xml_path} ...")

    # Clear existing UN entries
    existing_ids = [
        row.id
        for row in db.query(SanctionsEntry.id).filter(
            SanctionsEntry.list_name == LIST_NAME
        ).all()
    ]
    if existing_ids:
        db.query(SanctionsIdentifier).filter(
            SanctionsIdentifier.entry_id.in_(existing_ids)
        ).delete(synchronize_session=False)
        db.query(SanctionsLocation).filter(
            SanctionsLocation.entry_id.in_(existing_ids)
        ).delete(synchronize_session=False)
        db.query(SanctionsAlias).filter(
            SanctionsAlias.entry_id.in_(existing_ids)
        ).delete(synchronize_session=False)
        db.query(SanctionsEntry).filter(
            SanctionsEntry.id.in_(existing_ids)
        ).delete(synchronize_session=False)
        db.commit()
        print(f"[UN-IMPORT] Cleared {len(existing_ids)} old UN entries.")

    tree = etree.parse(xml_path)
    root = tree.getroot()
    total = 0

    # ------------------------------------------------------------------ #
    # Individuals                                                          #
    # ------------------------------------------------------------------ #
    individuals_section = root.find("INDIVIDUALS")
    if individuals_section is not None:
        for ind in individuals_section.findall("INDIVIDUAL"):
            dataid  = _text(ind, "DATAID")
            parts   = [
                _text(ind, "FIRST_NAME"),
                _text(ind, "SECOND_NAME"),
                _text(ind, "THIRD_NAME"),
                _text(ind, "FOURTH_NAME"),
            ]
            full_name = " ".join(p for p in parts if p)
            if not full_name:
                continue

            list_type  = _text(ind, "UN_LIST_TYPE")
            ref_num    = _text(ind, "REFERENCE_NUMBER")
            fixed_ref  = f"UN-{dataid}"

            entry = SanctionsEntry(
                fixed_ref    = fixed_ref,
                primary_name = full_name,
                entity_type  = "Individual",
                party_subtype= "Individual",
                programs     = json.dumps([list_type]) if list_type else "[]",
                list_name    = LIST_NAME,
                remarks      = ref_num or None,
            )
            db.add(entry)
            db.flush()

            # Primary alias
            db.add(SanctionsAlias(
                entry_id   = entry.id,
                alias_name = full_name,
                alias_type = "Name",
                is_primary = True,
                low_quality= False,
            ))

            # Additional aliases
            for alias_elem in ind.findall("INDIVIDUAL_ALIAS"):
                alias_name = _text(alias_elem, "ALIAS_NAME")
                quality    = _text(alias_elem, "QUALITY").lower()
                if alias_name and alias_name != full_name:
                    db.add(SanctionsAlias(
                        entry_id   = entry.id,
                        alias_name = alias_name,
                        alias_type = "A.K.A.",
                        is_primary = False,
                        low_quality= (quality == "low"),
                    ))

            # Addresses (all of them, store first as location)
            first_addr = True
            for addr_elem in ind.findall("INDIVIDUAL_ADDRESS"):
                city    = _text(addr_elem, "CITY")
                country = _text(addr_elem, "COUNTRY")
                state   = _text(addr_elem, "STATE_PROVINCE")
                note    = _text(addr_elem, "NOTE")
                if (city or country or state) and first_addr:
                    db.add(SanctionsLocation(
                        entry_id      = entry.id,
                        country       = country or None,
                        city          = city or None,
                        state_province= state or None,
                        address       = note or None,
                    ))
                    first_addr = False

            # Documents / Identifiers
            for doc_elem in ind.findall("INDIVIDUAL_DOCUMENT"):
                doc_type = _text(doc_elem, "TYPE_OF_DOCUMENT")
                doc_num  = _text(doc_elem, "NUMBER")
                doc_ctry = _text(doc_elem, "ISSUING_COUNTRY")
                if doc_num:
                    db.add(SanctionsIdentifier(
                        entry_id = entry.id,
                        id_type  = doc_type or None,
                        id_value = doc_num,
                        country  = doc_ctry or None,
                    ))

            total += 1
            if total % 500 == 0:
                db.commit()
                print(f"  [UN-IMPORT] {total} individuals processed …")

    # ------------------------------------------------------------------ #
    # Entities                                                             #
    # ------------------------------------------------------------------ #
    entities_section = root.find("ENTITIES")
    if entities_section is not None:
        for ent in entities_section.findall("ENTITY"):
            dataid    = _text(ent, "DATAID")
            name      = _text(ent, "FIRST_NAME")
            list_type = _text(ent, "UN_LIST_TYPE")
            ref_num   = _text(ent, "REFERENCE_NUMBER")
            if not name:
                continue

            fixed_ref = f"UN-{dataid}"

            entry = SanctionsEntry(
                fixed_ref    = fixed_ref,
                primary_name = name,
                entity_type  = "Entity",
                party_subtype= "Entity",
                programs     = json.dumps([list_type]) if list_type else "[]",
                list_name    = LIST_NAME,
                remarks      = ref_num or None,
            )
            db.add(entry)
            db.flush()

            db.add(SanctionsAlias(
                entry_id   = entry.id,
                alias_name = name,
                alias_type = "Name",
                is_primary = True,
                low_quality= False,
            ))

            # Entity aliases
            for alias_elem in ent.findall("ENTITY_ALIAS"):
                alias_name = _text(alias_elem, "ALIAS_NAME")
                quality    = _text(alias_elem, "QUALITY").lower()
                if alias_name and alias_name != name:
                    db.add(SanctionsAlias(
                        entry_id   = entry.id,
                        alias_name = alias_name,
                        alias_type = "A.K.A.",
                        is_primary = False,
                        low_quality= (quality == "low"),
                    ))

            # Addresses
            first_addr = True
            for addr_elem in ent.findall("ENTITY_ADDRESS"):
                city    = _text(addr_elem, "CITY")
                country = _text(addr_elem, "COUNTRY")
                state   = _text(addr_elem, "STATE_PROVINCE")
                note    = _text(addr_elem, "NOTE")
                if (city or country or state) and first_addr:
                    db.add(SanctionsLocation(
                        entry_id      = entry.id,
                        country       = country or None,
                        city          = city or None,
                        state_province= state or None,
                        address       = note or None,
                    ))
                    first_addr = False

            total += 1

    db.commit()
    print(f"[UN-IMPORT] Done! Imported {total} UN sanctions entries.")
    return total


if __name__ == "__main__":
    xml_path = settings.UN_XML_PATH
    if not Path(xml_path).exists():
        print(f"[ERROR] UN XML not found at: {xml_path}")
        print("Expected: ~/Downloads/consolidatedLegacyByNAME-2.xml")
        sys.exit(1)

    create_tables()
    db = SessionLocal()
    try:
        import_un_list(xml_path, db)
    finally:
        db.close()
