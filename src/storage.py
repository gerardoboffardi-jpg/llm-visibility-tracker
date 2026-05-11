"""SQLAlchemy models e session factory per LLM Visibility Tracker."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

load_dotenv(override=True)


def _resolve_database_url() -> str:
    """Priorità: env var DATABASE_URL > Streamlit secrets > SQLite locale.

    Normalizza eventuali `postgres://` (formato Heroku/Supabase URI) in
    `postgresql+psycopg://` richiesto da SQLAlchemy 2 + psycopg3.
    """
    url = os.getenv("DATABASE_URL")
    if not url:
        # Tenta Streamlit secrets se siamo in contesto Streamlit
        try:
            import streamlit as st  # type: ignore
            url = st.secrets.get("DATABASE_URL")  # type: ignore[attr-defined]
        except Exception:
            url = None
    if not url:
        default_path = Path(__file__).resolve().parent.parent / "llm_visibility.db"
        return f"sqlite:///{default_path}"

    # Normalizza prefissi
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


DATABASE_URL = _resolve_database_url()


class Base(DeclarativeBase):
    pass


class Prompt(Base):
    __tablename__ = "prompts"

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(64))
    geo: Mapped[str | None] = mapped_column(String(64))
    intent: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    responses: Mapped[list["Response"]] = relationship(back_populates="prompt")

    __table_args__ = (UniqueConstraint("text", name="uq_prompts_text"),)


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    trigger_type: Mapped[str] = mapped_column(String(32), default="manual")  # manual, scheduled, api
    config_hash: Mapped[str | None] = mapped_column(String(64))

    responses: Mapped[list["Response"]] = relationship(back_populates="run")


class Response(Base):
    __tablename__ = "responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), index=True)
    prompt_id: Mapped[int] = mapped_column(ForeignKey("prompts.id"), index=True)
    model_id: Mapped[str] = mapped_column(String(64), index=True)

    text: Mapped[str] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    tokens: Mapped[int | None] = mapped_column(Integer)
    raw_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    has_target_mention: Mapped[bool] = mapped_column(Boolean, default=False)
    has_target_citation: Mapped[bool] = mapped_column(Boolean, default=False)
    target_position_in_list: Mapped[int | None] = mapped_column(Integer)
    target_citation_position: Mapped[int | None] = mapped_column(Integer)
    total_citations: Mapped[int] = mapped_column(Integer, default=0)

    run: Mapped[Run] = relationship(back_populates="responses")
    prompt: Mapped[Prompt] = relationship(back_populates="responses")
    citations: Mapped[list["Citation"]] = relationship(back_populates="response", cascade="all, delete-orphan")
    mentions: Mapped[list["Mention"]] = relationship(back_populates="response", cascade="all, delete-orphan")


class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[int] = mapped_column(primary_key=True)
    response_id: Mapped[int] = mapped_column(ForeignKey("responses.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    url: Mapped[str] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(String(255), index=True)
    is_target_domain: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_competitor_domain: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    page_title: Mapped[str | None] = mapped_column(Text)
    snippet: Mapped[str | None] = mapped_column(Text)

    response: Mapped[Response] = relationship(back_populates="citations")


class Mention(Base):
    __tablename__ = "mentions"

    id: Mapped[int] = mapped_column(primary_key=True)
    response_id: Mapped[int] = mapped_column(ForeignKey("responses.id"), index=True)
    brand_name: Mapped[str] = mapped_column(String(128), index=True)
    is_target: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    position_in_text: Mapped[int | None] = mapped_column(Integer)
    context_snippet: Mapped[str | None] = mapped_column(Text)
    sentiment: Mapped[str | None] = mapped_column(String(16))  # positive, neutral, negative
    context_label: Mapped[str | None] = mapped_column(String(64))

    response: Mapped[Response] = relationship(back_populates="mentions")


class CompetitorDomain(Base):
    __tablename__ = "competitor_domains"

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_name: Mapped[str] = mapped_column(String(128), index=True)
    domain: Mapped[str] = mapped_column(String(255), unique=True, index=True)


engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_session():
    return SessionLocal()
