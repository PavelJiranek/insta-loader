# V3 YouTube Design Spec

## Goal

Add two commands — `youtube-meta` and `youtube-upload` — that generate YouTube-ready metadata from downloaded highlight data and upload the assembled videos as private YouTube videos.

## Architecture

Two new files: `insta_loader/youtube_meta.py` (metadata generation) and `insta_loader/youtube_uploader.py` (upload logic). `insta_loader/cli.py` gains a `YoutubeConfig` dataclass. `insta.py` gains two new subcommands. Both commands only process highlights that have a corresponding video in `output/<username>/videos/`.

## CLI

```
python insta.py youtube-meta   <insta-username> [--highlight NAME] [--output-dir DIR]
python insta.py youtube-upload <insta-username> [--highlight NAME] [--output-dir DIR] [--client-secrets PATH] [--playlist NAME]
```

`<insta-username>` is the Instagram username, which is also the folder name under `output/`. All YouTube output is grouped under `output/<insta-username>/youtube/`.

## Output structure

Metadata files are written to `output/<username>/youtube/<folder_name>.json`, one per highlight.

Example for highlight folder `🇿🇦9.CapeTown_Pt2` with slides from April–May 2026:

```json
{
  "highlight_folder": "🇿🇦9.CapeTown_Pt2",
  "video_path": "output/testuser/videos/🇿🇦9.CapeTown_Pt2.mp4",
  "youtube": {
    "title": "🇿🇦 Cape Town · Part 2 · Apr–May 2026",
    "description": "Cape Town highlights · Part 2 · Apr–May 2026\n\n@testuser",
    "tags": ["Cape Town", "South Africa", "Africa"],
    "category_id": "19",
    "privacy_status": "private"
  },
  "uploaded": false,
  "youtube_id": null
}
```

If the highlight is already uploaded, `"uploaded"` is `true` and `"youtube_id"` holds the YouTube video ID.

## `youtube_meta.py` module

Public interface: `run(config: YoutubeConfig) -> None`

Internal functions:

| Function | Responsibility |
|---|---|
| `_parse_title(folder_name)` | Strip sequence numbers, split camelCase, detect part number, extract place name |
| `_decode_flags(folder_name)` | Extract flag emojis, return list of ISO-3166-1 alpha-2 codes |
| `_build_tags(place_name, country_codes)` | Country names + continent + EU tag + US state if applicable |
| `_date_range(slides)` | First and last slide `date_utc`, return formatted string e.g. `Apr–May 2026` or `Nov 2025` |
| `_build_youtube_meta(folder_name, slides, username)` | Combine all of the above into the full metadata dict |
| `_write_meta(youtube_dir, folder_name, meta)` | Write JSON file; if file already exists and `uploaded: true`, skip; otherwise overwrite |

### Title generation rules

1. Strip leading sequence digits and dots: `8`, `9.`, `10.`
2. Strip flag emojis (processed separately)
3. Split camelCase into words: `CapeTown` → `Cape Town`, `CapePeninsula` → `Cape Peninsula`
4. Replace underscores with spaces, strip leftover punctuation
5. Detect part suffix from `_Pt1`, `_Pt2`, `_Part1`, `Part_II` etc. → `· Part N`
6. Append date range: `· Apr–May 2026`

Final format: `{flags} {place_name}[ · Part N] · {date_range}`

Examples:
- `🇿🇦9.CapeTown_Pt2` + Apr–May 2026 → `🇿🇦 Cape Town · Part 2 · Apr–May 2026`
- `8🇿🇦CapePeninsula` + Nov 2025 → `🇿🇦 Cape Peninsula · Nov 2025`
- `🇦🇷_Buenos_Aires` + Mar 2026 → `🇦🇷 Buenos Aires · Mar 2026`
- `🇺🇸LosAngeles` + Jun 2025 → `🇺🇸 Los Angeles · Jun 2025`

### Tag generation rules

From flag emoji(s):
- Country name (via `pycountry`)
- Continent — two tags for the Americas: both `Americas` and `North America` or `South America` depending on country; other continents get one tag (e.g. `Europe`, `Africa`, `Asia`, `Oceania`)
- `EU` if country is an EU member (bundled list of 27 ISO codes)

From place name:
- The extracted place name itself as a tag

Flag emojis are treated as hints, not requirements — titles may omit them due to Instagram's character limits. Country inference falls back to the place name:
- If flag present: use it as the primary country signal
- If no flag: check place name against `CITY_TO_COUNTRY` (bundled dict of well-known cities → ISO code); if matched, use that country for all tag generation
- If neither flag nor recognisable city: generate tags from place name only (no country/continent tags)

US state enrichment:
- If country resolves to `US` (from flag or city lookup), check place name against `CITY_TO_STATE` and add the state name as a tag

Example tags for `🇿🇦 Cape Town · Part 2`: `["Cape Town", "South Africa", "Africa"]`
Example tags for `🇺🇸 Los Angeles`: `["Los Angeles", "California", "United States", "North America", "Americas"]`
Example tags for `🇧🇷 São Paulo`: `["São Paulo", "Brazil", "South America", "Americas"]`
Example tags for `🇦🇹 Zillertal`: `["Zillertal", "Austria", "Europe", "EU"]`

### Date range format

- Same month: `Nov 2025`
- Adjacent months, same year: `Apr–May 2026`
- Different years: `Dec 2025–Jan 2026`

Derived from `date_utc` of the first and last non-failed slides in `metadata.json`.

## `youtube_uploader.py` module

Public interface: `run(config: YoutubeConfig) -> None`

Internal functions:

| Function | Responsibility |
|---|---|
| `_get_credentials(client_secrets_path)` | Load or refresh OAuth token; open browser on first run |
| `_get_or_create_playlist(youtube, name)` | Find existing playlist by name or create it (private); return playlist ID |
| `_upload_video(youtube, meta, video_path)` | Call YouTube Data API v3 `videos.insert`; return video ID |
| `_add_to_playlist(youtube, playlist_id, video_id)` | Call `playlistItems.insert` to add video to playlist |
| `_mark_uploaded(meta_path, youtube_id)` | Update JSON file with `uploaded: true` and `youtube_id` |

### Playlist

- `--playlist NAME` flag (default: `"Story Highlights"`)
- On first upload of a run, `_get_or_create_playlist` searches the authenticated user's playlists for one matching `NAME` (case-insensitive). If not found, creates it as a private playlist.
- Every successfully uploaded video is added to the playlist via `playlistItems.insert`.
- The playlist ID is stored in memory for the duration of the run (one lookup per run, not per video).
- Required additional OAuth scope: `https://www.googleapis.com/auth/youtube` (covers both upload and playlist management).

### Authentication

- `client_secrets.json` path: `--client-secrets` flag, or `YOUTUBE_CLIENT_SECRETS` env var, or default `~/.config/instaloader/youtube_client_secrets.json`
- Token saved to `~/.config/instaloader/youtube_token.json`
- Scopes: `https://www.googleapis.com/auth/youtube` (covers upload and playlist management)
- If `client_secrets.json` is missing, print setup instructions and exit 1:
  ```
  ✗  YouTube client secrets not found at <path>.
     To set up:
     1. Go to https://console.cloud.google.com/
     2. Create a project → Enable YouTube Data API v3
     3. Create OAuth 2.0 credentials (Desktop app)
     4. Download and save as <path>
  ```

### Upload behaviour

- Reads `output/<username>/youtube/*.json` (filtered by `--highlight` if provided)
- Skips files where `"uploaded": true`
- Skips files where `video_path` does not exist on disk, prints a warning
- On success: updates `uploaded: true`, `youtube_id: "<id>"`
- On API error: prints error, marks file as failed with `"upload_error": "<message>"`, continues to next

### Progress output

Uses Rich (same pattern as downloader and video creator):
- `✓  Cape Town Part 2 → youtube.com/watch?v=abc123 (private)`
- `–  Cape Town Part 2 skipped (already uploaded)`
- `✗  Cape Town Part 2 — upload failed: <reason>`

## `YoutubeConfig` dataclass

Added to `insta_loader/cli.py`:

```python
@dataclass
class YoutubeConfig:
    username: str
    highlight: Optional[str] = None
    output_dir: Optional[str] = None
    client_secrets: Optional[str] = None
    playlist: str = "Story Highlights"
```

## Dependencies

Added to `requirements.txt`:
- `pycountry>=22.0` — country name from ISO code
- `google-api-python-client>=2.0` — YouTube Data API v3
- `google-auth-oauthlib>=1.0` — OAuth 2.0 flow
- `google-auth-httplib2>=0.1` — HTTP transport for google-auth

## Files

| File | Change |
|---|---|
| `insta_loader/youtube_meta.py` | Create — metadata generation |
| `insta_loader/youtube_uploader.py` | Create — upload logic |
| `insta_loader/cli.py` | Modify — add `YoutubeConfig` |
| `insta.py` | Modify — add `youtube-meta` and `youtube-upload` subcommands |
| `requirements.txt` | Modify — add four new dependencies |
| `README.md` | Update — add youtube commands section, future AI-tags note |

## Testing

`tests/test_youtube_meta.py`:
- `_parse_title`: camelCase splitting, sequence number stripping, part detection
- `_decode_flags`: single flag, multiple flags, no flag
- `_build_tags`: country + continent + EU, US + state, no flag
- `_date_range`: same month, adjacent months, cross-year
- `_build_youtube_meta`: full integration with known input/output
- `run`: skips highlights with no video file, skips already-uploaded, writes JSON

`tests/test_youtube_uploader.py`:
- `_get_credentials`: loads existing token, triggers browser flow when missing
- `_get_or_create_playlist`: returns existing playlist ID, creates new if not found
- `_upload_video`: correct API call shape (mocked)
- `_add_to_playlist`: correct playlistItems.insert call (mocked)
- `_mark_uploaded`: updates JSON correctly
- `run`: skips already-uploaded, skips missing video, handles API error, adds to playlist

## Future

- `--ai-tags` flag: pass each image slide through a vision model (e.g. Claude) to identify landmarks and add them as tags. Opt-in due to API cost and latency (~1 call per image slide).
