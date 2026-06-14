from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base
from app.shared.models import TimestampMixin


class LLMModelProvider(TimestampMixin, Base):
    __tablename__ = "llm_model_providers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    api_key_env: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class LLMModelEndpoint(TimestampMixin, Base):
    __tablename__ = "llm_model_endpoints"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("llm_model_providers.id"), nullable=False)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    endpoint_id: Mapped[str] = mapped_column(String(200), nullable=False)
    supports_stream: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    supports_json: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_context_tokens: Mapped[int] = mapped_column(Integer, default=8192, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class LLMModelPolicy(TimestampMixin, Base):
    __tablename__ = "llm_model_policies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    policy_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    env: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    primary_model_id: Mapped[int] = mapped_column(ForeignKey("llm_model_endpoints.id"), nullable=False)
    fallback_model_id: Mapped[int | None] = mapped_column(ForeignKey("llm_model_endpoints.id"), nullable=True)
    timeout_ms: Mapped[int] = mapped_column(Integer, default=30000, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    default_temperature: Mapped[float] = mapped_column(Float, default=0.3, nullable=False)
    default_max_tokens: Mapped[int] = mapped_column(Integer, default=1024, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class LLMInvocationLog(Base):
    __tablename__ = "llm_invocation_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    trace_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(100), nullable=False)
    env: Mapped[str] = mapped_column(String(50), nullable=False)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    model_policy_id: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
