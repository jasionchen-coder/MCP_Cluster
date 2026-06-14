from typing import Any

from sqlalchemy import JSON, Boolean, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base
from app.shared.models import TimestampMixin


class PromptTemplate(TimestampMixin, Base):
    __tablename__ = "prompt_templates"
    __table_args__ = (UniqueConstraint("prompt_key", name="uq_prompt_key"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    prompt_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_version: Mapped[str] = mapped_column(String(50), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PromptVersion(TimestampMixin, Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (
        UniqueConstraint("prompt_key", "version", name="uq_prompt_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    prompt_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    variables_schema: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)


class PromptRenderLog(Base):
    __tablename__ = "prompt_render_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    env: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    variables_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
