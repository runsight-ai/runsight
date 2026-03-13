from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    base_path: str = "."
    db_url: str = "sqlite:///./runsight.db"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = SettingsConfigDict(env_prefix="RUNSIGHT_")


settings = Settings()
