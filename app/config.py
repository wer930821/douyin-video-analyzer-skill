from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    douyin_api_base: str = "http://127.0.0.1:8001"
    douyin_api_key: str = ""
    max_video_mb: int = 120
    frame_interval_seconds: int = 4
    max_frames: int = 8
    request_timeout_seconds: int = 90
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_fallback_models: str = "gemini-3.8-flash,gemini-3.5-flash"
    gemini_max_retries: int = 1

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
