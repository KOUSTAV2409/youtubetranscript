from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    cors_origins: str = "http://localhost:5173"
    database_path: str = "data/cache.db"
    max_transcript_chars: int = 60_000

    # YouTube blocks most cloud IPs. Free/datacenter proxies usually fail too;
    # residential (e.g. Webshare) is what reliably works. Paste-transcript is free fallback.
    webshare_proxy_username: str = ""
    webshare_proxy_password: str = ""
    # One URL, or comma-separated list to try in order:
    # YOUTUBE_PROXY_URL=http://1.2.3.4:8080,http://user:pass@host:port
    youtube_proxy_url: str = ""


settings = Settings()
