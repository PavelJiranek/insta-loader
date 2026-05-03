# Project Rules

## Changelog

After every commit (or logical batch of related commits) that adds a feature, fixes a bug, or changes behaviour, update `CHANGELOG.md`. Follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format — add entries under `[Unreleased]` at the top, grouped as:

- **Added** — new features
- **Changed** — changes to existing behaviour
- **Fixed** — bug fixes
- **Removed** — removed features

Skip changelog entries for docs-only commits (specs, plans, README), test-only commits, and chore/refactor commits that have no user-visible effect.

When a version is tagged, rename `[Unreleased]` to `[x.y.z] - YYYY-MM-DD` and open a new empty `[Unreleased]` section above it.

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/) for all commit messages:

```
<type>(<optional scope>): <description>
```

Common types: `feat`, `fix`, `docs`, `refactor`, `chore`, `test`

Examples:
- `feat(cli): add --highlight flag for single reel download`
- `fix(downloader): handle rate limit error with clean exit`
- `docs: add extending.md for V2 guidance`
- `chore: init project structure and requirements`
