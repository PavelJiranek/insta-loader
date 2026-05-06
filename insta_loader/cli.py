from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    username: str
    output_dir: Optional[str]
    highlight: Optional[str]
    login_user: Optional[str]
    update: bool = False
    retry_failed: bool = False


@dataclass
class VideoConfig:
    username: str
    highlight: Optional[str] = None
    output_dir: Optional[str] = None
    image_duration: int = 10
    update: bool = False


@dataclass
class YoutubeConfig:
    username: str
    highlight: Optional[str] = None
    output_dir: Optional[str] = None
    client_secrets: Optional[str] = None
    playlist: str = "Story Highlights"
    update: bool = False
    privacy: str = "unlisted"
