from unittest.mock import patch

from src.schemas import get_short_url


def test_get_short_url():
    result = get_short_url("abc123")
    assert result == "http://localhost:8000/abc123"


def test_get_short_url_with_trailing_slash():
    with patch("src.schemas.settings") as mock_settings:
        mock_settings.base_url = "http://example.com/"
        result = get_short_url("test")
        assert result == "http://example.com/test"
