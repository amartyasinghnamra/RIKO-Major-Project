# RIKO Website Prompt

Update the existing RIKO website. Do not rebuild it or change content that has already been approved.

## Project facts

- The repository root is the project root. There is no `RIKO_PROJECT` subdirectory inside the clone.
- The native desktop app is built with Python and Tkinter. It calls RIKO's shared text and voice backend directly; it is not a browser wrapper.
- The app runs on Windows and Linux. Its cards, composer, and chat surfaces use Tkinter Canvas drawing for cross-platform rounded corners. Keep the OS-native title bar.
- The CLI menu offers Text Chat, Voice Chat, Settings & Selectors, and Exit. Settings & Selectors covers persona, Kokoro voice and speed, and profile context.
- The desktop app and CLI share the chat sessions and audio pipeline. The desktop app has text and hands-free voice modes, Markdown-formatted model replies, a stop control, local profiles, and zoom from 80% to 160%. Zoom works with the visible −/+ controls, Ctrl/Command keyboard shortcuts, and Ctrl/Command plus mouse wheel.
- Preferences include ten configurable behavior controls: cuteness, playfulness, teasing, affection/warmth, energy, talkativeness, spontaneity, conversation initiative, emotional awareness, and reassurance, plus response-style presets. These are local style preferences that yield to the user's current request and serious tone.
- Kokoro Read aloud can optionally cache repeated synthesized phrases locally. It is off by default, capped at 128 MB, and clearable from Preferences. Hands-free Voice mode still uses the streaming Kokoro path.
- In text mode, assistant replies provide Regenerate and Read aloud actions. Preferences can enable or disable text-to-voice; speech is user-triggered and not automatic. A microphone control captures local Faster-Whisper transcription, shows rolling drafts in the composer, and finalizes the transcript when recording stops. Each recording is limited to two minutes; the user reviews and sends the transcript.
- While a response is generating, Stop or Escape cancels the active Ollama stream and Kokoro playback. Stopping a voice response leaves the voice session active and listening.
- In voice mode, selecting Voice starts listening and selecting Chat stops listening and playback. Kokoro receives cleaned text so Markdown markers such as `**` are not read aloud. Speaking over a reply can interrupt generation and capture a new utterance; short phrases such as “stop,” “wait,” “pause,” and “hold on” are treated as controls.
- Voice interruption is a prototype feature; acoustic echo cancellation is not implemented, and headphones are recommended. Do not promise reliable barge-in, perfect transcription, zero latency, or support for every language, device, or environment.
- Installers create or reuse the repository-local `.venv-tts`, install dependencies, fetch Kokoro assets, prepare Ollama with `qwen3:4b-instruct`, warm the Faster-Whisper `base` model cache, and start profile setup when no personal profile exists. Profile saving requires confirmation. Windows automation uses `winget` when needed; automatic Linux setup targets Debian/Ubuntu with `apt-get`.
- If a Kokoro download fails on Linux, the installer preserves a `.part` file under `models/kokoro/`; inspect or remove that partial asset before retrying. Do not describe installer reruns as failure-proof.
- A GitHub Actions workflow builds a per-user Windows `RIKO-Setup.exe` and an x86_64 Linux AppImage. These are setup-time download installers, not offline bundles; the AppImage's first run copies the app to the user's data directory and opens a terminal to install prerequisites and download dependencies/models. Do not present workflow artifacts as public release downloads unless they have actually been published as releases.
- RIKO is local-first, not guaranteed fully offline. Setup needs internet access for dependencies and model downloads. Do not claim that every dependency or integration works offline.
- Do not claim unfinished work is complete. GTK4 remains a roadmap item; the current GUI is Tkinter. Growth mode and voice barge-in tuning remain in progress.

## Keep approved content intact

- Keep the existing hero copy verbatim and keep the terminal illustration in the hero.
- Keep the Privacy section unchanged.
- Keep the Requirements estimates unchanged.
- Keep the current Status list unchanged, then include the two-line Roadmap block below inside Status.
- Keep this credits line exactly, with no extra contributor-role detail: “Initiated by Amartya Singh Namra (B.Tech AI & ML), with Priyanshu Tiwari and Saurabh Pandey.”

## Page structure and screenshots

Keep the current page and add a **Screenshots** section between **How it works** and **Install**. Use two neutral placeholder images until the real PNGs are supplied. Each image slot must use a 16:10 aspect ratio, descriptive alt text, and these exact captions:

1. **Text chat — a streaming reply from the local model**
2. **Voice chat — microphone in, Kokoro speech out**

Inside **Status**, show this Roadmap block exactly:

- Desktop GUI (GTK4) — in progress
- Growth mode and voice barge-in tuning — in progress

Do not present either roadmap item as finished.

## Installation instructions

Show repository-root commands only:

**Windows CMD**

```bat
git clone <repo-url>
cd RIKO-Major-Project
install.bat
run.bat
```

**Linux**

```sh
git clone <repo-url>
cd RIKO-Major-Project
bash install.sh
bash run.sh
```

The installer and launcher scripts are at the repository root. Never add a `RIKO_PROJECT` path segment after `cd`.
The Windows installer can use `winget` for missing Python, Ollama, or curl. The Linux installer uses `sudo` (or root) with `apt-get` and configures Debian/Ubuntu only. Explain that first-time setup downloads models and needs internet access. Do not imply that model assets or personal profiles are committed to the repository. Note the failed Kokoro-download retry caveat above when documenting Linux setup. If discussing the packaged downloads, distinguish generated GitHub Actions artifacts from published GitHub Releases.

## Responsive behavior

Verify at 390px viewport width:

- The navigation collapses into a menu.
- The hero terminal illustration scrolls horizontally instead of overflowing the page.
- The feature grid becomes one column.
- Screenshot cards remain readable and preserve their 16:10 image slots.

Keep the visual design consistent with the existing site. Make only the requested changes, preserve honest hardware and privacy claims, and use placeholders rather than invented screenshots or product claims.
