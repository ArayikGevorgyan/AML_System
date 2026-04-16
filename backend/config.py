from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    APP_NAME: str = "AML Transaction Monitoring System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/aml_system.db"

    SECRET_KEY: str = "aml-super-secret-key-change-in-production-2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours

    SDN_XML_PATH: str = str(Path.home() / "Downloads" / "sdn_advanced.xml")

    HIGH_RISK_COUNTRIES: list = [
        "IR", "KP", "SY", "CU", "SD", "RU", "BY", "MM",
        "AF", "IQ", "LY", "SO", "YE", "VE", "ZW",
    ]

    # SMTP email settings (set in .env file)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""

    ANTHROPIC_API_KEY: str = ""

    LARGE_TRANSACTION_THRESHOLD: float = 10_000.0
    STRUCTURING_THRESHOLD: float = 9_500.0
    VELOCITY_WINDOW_HOURS: int = 24
    VELOCITY_COUNT_THRESHOLD: int = 5
    VELOCITY_AMOUNT_THRESHOLD: float = 25_000.0

    class Config:
        env_file = ".env"


settings = Settings()
