from insta_loader.cli import VideoConfig

def test_video_config_defaults():
    c = VideoConfig(username="natgeo")
    assert c.highlight is None
    assert c.output_dir is None
