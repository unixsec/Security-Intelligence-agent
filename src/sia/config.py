"""SIA configuration management.

Loads configuration from environment variables, YAML files, and K8s secrets.

Enterprise-grade rules (SEC-001/002/003):
  - In production (`env == "production"`) critical secrets MUST be provided:
    MySQL password, JWT secret (+ keys when RS256), MinIO credentials.
    Missing values raise at startup so the pod fails loudly rather than
    silently using a weak default.
  - Secrets are preferentially loaded from a mounted directory
    (`/etc/sia/secrets/<ENV_VAR_NAME>`) — SEC-008 — and fall back to
    environment variables.
"""

from __future__ import annotations

import os
import secrets as _secrets_mod
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SECRETS_DIR = os.environ.get("SIA_SECRETS_DIR", "/etc/sia/secrets")


def _load_secret_from_file(name: str) -> str | None:
    """Read a secret value from the mounted secrets dir, if present."""
    p = Path(SECRETS_DIR) / name
    if p.is_file():
        try:
            return p.read_text().strip()
        except OSError:
            return None
    return None


def _resolve_secret(env_name: str) -> str | None:
    """Prefer file-mounted secret, fall back to env var."""
    v = _load_secret_from_file(env_name)
    if v is not None:
        return v
    return os.environ.get(env_name)


def _is_production() -> bool:
    return os.environ.get("SIA_ENV", "dev").lower() == "production"


class DatabaseSettings(BaseSettings):
    host: str = "localhost"
    port: int = 3306
    user: str = "sia"
    password: str = ""
    database: str = "sia"
    pool_size: int = 10
    pool_recycle: int = 3600

    # TLS (SEC-007)
    tls_mode: str = "disabled"  # disabled | preferred | required
    tls_ca_path: str = "/etc/sia/tls/mysql-ca.crt"

    @property
    def async_url(self) -> str:
        # TLS parameters are passed via connect_args (see common/database.py).
        return (
            f"mysql+aiomysql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    def async_connect_args(self) -> dict:
        """TLS + driver connect args (SEC-007)."""
        args: dict = {}
        if self.tls_mode in ("preferred", "required"):
            ssl_cfg: dict = {}
            if os.path.exists(self.tls_ca_path):
                ssl_cfg["ca"] = self.tls_ca_path
            # aiomysql accepts a bool or dict; dict enables cert verification
            # when a CA is provided, otherwise relies on system CAs.
            args["ssl"] = ssl_cfg or True
        return args

    @model_validator(mode="after")
    def _require_password_in_prod(self) -> DatabaseSettings:
        if _is_production():
            pwd = self.password or _resolve_secret("SIA_MYSQL_PASSWORD") or ""
            if not pwd:
                raise RuntimeError(
                    "SIA_MYSQL_PASSWORD is required in production (env=production)"
                )
            self.password = pwd
        return self

    model_config = SettingsConfigDict(env_prefix="SIA_MYSQL_", extra="ignore")


class RedisSettings(BaseSettings):
    host: str = "localhost"
    port: int = 6379
    password: str = ""
    db: int = 0
    tls_enabled: bool = False
    tls_ca_path: str = "/etc/sia/tls/redis-ca.crt"

    @property
    def url(self) -> str:
        auth = f":{self.password}@" if self.password else ""
        scheme = "rediss" if self.tls_enabled else "redis"
        url = f"{scheme}://{auth}{self.host}:{self.port}/{self.db}"
        if self.tls_enabled and os.path.exists(self.tls_ca_path):
            url += f"?ssl_ca_certs={self.tls_ca_path}"
        return url

    @model_validator(mode="after")
    def _resolve_pw_from_secret(self) -> RedisSettings:
        if not self.password:
            v = _resolve_secret("SIA_REDIS_PASSWORD")
            if v is not None:
                self.password = v
        return self

    model_config = SettingsConfigDict(env_prefix="SIA_REDIS_", extra="ignore")


class MilvusSettings(BaseSettings):
    host: str = "localhost"
    port: int = 19530
    token: str = ""
    collection_name: str = "intel_vectors"

    @model_validator(mode="after")
    def _resolve_token(self) -> MilvusSettings:
        if not self.token:
            v = _resolve_secret("SIA_MILVUS_TOKEN")
            if v is not None:
                self.token = v
        return self

    model_config = SettingsConfigDict(env_prefix="SIA_MILVUS_", extra="ignore")


class MinIOSettings(BaseSettings):
    enabled: bool = True
    host: str = "localhost"
    port: int = 9000
    access_key: str = ""
    secret_key: str = ""
    bucket: str = "sia-reports"
    secure: bool = False

    @property
    def endpoint(self) -> str:
        return f"{self.host}:{self.port}"

    @model_validator(mode="after")
    def _require_creds_in_prod(self) -> MinIOSettings:
        if not self.access_key:
            v = _resolve_secret("SIA_MINIO_ACCESS_KEY")
            if v is not None:
                self.access_key = v
        if not self.secret_key:
            v = _resolve_secret("SIA_MINIO_SECRET_KEY")
            if v is not None:
                self.secret_key = v

        if _is_production() and self.enabled:
            if not self.access_key or not self.secret_key:
                raise RuntimeError(
                    "SIA_MINIO_ACCESS_KEY and SIA_MINIO_SECRET_KEY are required "
                    "in production when MinIO is enabled"
                )
            if self.access_key == "minioadmin" or self.secret_key == "minioadmin":
                raise RuntimeError(
                    "Default 'minioadmin' credentials are not allowed in production"
                )
        return self

    model_config = SettingsConfigDict(env_prefix="SIA_MINIO_", extra="ignore")


class AuthSecretSettings(BaseSettings):
    """JWT / API-key secrets. Loaded from file first, env second."""

    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"  # HS256 | RS256
    jwt_private_key: str = ""  # base64 PEM (RS256)
    jwt_public_key: str = ""  # base64 PEM (RS256)
    api_key: str = ""
    admin_password: str = ""

    @model_validator(mode="after")
    def _resolve_and_validate(self) -> AuthSecretSettings:
        # pull from /etc/sia/secrets or env
        self.jwt_secret = self.jwt_secret or _resolve_secret("SIA_AUTH_JWT_SECRET") or ""
        self.jwt_algorithm = (
            self.jwt_algorithm or _resolve_secret("SIA_AUTH_JWT_ALGORITHM") or "HS256"
        )
        self.jwt_private_key = (
            self.jwt_private_key or _resolve_secret("SIA_AUTH_JWT_PRIVATE_KEY") or ""
        )
        self.jwt_public_key = (
            self.jwt_public_key or _resolve_secret("SIA_AUTH_JWT_PUBLIC_KEY") or ""
        )
        self.api_key = self.api_key or _resolve_secret("SIA_API_KEY") or ""
        self.admin_password = (
            self.admin_password or _resolve_secret("SIA_ADMIN_PASSWORD") or ""
        )

        if _is_production():
            if self.jwt_algorithm == "HS256":
                if not self.jwt_secret or len(self.jwt_secret) < 32:
                    raise RuntimeError(
                        "SIA_AUTH_JWT_SECRET must be ≥ 32 chars in production "
                        "(HS256). Generate with: openssl rand -hex 32"
                    )
                if self.jwt_secret in ("change-me-in-production", "changeme", "secret"):
                    raise RuntimeError(
                        "SIA_AUTH_JWT_SECRET uses a placeholder value. "
                        "Generate a real secret with: openssl rand -hex 32"
                    )
            elif self.jwt_algorithm == "RS256":
                if not self.jwt_private_key or not self.jwt_public_key:
                    raise RuntimeError(
                        "RS256 requires SIA_AUTH_JWT_PRIVATE_KEY and "
                        "SIA_AUTH_JWT_PUBLIC_KEY (base64-encoded PEM) in production"
                    )
            else:
                raise RuntimeError(
                    f"Unsupported JWT algorithm: {self.jwt_algorithm} (expected HS256 or RS256)"
                )

            if not self.api_key:
                raise RuntimeError("SIA_API_KEY is required in production")

        # Dev fallback: generate an ephemeral JWT secret so the app can boot.
        if not _is_production() and self.jwt_algorithm == "HS256" and not self.jwt_secret:
            self.jwt_secret = _secrets_mod.token_hex(32)

        return self

    model_config = SettingsConfigDict(env_prefix="SIA_AUTH_", extra="ignore")


class Settings(BaseSettings):
    """Root application settings."""

    env: str = "dev"
    debug: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    log_level: str = "INFO"
    log_json_format: bool = False
    https_proxy: str = ""
    otlp_endpoint: str = ""

    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    milvus: MilvusSettings = Field(default_factory=MilvusSettings)
    minio: MinIOSettings = Field(default_factory=MinIOSettings)
    auth: AuthSecretSettings = Field(default_factory=AuthSecretSettings)

    prompts_dir: str = "prompts"
    workflows_dir: str = "workflows"
    config_dir: str = "config"

    @model_validator(mode="after")
    def _validate_env(self) -> Settings:
        if self.env == "production" and self.debug:
            raise RuntimeError("SIA_DEBUG must be false in production")
        return self

    model_config = SettingsConfigDict(env_prefix="SIA_", extra="ignore")


def _resolve_env_vars(obj: object) -> object:
    """Recursively resolve ${ENV_VAR:-default} patterns in config values."""
    import re

    pattern = re.compile(r"\$\{([^}]+)\}")

    def _resolve_match(m: "re.Match[str]") -> str:
        expr = m.group(1)
        if ":-" in expr:
            var, default = expr.split(":-", 1)
            return os.environ.get(var, default)
        return os.environ.get(expr, "")

    if isinstance(obj, str):
        return pattern.sub(_resolve_match, obj)
    if isinstance(obj, dict):
        return {k: _resolve_env_vars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_env_vars(v) for v in obj]
    return obj


def load_yaml_config(path: str) -> dict:
    """Load a YAML configuration file with env var resolution."""
    filepath = Path(path)
    if not filepath.exists():
        return {}
    with filepath.open() as f:
        raw = yaml.safe_load(f) or {}
    return _resolve_env_vars(raw)


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()


def get_llm_config() -> dict:
    """Load LLM gateway configuration from YAML."""
    settings = get_settings()
    config_path = os.path.join(settings.config_dir, "llm_gateway.yaml")
    return load_yaml_config(config_path)


@lru_cache
def get_auth_config() -> dict:
    """Load authentication configuration from YAML."""
    settings = get_settings()
    config_path = os.path.join(settings.config_dir, "auth.yaml")
    return load_yaml_config(config_path)
