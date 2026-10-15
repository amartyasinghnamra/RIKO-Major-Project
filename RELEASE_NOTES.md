# RIKO v0.1.0-preview.3

## Downloads

- `RIKO-Setup.exe` — Windows x64 per-user installer.
- `RIKO-x86_64.AppImage` — Linux x86_64 launcher and installer.

These are setup-download packages, not offline bundles. They fetch Python dependencies, Ollama, and model assets during setup. Internet access is required; model weights are not included in either download.

## Highlights

- Native Tkinter desktop app and terminal mode share the conversation and voice pipelines.
- Assistant tool lookups appear in collapsible cards in both text and voice sessions.
- User messages are right-aligned; wider RIKO replies are left-aligned.
- Local Ollama integration with `qwen3:4b-instruct`, Faster-Whisper transcription, and Kokoro speech synthesis.
- Local profiles and behavior preferences, response cancellation, Read aloud, and optional bounded speech caching.
- Windows installer adds Desktop and Start Menu shortcuts that open the GUI without a console window.
- Linux first launch creates Desktop and application-menu shortcuts. After setup, those shortcuts open the GUI directly.

## Setup

**Windows:** Run `RIKO-Setup.exe`. It installs RIKO per-user and runs setup. If Python, Ollama, or curl is missing, setup may use `winget` to install it. After setup, launch RIKO from the Desktop or Start Menu shortcut.

**Linux:** Make the AppImage executable and launch it. First launch opens a terminal to install prerequisites and download assets; automatic system setup supports Debian/Ubuntu and may request `sudo`. After setup, launch RIKO from the Desktop or application menu.

## Known limitations

- Linux package supports x86_64; automatic setup targets Debian/Ubuntu.
- Voice interruption is a prototype. Acoustic echo cancellation is not implemented; headphones are recommended.
- Setup requires internet access and several gigabytes of free space for dependencies and model downloads.
- Automated checks passed: 109 tests, including clean-checkout packaging, Python compilation, Linux shell syntax, desktop-entry validation, and package-content checks. Complete first-run dependency/model downloads and a live microphone-to-audio session have not been smoke-tested.

## Publishing

Push the `v0.1.0-preview.3` tag to trigger the packaging workflow. It builds both installers, creates a GitHub prerelease using these notes, and attaches `RIKO-Setup.exe` and `RIKO-x86_64.AppImage` automatically.
