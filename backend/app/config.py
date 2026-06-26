from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "change-me-in-production-please"
DEFAULT_ADMIN_PASSWORD = "admin1234"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # development | production — production refuses insecure default secrets
    environment: str = "development"

    # MongoDB
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "taskmanagement"

    # Auth
    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 1 day

    # Default admin (seeded on startup if no users exist)
    admin_username: str = "admin"
    admin_email: str = "admin@example.com"
    admin_password: str = DEFAULT_ADMIN_PASSWORD

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _enforce_production_secrets(self):
        # In production, fail fast rather than ship a forgeable token / known login.
        if self.environment == "production":
            if not self.jwt_secret or self.jwt_secret == DEFAULT_JWT_SECRET:
                raise ValueError(
                    "JWT_SECRET must be set to a strong, unique value in production."
                )
            if not self.admin_password or self.admin_password == DEFAULT_ADMIN_PASSWORD:
                raise ValueError(
                    "ADMIN_PASSWORD must be set to a non-default value in production."
                )
        return self


settings = Settings()
