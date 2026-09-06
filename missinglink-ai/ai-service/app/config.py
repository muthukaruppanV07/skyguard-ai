from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AI_", env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8081
    api_key: str = "change-me-ai-key"
    database_url: str = "postgresql+psycopg://missinglink:change-me@localhost:5432/missinglink"
    fallback_allowed: bool = True
    vector_dim: int = 512

    # Model selection ("" or "auto" => fallback heuristics)
    face_model: str = "auto"
    embedding_model: str = "auto"
    object_model: str = "auto"

    # Matching weights; auto-renormalised when a signal is missing
    weight_face: float = 0.30
    weight_clothing: float = 0.20
    weight_accessory: float = 0.10
    weight_body: float = 0.10
    weight_image: float = 0.15
    weight_location: float = 0.05
    weight_time: float = 0.05
    weight_text: float = 0.05

    min_match_score: float = 0.35
    match_k: int = 10

    bootstrap_on_start: bool = True

    @property
    def weights(self) -> List[float]:
        return [
            self.weight_face,
            self.weight_clothing,
            self.weight_accessory,
            self.weight_body,
            self.weight_image,
            self.weight_location,
            self.weight_time,
            self.weight_text,
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
