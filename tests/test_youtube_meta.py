import pytest
from insta_loader.cli import YoutubeConfig


def test_youtube_config_defaults():
    c = YoutubeConfig(username="natgeo")
    assert c.highlight is None
    assert c.output_dir is None
    assert c.client_secrets is None
    assert c.playlist == "Story Highlights"
