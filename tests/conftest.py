import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def mock_summarizer_in_downloader(request):
    """Prevent downloader tests from hitting summarizer.run() which needs real disk layout."""
    if "test_downloader" in request.fspath.basename:
        with patch("insta_loader.downloader.summarizer") as m:
            yield m
    else:
        yield
