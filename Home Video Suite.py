import gradio as gr
import os
import re
import shutil
import chardet
import platform
import subprocess
import time

# ═══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

SUPPORTED_VIDEO = ('.mp4', '.webm', '.ogg', '.mkv', '.avi')
SUPPORTED_SUBS  = ('.srt', '.vtt')

ENCODING_OPTIONS = [
    "Hebrew (Windows-1255)",
    "Auto (UTF-8)",
    "Western (Windows-1252)",
    "Cyrillic (Windows-1251)",
    "Arabic (Windows-1256)",
]

ENCODING_MAP = {
    "Hebrew":   "windows-1255",
    "Western":  "windows-1252",
    "Cyrillic": "windows-1251",
    "Arabic":   "windows-1256",
}

SUBTITLE_STYLES = {
    "Classic White (Default)": (
        "FontName=Arial,FontSize=22,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,Outline=2,Shadow=1,MarginV=20,Alignment=2"
    ),
    "Yellow Bold": (
        "FontName=Arial,FontSize=24,Bold=1,PrimaryColour=&H0000FFFF,"
        "OutlineColour=&H00000000,Outline=2,Shadow=1,MarginV=20,Alignment=2"
    ),
    "Cinema Black Box": (
        "FontName=Arial,FontSize=22,PrimaryColour=&H00FFFFFF,"
        "BackColour=&H80000000,BorderStyle=4,Outline=0,Shadow=0,"
        "MarginV=20,Alignment=2"
    ),
    "Top of Screen": (
        "FontName=Arial,FontSize=22,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,Outline=2,Shadow=1,MarginV=20,Alignment=8"
    ),
    "Large + Bold": (
        "FontName=Arial,FontSize=30,Bold=1,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,Outline=3,Shadow=2,MarginV=25,Alignment=2"
    ),
    "Cyan Outline": (
        "FontName=Arial,FontSize=22,PrimaryColour=&H00FFFF00,"
        "OutlineColour=&H00000000,Outline=2,Shadow=1,MarginV=20,Alignment=2"
    ),
    "Minimal (No Shadow)": (
        "FontName=Arial,FontSize=22,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,Outline=1,Shadow=0,MarginV=20,Alignment=2"
    ),
}

# ═══════════════════════════════════════════════════════════════════════════════
#  SHARED HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _get_ffmpeg() -> str:
    """
    Find ffmpeg at runtime, working around stale-PATH issues after winget installs.
    Search order: shutil.which → WinGet Links → WinGet Packages → Chocolatey → Scoop
    """
    found = shutil.which("ffmpeg")
    if found:
        return found

    user_profile = os.environ.get("USERPROFILE", "")

    winget_links = os.path.join(user_profile, "AppData", "Local",
                                "Microsoft", "WinGet", "Links", "ffmpeg.exe")
    if os.path.isfile(winget_links):
        return winget_links

    winget_pkgs = os.path.join(user_profile, "AppData", "Local",
                               "Microsoft", "WinGet", "Packages")
    if os.path.isdir(winget_pkgs):
        for entry in os.listdir(winget_pkgs):
            if entry.lower().startswith("gyan.ffmpeg"):
                for root, _, files in os.walk(os.path.join(winget_pkgs, entry)):
                    if "ffmpeg.exe" in files:
                        return os.path.join(root, "ffmpeg.exe")

    choco = r"C:\ProgramData\chocolatey\bin\ffmpeg.exe"
    if os.path.isfile(choco):
        return choco

    scoop = os.path.join(user_profile, "scoop", "shims", "ffmpeg.exe")
    if os.path.isfile(scoop):
        return scoop

    return ""


def _get_ffprobe() -> str:
    """Same search logic as _get_ffmpeg() but for ffprobe."""
    found = shutil.which("ffprobe")
    if found:
        return found

    user_profile = os.environ.get("USERPROFILE", "")

    winget_links = os.path.join(user_profile, "AppData", "Local",
                                "Microsoft", "WinGet", "Links", "ffprobe.exe")
    if os.path.isfile(winget_links):
        return winget_links

    winget_pkgs = os.path.join(user_profile, "AppData", "Local",
                               "Microsoft", "WinGet", "Packages")
    if os.path.isdir(winget_pkgs):
        for entry in os.listdir(winget_pkgs):
            if entry.lower().startswith("gyan.ffmpeg"):
                for root, _, files in os.walk(os.path.join(winget_pkgs, entry)):
                    if "ffprobe.exe" in files:
                        return os.path.join(root, "ffprobe.exe")

    choco = r"C:\ProgramData\chocolatey\bin\ffprobe.exe"
    if os.path.isfile(choco):
        return choco

    scoop = os.path.join(user_profile, "scoop", "shims", "ffprobe.exe")
    if os.path.isfile(scoop):
        return scoop

    return ""


def _time_to_seconds(time_str: str) -> float:
    try:
        h, m, s = time_str.split(':')
        return int(h) * 3600 + int(m) * 60 + float(s)
    except ValueError:
        return 0.0


def _startup_info():
    """Suppress console window on Windows."""
    si = None
    if os.name == 'nt':
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return si


def _no_window_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0


def _get_video_duration(video_path: str) -> float:
    ffprobe = _get_ffprobe()
    if not ffprobe:
        return 0.0
    cmd = [ffprobe, '-v', 'error',
           '-show_entries', 'format=duration',
           '-of', 'default=noprint_wrappers=1:nokey=1',
           video_path]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, creationflags=_no_window_flags())
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def _browse_path(is_folder=False, filetypes=None, title="Browse",
                 save=False, initial_file=""):
    """Open a native OS file/folder picker and return the selected path."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        if is_folder:
            path = filedialog.askdirectory(title=title)
        elif save:
            path = filedialog.asksaveasfilename(
                title=title,
                initialfile=initial_file,
                defaultextension=".mp4",
                filetypes=filetypes or [("MP4 Files", "*.mp4")]
            )
        else:
            path = filedialog.askopenfilename(
                title=title,
                filetypes=filetypes or [("All Files", "*.*")]
            )
        root.destroy()
        return path if path else gr.update()
    except Exception:
        return gr.update()


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 1 — STREAM VIDEOS
# ═══════════════════════════════════════════════════════════════════════════════

def browse_stream_folder() -> str:
    return _browse_path(is_folder=True, title="Select Video Folder")


def scan_folder(folder_path: str):
    folder_path = folder_path.strip('"').strip("'")

    if not os.path.isdir(folder_path):
        return (gr.update(choices=[], value=None),
                gr.update(choices=["None"], value="None"),
                "❌ Invalid folder path. Please check and try again.")

    video_files, sub_files = [], []
    for file in sorted(os.listdir(folder_path)):
        if file.endswith("_utf8.srt") or file.endswith("_utf8.vtt"):
            continue
        full = os.path.join(folder_path, file)
        if file.lower().endswith(SUPPORTED_VIDEO):
            video_files.append(full)
        elif file.lower().endswith(SUPPORTED_SUBS):
            sub_files.append(full)

    if not video_files:
        return (gr.update(choices=[], value=None),
                gr.update(choices=["None"], value="None"),
                f"⚠️ No videos found. Supported formats: {', '.join(SUPPORTED_VIDEO)}")

    sub_choices = ["None"] + sub_files
    default_sub = "None"
    first_base  = os.path.splitext(os.path.basename(video_files[0]))[0]
    for sub in sub_files:
        if first_base in sub:
            default_sub = sub
            break

    return (gr.update(choices=video_files, value=video_files[0]),
            gr.update(choices=sub_choices, value=default_sub),
            f"✅ Found {len(video_files)} video(s) and {len(sub_files)} subtitle(s).")


def _fix_subtitle_encoding(subtitle_path: str, encoding_choice: str) -> str | None:
    """Re-encode subtitle file to UTF-8 for the web player."""
    if not subtitle_path or subtitle_path == "None" or not os.path.exists(subtitle_path):
        return None

    target_enc = "utf-8"
    for key, enc in ENCODING_MAP.items():
        if key in encoding_choice:
            target_enc = enc
            break

    try:
        with open(subtitle_path, 'r', encoding=target_enc) as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(subtitle_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

    base = os.path.splitext(subtitle_path)[0]
    ext  = os.path.splitext(subtitle_path)[1]
    if base.endswith("_utf8"):
        base = base[:-5]
    safe_path = f"{base}_utf8{ext}"
    with open(safe_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return safe_path


def play_video(video_path: str, subtitle_path: str, encoding_choice: str):
    if not video_path or not os.path.exists(video_path):
        return gr.update(value=None, subtitles=None), "❌ No video selected."

    if video_path.lower().endswith(('.avi', '.mkv')):
        return (gr.update(value=None, subtitles=None),
                "❌ MKV/AVI cannot play directly. Use the '🔧 Convert' tab first.")

    valid_sub = None
    if subtitle_path and subtitle_path != "None":
        try:
            valid_sub = _fix_subtitle_encoding(subtitle_path, encoding_choice)
        except Exception:
            valid_sub = None

    lang = encoding_choice.split(' ')[0]
    return gr.update(value=video_path, subtitles=valid_sub), f"▶️ Playing · Subtitles: {lang}"


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 2 — CONVERT TO MP4
# ═══════════════════════════════════════════════════════════════════════════════

_conv_process: subprocess.Popen | None = None
_conv_cancel = False


def browse_conv_input():
    return _browse_path(
        title="Select Video to Convert",
        filetypes=[("Video Files", "*.mkv *.avi *.mov *.mp4 *.webm"), ("All Files", "*.*")]
    )


def conv_input_changed(input_path: str):
    """Auto-fill the output path when the user picks an input file."""
    if input_path and os.path.isfile(input_path):
        out = os.path.splitext(input_path)[0] + "_WEB.mp4"
        return out
    return gr.update()


def browse_conv_output(input_path: str):
    initial = ""
    if input_path:
        initial = os.path.splitext(os.path.basename(input_path))[0] + "_WEB.mp4"
    return _browse_path(save=True, title="Save Converted File As",
                        filetypes=[("MP4 Files", "*.mp4")], initial_file=initial)


def convert_video(input_path: str, output_path: str, conversion_mode: str):
    """Convert MKV/AVI/MOV → web-compatible MP4. Yields (status, progress 0.0–1.0)."""
    global _conv_process, _conv_cancel

    if not input_path or not os.path.isfile(input_path):
        yield "❌ Please select a valid input video.", 0.0
        return
    if not output_path:
        yield "❌ Please specify an output file path.", 0.0
        return
    if os.path.exists(output_path):
        yield "⚠️ Output file already exists. Delete it first or choose a different name.", 0.0
        return

    ffmpeg_exe = _get_ffmpeg()
    if not ffmpeg_exe:
        yield ("❌ FFmpeg not found. If you just ran 'winget install ffmpeg', "
               "close this terminal, open a new one, and restart the app.", 0.0)
        return

    cmd = [ffmpeg_exe, "-y", "-i", input_path]
    if "Fast" in conversion_mode:
        cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-sn"]
    else:
        cmd += ["-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-b:a", "256k", "-sn"]
    cmd.append(output_path)

    _conv_cancel  = False
    duration_re   = re.compile(r"Duration:\s*(\d{2}:\d{2}:\d{2}\.\d+)")
    time_re       = re.compile(r"time=\s*(\d{2}:\d{2}:\d{2}\.\d+)")

    try:
        _conv_process = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            universal_newlines=True, startupinfo=_startup_info()
        )
    except FileNotFoundError:
        yield f"❌ Could not launch FFmpeg at '{ffmpeg_exe}'. Try restarting your terminal.", 0.0
        return

    total_dur = 0.0
    yield "⏳ Starting…", 0.0

    for line in _conv_process.stderr:
        if _conv_cancel:
            break
        if total_dur == 0:
            m = duration_re.search(line)
            if m:
                total_dur = _time_to_seconds(m.group(1))
        m = time_re.search(line)
        if m and total_dur > 0:
            pct = min(_time_to_seconds(m.group(1)) / total_dur, 1.0)
            tag = "Copying" if "Fast" in conversion_mode else "Encoding"
            yield f"⏳ {tag}… {int(pct * 100)}%", pct

    _conv_process.wait()

    if _conv_cancel:
        time.sleep(0.3)
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except Exception:
                pass
        yield "🚫 Cancelled.", 0.0
    elif _conv_process.returncode == 0:
        yield "✅ Conversion complete!", 1.0
    else:
        yield "❌ Conversion failed. Check the input file.", 0.0

    _conv_process = None


def cancel_conversion():
    global _conv_cancel, _conv_process
    if _conv_process is not None:
        _conv_cancel = True
        _conv_process.terminate()
        return "🚫 Cancelling…"
    return "⚠️ No conversion is running."


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 3 — BURN SUBTITLES (SUBurn)
# ═══════════════════════════════════════════════════════════════════════════════

_burn_process: subprocess.Popen | None = None
_burn_cancel = False


def browse_burn_video():
    return _browse_path(
        title="Select Video",
        filetypes=[("Video Files", "*.mp4 *.mkv *.avi *.mov *.webm"), ("All Files", "*.*")]
    )


def browse_burn_srt():
    return _browse_path(
        title="Select Subtitle File",
        filetypes=[("SRT Files", "*.srt"), ("All Files", "*.*")]
    )


def browse_burn_output(video_path: str):
    initial = "output_hardsubbed.mp4"
    if video_path and os.path.isfile(video_path):
        name, _ = os.path.splitext(os.path.basename(video_path))
        initial = f"{name}_hardsubbed.mp4"
    return _browse_path(save=True, title="Save Burned Video As",
                        filetypes=[("MP4 Files", "*.mp4")], initial_file=initial)


def burn_video_changed(video_path: str):
    """Auto-fill output path when a video is picked."""
    if video_path and os.path.isfile(video_path):
        name, _ = os.path.splitext(video_path)
        return name + "_hardsubbed.mp4"
    return gr.update()


def _ensure_utf8(filepath: str, encoding_choice: str) -> str:
    """Re-encode SRT to UTF-8. Returns path to safe copy (or original if already UTF-8)."""
    with open(filepath, 'rb') as f:
        raw = f.read()

    target_enc = "utf-8"
    for key, enc in ENCODING_MAP.items():
        if key in encoding_choice:
            target_enc = enc
            break

    # Auto mode: use chardet to sniff
    if target_enc == "utf-8":
        detected = (chardet.detect(raw).get("encoding") or "utf-8").lower()
        if detected in ("utf-8", "ascii"):
            return filepath
        target_enc = detected

    try:
        text = raw.decode(target_enc)
    except (UnicodeDecodeError, LookupError):
        text = raw.decode("utf-8", errors="replace")

    new_path = filepath.replace(".srt", "_utf8burn.srt")
    with open(new_path, 'w', encoding='utf-8') as f:
        f.write(text)
    return new_path


def _format_ffmpeg_path(filepath: str) -> str:
    """Escape path for FFmpeg subtitles filter on Windows."""
    filepath = filepath.replace('\\', '/')
    filepath = filepath.replace(':', '\\:')
    return filepath


def burn_subtitles(video_path: str, srt_path: str, output_path: str,
                   encoding_choice: str, style_choice: str):
    """Burn SRT subtitles permanently into the video. Yields (status, progress 0.0–1.0)."""
    global _burn_process, _burn_cancel

    if not video_path or not os.path.isfile(video_path):
        yield "❌ Please select a valid video file.", 0.0
        return
    if not srt_path or not os.path.isfile(srt_path):
        yield "❌ Please select a valid SRT subtitle file.", 0.0
        return
    if not output_path:
        yield "❌ Please specify an output file path.", 0.0
        return
    if os.path.exists(output_path):
        yield "⚠️ Output file already exists. Delete it first or choose a different name.", 0.0
        return

    ffmpeg_exe = _get_ffmpeg()
    if not ffmpeg_exe:
        yield ("❌ FFmpeg not found. If you just ran 'winget install ffmpeg', "
               "close this terminal, open a new one, and restart the app.", 0.0)
        return

    yield "🔤 Checking subtitle encoding…", 0.0
    safe_srt = srt_path
    try:
        safe_srt = _ensure_utf8(srt_path, encoding_choice)
    except Exception as e:
        yield f"❌ Failed to process subtitle file: {e}", 0.0
        return

    yield "📏 Reading video duration…", 0.0
    total_dur  = _get_video_duration(video_path)

    style      = SUBTITLE_STYLES[style_choice]
    ffmpeg_srt = _format_ffmpeg_path(safe_srt)

    cmd = [
        ffmpeg_exe, "-y",
        "-i", video_path,
        "-vf", f"subtitles='{ffmpeg_srt}':force_style='{style}'",
        "-c:v", "libx264", "-crf", "23", "-preset", "fast",
        "-c:a", "copy",
        "-progress", "pipe:1",
        "-nostats",
        output_path
    ]

    _burn_cancel = False
    try:
        _burn_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_no_window_flags(),
        )
    except FileNotFoundError:
        yield f"❌ Could not launch FFmpeg at '{ffmpeg_exe}'. Try restarting your terminal.", 0.0
        if safe_srt != srt_path and os.path.exists(safe_srt):
            os.remove(safe_srt)
        return

    yield "🔥 Burning subtitles… Please wait.", 0.0

    for line in iter(_burn_process.stdout.readline, ''):
        if _burn_cancel:
            break
        if "out_time_us=" in line:
            try:
                us  = int(line.strip().split("=")[1])
                sec = us / 1_000_000.0
                if total_dur > 0:
                    pct = max(0.0, min(sec / total_dur, 1.0))
                    yield f"🔥 Burning… {int(pct * 100)}%", pct
            except ValueError:
                pass

    _burn_process.wait()
    retcode = _burn_process.returncode
    _burn_process = None

    if safe_srt != srt_path and os.path.exists(safe_srt):
        try:
            os.remove(safe_srt)
        except Exception:
            pass

    if _burn_cancel:
        time.sleep(0.3)
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except Exception:
                pass
        yield "🚫 Cancelled.", 0.0
    elif retcode == 0:
        yield f"✅ Done! Saved to: {output_path}", 1.0
    else:
        yield "❌ Burning failed. Check your video and subtitle files.", 0.0


def cancel_burn():
    global _burn_cancel, _burn_process
    if _burn_process is not None:
        _burn_cancel = True
        _burn_process.terminate()
        return "🚫 Cancelling…"
    return "⚠️ No burn job is running."


# ═══════════════════════════════════════════════════════════════════════════════
#  ALLOWED PATHS FOR GRADIO FILE SERVING
# ═══════════════════════════════════════════════════════════════════════════════

if platform.system() == "Windows":
    allowed_drives = ["C:\\", "D:\\", "E:\\", "F:\\", "G:\\", "Z:\\"]
else:
    allowed_drives = ["/"]


# ═══════════════════════════════════════════════════════════════════════════════
#  GRADIO UI
# ═══════════════════════════════════════════════════════════════════════════════

with gr.Blocks(theme=gr.themes.Soft(), title="🎬 Home Video Suite") as app:

    gr.Markdown("# 🎬 Home Video Suite")
    gr.Markdown(
        "Stream · Convert · Burn Subtitles — all from one place. "
        "**(Keep the terminal open!)**"
    )

    with gr.Tabs():

        # ─────────────────────────────────────────────────────────────────────
        # TAB 1 — STREAM
        # ─────────────────────────────────────────────────────────────────────
        with gr.TabItem("▶️ Stream Videos"):
            with gr.Row():
                with gr.Column(scale=2):

                    gr.Markdown("### 📁 Folder")
                    with gr.Row():
                        stream_folder_input = gr.Textbox(
                            label="Folder Path",
                            placeholder="e.g. C:\\Users\\You\\Videos",
                            scale=4,
                        )
                        stream_browse_btn = gr.Button("📂 1 - Browse", scale=1, min_width=90)

                    stream_scan_btn    = gr.Button("🔍 2 - Load Folder", variant="primary")
                    stream_scan_status = gr.Textbox(label="Scanner Status", interactive=False)

                    gr.Markdown("### 🎞️ Media Selection")
                    stream_video_dd = gr.Dropdown(label="Video", choices=[], interactive=True)

                    with gr.Row():
                        stream_sub_dd = gr.Dropdown(
                            label="💬 Subtitles", choices=["None"], value="None",
                            interactive=True, scale=3
                        )
                        stream_enc_dd = gr.Dropdown(
                            label="🔤 Language", choices=ENCODING_OPTIONS,
                            value="Hebrew (Windows-1255)", interactive=True, scale=2
                        )

                    stream_play_btn    = gr.Button("▶️ 3 - Load Video", variant="primary")
                    stream_play_status = gr.Textbox(label="Player Status", interactive=False)

                with gr.Column(scale=3):
                    stream_player = gr.Video(label="Video Player", height=540)

            stream_browse_btn.click(fn=browse_stream_folder, outputs=stream_folder_input)
            stream_scan_btn.click(fn=scan_folder, inputs=stream_folder_input,
                                  outputs=[stream_video_dd, stream_sub_dd, stream_scan_status])
            stream_play_btn.click(fn=play_video,
                                  inputs=[stream_video_dd, stream_sub_dd, stream_enc_dd],
                                  outputs=[stream_player, stream_play_status])

        # ─────────────────────────────────────────────────────────────────────
        # TAB 2 — CONVERT
        # ─────────────────────────────────────────────────────────────────────
        with gr.TabItem("🔧 Convert to MP4"):
            with gr.Column():
                gr.Markdown(
                    "Convert MKV / AVI / MOV files to a web-compatible MP4. "
                    "Required before streaming those formats in the Stream tab."
                )

                with gr.Row():
                    conv_input_box = gr.Textbox(label="📥 Input Video", scale=4,
                                               placeholder="Select or paste a file path…")
                    conv_in_btn    = gr.Button("📂 Browse", scale=1, min_width=90)

                with gr.Row():
                    conv_output_box = gr.Textbox(label="📤 Output File", scale=4,
                                                placeholder="Auto-filled when you pick an input…")
                    conv_out_btn    = gr.Button("💾 Save As", scale=1, min_width=90)

                conv_mode = gr.Dropdown(
                    label="Conversion Mode",
                    choices=[
                        "Fast Copy + Audio Convert (Recommended)",
                        "Full Re-encode (Smaller file, much slower)",
                    ],
                    value="Fast Copy + Audio Convert (Recommended)",
                )

                with gr.Row():
                    conv_start_btn  = gr.Button("🔧 Start Conversion", variant="primary")
                    conv_cancel_btn = gr.Button("🚫 Cancel", variant="stop")

                conv_progress = gr.Slider(label="Progress", minimum=0, maximum=1,
                                          value=0, interactive=False)
                conv_status   = gr.Textbox(label="Status", interactive=False)

            conv_in_btn.click(fn=browse_conv_input, outputs=conv_input_box)
            conv_input_box.change(fn=conv_input_changed, inputs=conv_input_box,
                                  outputs=conv_output_box)
            conv_out_btn.click(fn=browse_conv_output, inputs=conv_input_box,
                               outputs=conv_output_box)
            conv_start_btn.click(fn=convert_video,
                                 inputs=[conv_input_box, conv_output_box, conv_mode],
                                 outputs=[conv_status, conv_progress])
            conv_cancel_btn.click(fn=cancel_conversion, outputs=conv_status)

        # ─────────────────────────────────────────────────────────────────────
        # TAB 3 — BURN SUBTITLES
        # ─────────────────────────────────────────────────────────────────────
        with gr.TabItem("🔥 Burn Subtitles"):
            with gr.Column():
                gr.Markdown(
                    "Permanently burn (hardsub) an SRT subtitle file into a video. "
                    "The output is a new MP4 — your original file is never modified."
                )

                with gr.Row():
                    burn_video_box = gr.Textbox(label="🎬 Input Video", scale=4,
                                               placeholder="Select a video file…")
                    burn_vid_btn   = gr.Button("📂 Browse", scale=1, min_width=90)

                with gr.Row():
                    burn_srt_box = gr.Textbox(label="💬 SRT Subtitle File", scale=4,
                                             placeholder="Select an SRT file…")
                    burn_srt_btn = gr.Button("📂 Browse", scale=1, min_width=90)

                with gr.Row():
                    burn_out_box = gr.Textbox(label="📤 Output File", scale=4,
                                             placeholder="Auto-filled when you pick a video…")
                    burn_out_btn = gr.Button("💾 Save As", scale=1, min_width=90)

                with gr.Row():
                    burn_enc_dd = gr.Dropdown(
                        label="🔤 Subtitle Encoding",
                        choices=ENCODING_OPTIONS,
                        value="Hebrew (Windows-1255)",
                        scale=1,
                    )
                    burn_style_dd = gr.Dropdown(
                        label="🎨 Subtitle Style",
                        choices=list(SUBTITLE_STYLES.keys()),
                        value="Classic White (Default)",
                        scale=1,
                    )

                with gr.Row():
                    burn_start_btn  = gr.Button("🔥 Burn Subtitles", variant="primary")
                    burn_cancel_btn = gr.Button("🚫 Cancel", variant="stop")

                burn_progress = gr.Slider(label="Progress", minimum=0, maximum=1,
                                          value=0, interactive=False)
                burn_status   = gr.Textbox(label="Status", interactive=False)

            burn_vid_btn.click(fn=browse_burn_video, outputs=burn_video_box)
            burn_video_box.change(fn=burn_video_changed, inputs=burn_video_box,
                                  outputs=burn_out_box)
            burn_srt_btn.click(fn=browse_burn_srt, outputs=burn_srt_box)
            burn_out_btn.click(fn=browse_burn_output, inputs=burn_video_box,
                               outputs=burn_out_box)
            burn_start_btn.click(
                fn=burn_subtitles,
                inputs=[burn_video_box, burn_srt_box, burn_out_box,
                        burn_enc_dd, burn_style_dd],
                outputs=[burn_status, burn_progress]
            )
            burn_cancel_btn.click(fn=cancel_burn, outputs=burn_status)


# ═══════════════════════════════════════════════════════════════════════════════
#  LAUNCH
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app.launch(share=True, allowed_paths=allowed_drives)
