from __future__ import annotations
import os
from typing import Optional

from cryptography.fernet import Fernet
from sqlalchemy import create_engine, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./.data/app.db")
FERNET_KEY = os.getenv("FERNET_KEY")  # base64 urlsafe key (Fernet.generate_key())

_engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class UserCred(Base):
    __tablename__ = "user_cred"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    openai_api_key_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

def init_db() -> None:
    os.makedirs(".data", exist_ok=True)
    Base.metadata.create_all(_engine)

def _fernet() -> Fernet:
    if not FERNET_KEY:
        raise RuntimeError("FERNET_KEY not set. Generate one and export it.")
    key: bytes = FERNET_KEY.encode() if isinstance(FERNET_KEY, str) else FERNET_KEY
    return Fernet(key)

def set_openai_key(subject: str, api_key_plain: str) -> None:
    f = _fernet()
    enc = f.encrypt(api_key_plain.encode()).decode()
    with SessionLocal() as db:
        row = db.query(UserCred).filter_by(subject=subject).one_or_none()
        if not row:
            row = UserCred(subject=subject)
            db.add(row)
        row.openai_api_key_enc = enc
        db.commit()

def get_openai_key(subject: str) -> Optional[str]:
    with SessionLocal() as db:
        row = db.query(UserCred).filter_by(subject=subject).one_or_none()
        if not row or not row.openai_api_key_enc:
            return None
        f = _fernet()
        return f.decrypt(row.openai_api_key_enc.encode()).decode()
