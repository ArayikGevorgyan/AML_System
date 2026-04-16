"""
OFAC SDN Advanced XML Import Script
=====================================
Parses sdn_advanced.xml and populates the SQLite sanctions tables.

XML Structure understood:
  <Sanctions>
    <ReferenceValueSets>
      <AliasTypeValues>     — maps AliasType IDs to names (A.K.A., F.K.A., etc.)
      <SanctionsProgramValues> — maps program IDs to codes (SDGT, IRAN, etc.)
      <PartySubTypeValues>  — maps subtype IDs to labels (Individual, Entity, etc.)
    </ReferenceValueSets>
    <DistinctParties>
      <DistinctParty FixedRef="...">
        <Profile PartySubTypeID="...">
          <Identity>
            <Alias AliasTypeID="..." Primary="true/false" LowQuality="true/false">
              <DocumentedName>
                <DocumentedNamePart>
                  <NamePartValue>...</NamePartValue>
    <SanctionsEntries>
      <SanctionsEntry>
        <ProfileReference FixedRef="...">
        <SanctionsMeasure>
          <Program>...</Program>   — references SanctionsProgramID

Run from backend/: python scripts/import_sanctions.py
"""

import sys
import os
import json
from pathlib import Path

# Allow imports from backend root
sys.path.insert(0, str(Path(__file__).parent.parent))

from lxml import etree
from sqlalchemy.orm import Session

from database import SessionLocal, create_tables
from models.sanctions import SanctionsEntry, SanctionsAlias, SanctionsLocation, SanctionsIdentifier
from config import settings

NS = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/ADVANCED_XML"
NS_PREFIX = f"{{{NS}}}"


def tag(name: str) -> str:
    return f"{NS_PREFIX}{name}"


def parse_and_import(xml_path: str, db: Session, batch_size: int = 500):
    print(f"[IMPORT] Parsing {xml_path} ...")

    # ------------------------------------------------------------------ #
    # Phase 1: Build reference lookup tables from <ReferenceValueSets>    #
    # ------------------------------------------------------------------ #
    alias_type_map: dict[str, str] = {}       # ID → "A.K.A." etc.
    program_map: dict[str, str] = {}          # ID → "SDGT" etc.
    party_subtype_map: dict[str, str] = {}    # ID → "Individual" etc.
    country_map: dict[str, str] = {}          # ID → "Iran" etc.
    id_doc_type_map: dict[str, str] = {}      # ID → "Passport" etc.
    location_map: dict[str, dict] = {}        # locationID → {country, city, ...}

    context = etree.iterparse(xml_path, events=("end",), recover=True)

    # First pass: reference value sets only
    for event, elem in context:
        local = elem.tag.replace(NS_PREFIX, "")

        if local == "AliasType":
            alias_type_map[elem.get("ID", "")] = elem.text or ""

        elif local == "SanctionsProgram":
            program_map[elem.get("ID", "")] = elem.text or ""

        elif local == "PartySubType":
            party_subtype_map[elem.get("ID", "")] = elem.text or ""

        elif local == "Country":
            country_map[elem.get("ID", "")] = elem.text or ""

        elif local == "IDRegDocType":
            id_doc_type_map[elem.get("ID", "")] = elem.text or ""

        elif local == "ReferenceValueSets":
            elem.clear()
            break   # Stop after reference section

    del context

    # ------------------------------------------------------------------ #
    # Phase 2: Build Location map from <Locations>                        #
    # ------------------------------------------------------------------ #
    print("[IMPORT] Building location index ...")
    context2 = etree.iterparse(xml_path, events=("end",), recover=True)

    for event, elem in context2:
        local = elem.tag.replace(NS_PREFIX, "")

        if local == "Location":
            loc_id = elem.get("ID", "")
            country_id = None
            city = None
            address_parts = []
            state = None
            postal = None

            # Country
            lc_elem = elem.find(tag("LocationCountry"))
            if lc_elem is not None:
                country_id = lc_elem.get("CountryID", "")

            # Location parts
            for lp in elem.findall(tag("LocationPart")):
                lp_type = lp.get("LocPartTypeID", "")
                for lpv in lp.findall(tag("LocationPartValue")):
                    val_elem = lpv.find(tag("Value"))
                    val = val_elem.text if val_elem is not None else None
                    if not val:
                        continue
                    # 1451=Street, 1452=Address2, 1453=Address3,
                    # 1454=City, 1455=State, 1456=PostalCode
                    if lp_type in ("1451", "1452", "1453"):
                        address_parts.append(val)
                    elif lp_type == "1454":
                        city = val
                    elif lp_type == "1455":
                        state = val
                    elif lp_type == "1456":
                        postal = val

            location_map[loc_id] = {
                "country_id": country_id,
                "country": country_map.get(country_id or "", ""),
                "city": city,
                "state": state,
                "address": ", ".join(address_parts) if address_parts else None,
                "postal_code": postal,
            }
            elem.clear()

        elif local == "Locations":
            elem.clear()
            break

    del context2

    # ------------------------------------------------------------------ #
    # Phase 3: Parse DistinctParties                                      #
    # ------------------------------------------------------------------ #
    print("[IMPORT] Importing DistinctParties ...")

    # Clear existing data
    db.query(SanctionsIdentifier).delete()
    db.query(SanctionsLocation).delete()
    db.query(SanctionsAlias).delete()
    db.query(SanctionsEntry).delete()
    db.commit()
    print("[IMPORT] Cleared old sanctions data.")

    context3 = etree.iterparse(xml_path, events=("start", "end"), recover=True)
    batch_entries = []
    total_parties = 0
    in_distinct_parties = False

    for event, elem in context3:
        local = elem.tag.replace(NS_PREFIX, "")

        if event == "start" and local == "DistinctParties":
            in_distinct_parties = True
            continue

        if event != "end":
            continue

        if local == "DistinctParty" and in_distinct_parties:
            fixed_ref = elem.get("FixedRef", "")
            profile = elem.find(tag("Profile"))
            if profile is None:
                elem.clear()
                continue

            party_subtype_id = profile.get("PartySubTypeID", "")
            entity_type = party_subtype_map.get(party_subtype_id, "Unknown")

            identity = profile.find(tag("Identity"))
            if identity is None:
                elem.clear()
                continue

            aliases_data = []
            primary_name = None
            location_ids = []

            for alias in identity.findall(tag("Alias")):
                alias_type_id = alias.get("AliasTypeID", "")
                is_primary = alias.get("Primary", "false").lower() == "true"
                low_quality = alias.get("LowQuality", "false").lower() == "true"
                alias_type_label = alias_type_map.get(alias_type_id, "")

                for doc_name in alias.findall(tag("DocumentedName")):
                    name_parts = []
                    for dnp in doc_name.findall(tag("DocumentedNamePart")):
                        npv = dnp.find(tag("NamePartValue"))
                        if npv is not None and npv.text:
                            name_parts.append(npv.text.strip())
                    full_name = " ".join(name_parts)
                    if full_name:
                        aliases_data.append({
                            "name": full_name,
                            "type": alias_type_label,
                            "is_primary": is_primary,
                            "low_quality": low_quality,
                        })
                        if is_primary and not primary_name:
                            primary_name = full_name

            if not primary_name and aliases_data:
                primary_name = aliases_data[0]["name"]
            if not primary_name:
                elem.clear()
                continue

            # Location references from Feature elements
            for feature in profile.findall(tag("Feature")):
                for fv in feature.findall(tag("FeatureVersion")):
                    for vl in fv.findall(tag("VersionLocation")):
                        loc_id = vl.get("LocationID", "")
                        if loc_id:
                            location_ids.append(loc_id)

            batch_entries.append({
                "fixed_ref": fixed_ref,
                "primary_name": primary_name,
                "entity_type": entity_type,
                "party_subtype_id": party_subtype_id,
                "aliases": aliases_data,
                "location_ids": location_ids,
            })
            total_parties += 1

            if len(batch_entries) >= batch_size:
                _flush_batch(batch_entries, location_map, db)
                batch_entries = []
                print(f"  [IMPORT] Processed {total_parties} parties ...")

            elem.clear()

        elif local == "DistinctParties":
            # End of section
            break

    if batch_entries:
        _flush_batch(batch_entries, location_map, db)

    # ------------------------------------------------------------------ #
    # Phase 4: Parse SanctionsEntries to populate programs per entry      #
    # ------------------------------------------------------------------ #
    print("[IMPORT] Parsing SanctionsEntries for program data ...")
    # Build fixed_ref → db_id lookup
    fixed_ref_to_id: dict[str, int] = {}
    for row in db.query(SanctionsEntry.id, SanctionsEntry.fixed_ref).all():
        fixed_ref_to_id[row.fixed_ref] = row.id

    context4 = etree.iterparse(xml_path, events=("start", "end"), recover=True)
    in_se = False
    prog_updates: dict[str, list] = {}  # fixed_ref → [program, ...]

    for event, elem in context4:
        local = elem.tag.replace(NS_PREFIX, "")

        if event == "start" and local == "SanctionsEntries":
            in_se = True
            continue

        if not in_se:
            continue

        if event == "end" and local == "SanctionsEntry":
            profile_id = elem.get("ProfileID", "")
            programs_found = []
            for measure in elem.findall(tag("SanctionsMeasure")):
                comment_el = measure.find(tag("Comment"))
                if comment_el is not None and comment_el.text and comment_el.text.strip():
                    prog = comment_el.text.strip()
                    # Only include if it looks like a program code (no spaces, uppercase or dashes)
                    if prog and len(prog) <= 40:
                        programs_found.append(prog)
            if programs_found and profile_id:
                prog_updates.setdefault(profile_id, []).extend(programs_found)
            elem.clear()

        elif event == "end" and local == "SanctionsEntries":
            break

    del context4

    # Apply program updates in bulk
    updated = 0
    for fixed_ref, progs in prog_updates.items():
        db_id = fixed_ref_to_id.get(fixed_ref)
        if db_id:
            unique_progs = list(dict.fromkeys(progs))  # deduplicate, preserve order
            db.query(SanctionsEntry).filter(SanctionsEntry.id == db_id).update(
                {"programs": json.dumps(unique_progs)}
            )
            updated += 1
    db.commit()
    print(f"[IMPORT] Updated programs for {updated} entries.")

    print(f"[IMPORT] Done! Imported {total_parties} sanctions entries.")
    return total_parties


def _flush_batch(batch: list, location_map: dict, db: Session):
    for item in batch:
        entry = SanctionsEntry(
            fixed_ref=item["fixed_ref"],
            primary_name=item["primary_name"],
            entity_type=item["entity_type"],
            party_subtype=item["party_subtype_id"],
            programs=json.dumps([]),
            list_name="SDN",
        )
        db.add(entry)
        db.flush()

        for a in item["aliases"]:
            db.add(SanctionsAlias(
                entry_id=entry.id,
                alias_name=a["name"],
                alias_type=a["type"],
                is_primary=a["is_primary"],
                low_quality=a["low_quality"],
            ))

        for loc_id in item["location_ids"][:1]:   # store first location per entry
            loc = location_map.get(loc_id)
            if loc:
                db.add(SanctionsLocation(
                    entry_id=entry.id,
                    country=loc.get("country"),
                    city=loc.get("city"),
                    state_province=loc.get("state"),
                    address=loc.get("address"),
                    postal_code=loc.get("postal_code"),
                ))

    db.commit()


if __name__ == "__main__":
    xml_path = settings.SDN_XML_PATH
    if not Path(xml_path).exists():
        print(f"[ERROR] SDN XML not found at: {xml_path}")
        print("Please copy sdn_advanced-3.xml to ~/Downloads/ or update SDN_XML_PATH in config.py")
        sys.exit(1)

    create_tables()
    db = SessionLocal()
    try:
        count = parse_and_import(xml_path, db)
        print(f"[IMPORT] Successfully imported {count} sanctions entries into SQLite.")
    finally:
        db.close()
