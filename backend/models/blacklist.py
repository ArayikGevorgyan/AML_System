from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from database import Base


class BlacklistEntry(Base):
    __tablename__ = "blacklist_entries"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    entry_type   = Column(String, nullable=False, index=True)
    value        = Column(String, nullable=False, index=True)
    reason       = Column(String, nullable=False)
    severity     = Column(String, default="high")
    list_type    = Column(String, default="black", index=True)  # black, yellow, white
    is_active    = Column(Boolean, default=True, index=True)
    added_by     = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at   = Column(DateTime, server_default=func.now())
    updated_at   = Column(DateTime, onupdate=func.now())
    expires_at   = Column(DateTime, nullable=True)
    review_note  = Column(String, nullable=True)


class BlacklistMovementLog(Base):
    __tablename__ = "blacklist_movement_logs"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    entry_id     = Column(Integer, ForeignKey("blacklist_entries.id"), nullable=False, index=True)
    from_list    = Column(String, nullable=False)
    to_list      = Column(String, nullable=False)
    reason       = Column(String, nullable=False)
    moved_by     = Column(Integer, ForeignKey("users.id"), nullable=True)
    moved_by_name = Column(String, nullable=True)
    created_at   = Column(DateTime, server_default=func.now())
