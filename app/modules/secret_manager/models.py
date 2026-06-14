from typing import Any

from sqlalchemy import Boolean, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base
from app.shared.models import TimestampMixin


class ManagedSecret(TimestampMixin, Base):
    __tablename__ = "secret_managed_secrets"
    __table_args__ = (
        UniqueConstraint("project_id", "env", "secret_key", name="uq_secret_project_env_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    env: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    secret_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    value_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def metadata_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "env": self.env,
            "secret_key": self.secret_key,
            "secret_ref": f"secret://{self.project_id}/{self.env}/{self.secret_key}",
            "description": self.description,
            "version": self.version,
            "enabled": self.enabled,
            "value_fingerprint": self.value_fingerprint,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
