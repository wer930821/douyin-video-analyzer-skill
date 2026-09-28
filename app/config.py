from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str = ""
    vision_model: str = "gpt-5.6-luna"
    transcribe_model: str = "gpt-4o-mini-transcribe"
    douyin_api_base: str = "http://127.0.0.1:8001"
    douyin_api_key: str = ""
    max_video_mb: int = 120
    frame_interval_seconds: int = 4
    max_frames: int = 18
    request_timeout_seconds: int = 90

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
