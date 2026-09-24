from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Dùng SQLite cho môi trường phát triển
    DATABASE_URL: str = "sqlite:///./csms.db"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
