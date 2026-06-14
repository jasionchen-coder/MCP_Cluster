from typing import Any

from sqlalchemy import Boolean, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base
from app.shared.models import TimestampMixin


class RegisteredTool(TimestampMixin, Base):
    __tablename__ = "tool_registered_tools"
    __table_args__ = (
        UniqueConstraint("project_id", "env", "tool_id", name="uq_tool_project_env_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    env: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    tool_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    endpoint_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    output_schema: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    auth_type: Mapped[str] = mapped_column(String(50), default="none", nullable=False)
    secret_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    permission_scope: Mapped[str] = mapped_column(String(50), default="project", nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def as_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "env": self.env,
            "tool_id": self.tool_id,
            "display_name": self.display_name,
            "description": self.description,
            "tool_type": self.tool_type,
            "endpoint_config": self.endpoint_config,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "auth_type": self.auth_type,
            "secret_ref": self.secret_ref,
            "permission_scope": self.permission_scope,
            "tags": self.tags,
            "version": self.version,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
