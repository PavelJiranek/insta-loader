import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def no_api_pause():
    """The real pause sleeps 2s+ per Instagram API call; never let tests wait on it.

    Tests that need to check the pause is called, or the delay it computes,
    use the yielded mock or insta_loader.downloader._api_delay directly.
    """
    with patch("insta_loader.downloader._api_pause") as m:
        yield m


@pytest.fixture(autouse=True)
def mock_summarizer_in_downloader(request):
    """Prevent downloader tests from hitting summarizer.run() which needs real disk layout."""
    if "test_downloader" in request.fspath.basename:
        with patch("insta_loader.downloader.summarizer") as m:
            yield m
    else:
        yield
