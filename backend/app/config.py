from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Ortam ayarları; parola ve bağlantı bilgileri kod içine gömülmez."""

    db_host: str = "db"
    db_port: int = 3306
    db_name: str = "yem_simulation"
    db_user: str = "yem_simulation_app"
    db_password: str = "local_db_password"
    tz: str = "UTC"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )


settings = Settings()
