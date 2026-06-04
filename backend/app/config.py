from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = ""
    sqlite_path: str = "./data.sqlite"
    port: int = 3001
    node_env: str = "development"
    groq_api_key: str = ""
    # Comma-separated list of allowed CORS origins, e.g.
    # "https://planner.ontwrpn.com,http://localhost:5173".
    # Left empty it defaults permissively (allow all) — safe for the single-container
    # deploy where the SPA is served same-origin, and convenient for local dev.
    # CORS_ORIGINS is the canonical name; FRONTEND_ORIGIN is accepted as an alias.
    cors_origins: str = ""
    frontend_origin: str = ""

    @property
    def cors_allow_origins(self) -> list[str]:
        raw = self.cors_origins or self.frontend_origin
        origins = [o.strip() for o in raw.split(",") if o.strip()]
        return origins or ["*"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
