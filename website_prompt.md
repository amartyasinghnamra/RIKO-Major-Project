# RIKO Website Prompt

Update the existing RIKO website. Do not rebuild it or change content that has already been approved.

## Project facts

- The repository root is the project root. There is no `RIKO_PROJECT` subdirectory inside the clone.
- The native desktop app is built with Python and Tkinter. It calls RIKO's shared text and voice backend directly; it is not a browser wrapper.
- The app runs on Windows and Linux. Its cards, composer, and chat surfaces use Tkinter Canvas drawing for cross-platform rounded corners. Keep the OS-native title bar.
- The desktop app has text and hands-free voice modes, Markdown-formatted model replies, a stop control, local profiles, and zoom from 80% to 160%. Zoom works with the visible −/+ controls, Ctrl/Command keyboard shortcuts, and Ctrl/Command plus mouse wheel.
- In voice mode, Kokoro receives cleaned text so Markdown markers such as `**` are not read aloud.
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

## Responsive behavior

Verify at 390px viewport width:

- The navigation collapses into a menu.
- The hero terminal illustration scrolls horizontally instead of overflowing the page.
- The feature grid becomes one column.
- Screenshot cards remain readable and preserve their 16:10 image slots.

Keep the visual design consistent with the existing site. Make only the requested changes, preserve honest hardware and privacy claims, and use placeholders rather than invented screenshots or product claims.
