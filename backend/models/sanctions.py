from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from database import Base


class SanctionsEntry(Base):
    __tablename__ = "sanctions_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fixed_ref = Column(String, unique=True, nullable=False, index=True)
    primary_name = Column(String, nullable=False, index=True)
    entity_type = Column(String, nullable=True)
    party_subtype = Column(String, nullable=True)
    programs = Column(String, nullable=True)
    list_name = Column(String, default="SDN")
    remarks = Column(String, nullable=True)
    imported_at = Column(DateTime, server_default=func.now())


class SanctionsAlias(Base):
    __tablename__ = "sanctions_aliases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_id = Column(Integer, ForeignKey("sanctions_entries.id"), nullable=False, index=True)
    alias_name = Column(String, nullable=False, index=True)
    alias_type = Column(String, nullable=True)
    is_primary = Column(Boolean, default=False)
    low_quality = Column(Boolean, default=False)


class SanctionsLocation(Base):
    __tablename__ = "sanctions_locations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_id = Column(Integer, ForeignKey("sanctions_entries.id"), nullable=False, index=True)
    country = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state_province = Column(String, nullable=True)
    address = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)


class SanctionsIdentifier(Base):
    __tablename__ = "sanctions_identifiers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_id = Column(Integer, ForeignKey("sanctions_entries.id"), nullable=False, index=True)
    id_type = Column(String, nullable=True)
    id_value = Column(String, nullable=True)
    country = Column(String, nullable=True)
