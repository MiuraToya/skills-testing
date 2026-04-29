from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Reservation API"
    timezone: str = "Asia/Tokyo"
    database_url: str = "mysql+pymysql://app:app@db:3306/reservation_db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
