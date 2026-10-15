# Changelog

## 2026-10-15

### Added

- Added structured tool-call events carrying the tool name, arguments, and result paths from the conversation manager.
- Added collapsed-by-default tool cards inside assistant replies. They expand to show the query or pattern and the files returned, in both text and voice mode.
- Kept tool events out of Kokoro's text stream, leaving spoken response handling unchanged.
- Mirrored chat alignment: user messages sit on the right, while wider RIKO replies sit on the left with a distinct muted-teal surface.
- Added source staging, an Inno Setup definition for Windows, an AppImage first-run launcher for Linux, and a GitHub Actions workflow to build both packages. Packages download dependencies and model assets during setup rather than bundling them.
- Added neutral text-chat and voice-chat screenshot placeholders to the README.

### Fixed

- Corrected the Linux installer partial-download path so failed Kokoro downloads are kept as `.part` files beside their target assets.
- Made package staging create an empty Kokoro asset directory when a clean checkout has no ignored `models/` directory.
- Added LF line-ending rules for shell and desktop-entry files, and corrected the AppImage desktop metadata.

### Documentation

- Modernized the README, added the CLI Settings menu entry, documented package setup behavior, and clarified Linux support and retry requirements.
- Updated `website_prompt.md` with current feature, packaging, and setup facts while retaining its approved-copy constraints.

### Validation

- Full Python test suite: 109 passed, including a clean-checkout staging regression test.
- Python compilation, Linux shell syntax checks, AppImage desktop-entry validation, package staging checks, and `git diff --check` passed.
- Built `build/output/RIKO-Setup.exe` with Inno Setup and `build/output/RIKO-x86_64.AppImage` in Ubuntu WSL.

### Artifact policy

- Generated installers stay under the ignored `build/` directory; model weights and private local profiles are not committed.
- GitHub Actions uploads Windows and Linux build artifacts for 14 days on main/manual runs. Pushing a `v*` tag creates a GitHub Release and attaches both installers.
