from pathlib import Path

import pytest

from rendercart.core.config import Settings


def test_settings_loads_numeric_values_from_dotenv_as_strings(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("AI_EMBEDDING_DIMENSION=1024\n", encoding="utf-8")

    settings = Settings(_env_file=env_file)

    assert settings.ai_embedding_dimension == 1024


def test_embedding_dimension_must_match_database_vector_schema() -> None:
    with pytest.raises(ValueError, match="AI_EMBEDDING_DIMENSION must be 1024"):
        Settings(ai_embedding_dimension=768)
