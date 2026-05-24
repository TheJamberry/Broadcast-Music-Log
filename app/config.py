from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    database_url: str = Field("sqlite:///./broadcast_music_log.db")
    acoustid_api_key: str = Field(...)
    sample_duration: int = Field(18)
    poll_interval_seconds: int = Field(25)
    confidence_threshold: float = Field(0.75)
    ignore_window_seconds: int = Field(300)
    ffmpeg_path: str = Field("ffmpeg")
    fpcalc_path: str = Field("fpcalc")
    temp_dir: str = Field("./tmp")


settings = Settings()
