from typing import Any

from sqlalchemy import Boolean, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base
from app.shared.models import TimestampMixin


class TaskConfig(TimestampMixin, Base):
    __tablename__ = "config_task_configs"
    __table_args__ = (
        UniqueConstraint("project_id", "env", "task_type", name="uq_config_task"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    env: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    prompt_key: Mapped[str] = mapped_column(String(200), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    model_policy_id: Mapped[str] = mapped_column(String(100), nullable=False)
    rag_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rag_policy_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def as_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "env": self.env,
            "task_type": self.task_type,
            "prompt_key": self.prompt_key,
            "prompt_version": self.prompt_version,
            "model_policy_id": self.model_policy_id,
            "rag_enabled": self.rag_enabled,
            "rag_policy_id": self.rag_policy_id,
            "enabled": self.enabled,
        }


class ConfigChangeLog(Base):
    __tablename__ = "config_change_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    env: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    config_type: Mapped[str] = mapped_column(String(50), nullable=False)
    config_key: Mapped[str] = mapped_column(String(100), nullable=False)
    before_value: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after_value: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    changed_by: Mapped[str] = mapped_column(String(100), default="system", nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
