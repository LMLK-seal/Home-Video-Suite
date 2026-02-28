# 🎬 Home Video Suite

A local, browser-based video utility built with Gradio. Stream your home videos with subtitle support, convert MKV/AVI files to web-compatible MP4, and permanently burn hardcoded subtitles all from one clean interface. No cloud upload required.

📡 Share with family & friends - no upload needed.
Every time you launch the app, Gradio generates a temporary public link (e.g. https://xxxx.gradio.live) that's printed in your terminal. Share that link with anyone on the internet and they can watch your videos directly from your machine no file sharing service, no cloud storage, no account required. The link stays active as long as the app is running and expires shortly after you close it. (Right click on the video and copy the link).


---

![Home Video Suite](https://github.com/LMLK-seal/Home-Video-Suite/blob/main/Screenshots/Screenshot.png)

## ✨ Features

### ▶️ Stream Videos
- Browse a local folder and load all supported video files in one click
- Optional subtitle support (`.srt` / `.vtt`) with automatic language matching
- On-the-fly subtitle re-encoding so non-UTF-8 files (Hebrew, Arabic, Cyrillic, etc.) display correctly in the browser player

### 🔧 Convert to MP4
- Convert MKV, AVI, MOV and other formats to a web-compatible MP4
- **Fast Copy** mode — remuxes video stream as-is, re-encodes audio to AAC (seconds, lossless quality)
- **Full Re-encode** mode - re-encodes with H.264 + AAC for maximum compatibility (smaller file, slower)
- Real-time progress bar and cancellation support

### 🔥 Burn Subtitles (Hardsub)
- Permanently embed an `.srt` subtitle file into any video
- Handles non-UTF-8 subtitle encodings: Hebrew, Arabic, Cyrillic, Western European, or auto-detect
- Seven built-in subtitle styles:
  - Classic White, Yellow Bold, Cinema Black Box, Top of Screen, Large + Bold, Cyan Outline, Minimal
- Real-time progress bar and cancellation support
- Original file is **never modified** - output is always a new file

---

## 🖥️ Requirements

- Python 3.10+
- [FFmpeg](https://ffmpeg.org/) (see installation below)

---

## 📦 Installation

### 1. Clone the repository

```bash
git clone https://github.com/LMLK-seal/home-video-suite.git
cd home-video-suite
```

### 2. Install Python dependencies

```bash
pip install gradio chardet
```

### 3. Install FFmpeg

**Windows (recommended):**
```powershell
winget install ffmpeg
```
> ⚠️ After running `winget install ffmpeg`, **close your terminal and open a new one** before launching the app so the PATH is refreshed. The app also auto-detects FFmpeg from common WinGet, Chocolatey, and Scoop install locations as a fallback.

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt install ffmpeg
```

---

## 🚀 Usage

```bash
python Home_Video_Suite.py
```

The app will launch in your browser automatically. Keep the terminal open while using the app.

A public shareable link is also printed to the terminal (powered by Gradio's `share=True`) — useful for accessing the app from another device on your network.

---

## 📁 Supported Formats

| Type | Formats |
|------|---------|
| Video (Stream) | `.mp4`, `.webm`, `.ogg` |
| Video (Convert / Burn) | `.mp4`, `.mkv`, `.avi`, `.mov`, `.webm` |
| Subtitles | `.srt`, `.vtt` |

> MKV and AVI files must be converted to MP4 before they can be streamed in the browser player.

---

## 🗂️ Project Structure

```
Home_Video_Suite.py   # Single-file application
README.md
```

---

## 🔧 How It Works

The app is built on **Gradio Blocks** and uses **FFmpeg** under the hood for all video processing. File and folder selection uses native OS dialogs via `tkinter`. Subtitle encoding detection uses the `chardet` library.

FFmpeg is located at runtime using the following search order:

1. System `PATH`
2. WinGet Links (`%LOCALAPPDATA%\Microsoft\WinGet\Links`)
3. WinGet Packages directory (`gyan.ffmpeg`)
4. Chocolatey (`C:\ProgramData\chocolatey\bin`)
5. Scoop shims

---

## 📄 License

MIT License — feel free to use, modify, and distribute.
