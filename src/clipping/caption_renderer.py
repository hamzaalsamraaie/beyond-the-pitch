"""
Animated caption renderer — word-by-word pop-on style.

Generates an ASS (Advanced SubStation Alpha) subtitle file from word-level
timestamps, then uses FFmpeg's 'ass' filter to burn captions into the video.

Caption style:
  - 2–4 words per caption event (natural phrase breaks)
  - Bold white text, 86px, centered in the bottom-third safe zone
  - Black outline + drop shadow for legibility on any background
  - Gold accent for the first caption of a scene (hook highlight)
  - Channel branding "BEYOND THE PITCH" in a small top bar

ASS timecode format: H:MM:SS.cs  (centiseconds, not milliseconds)
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from src.clipping.models import WordTimestamp
from src.core.logger import get_logger

logger = get_logger(__name__)

# ── Layout ─────────────────────────────────────────────────────────────────────
_PLAY_RES_X = 1080
_PLAY_RES_Y = 1920
_MARGIN_V_CAPTION = 160   # px from bottom for captions
_MARGIN_V_BRAND = 60      # px from top for branding

# ── Colours (ASS AABBGGRR — alpha=00 means opaque) ──────────────────────────
_WHITE = "&H00FFFFFF"
_GOLD = "&H004CA8C9"       # #C9A84C → BGR: 4C A8 C9
_BLACK_OUTLINE = "&H00000000"
_SHADOW_COLOUR = "&H80000000"  # semi-transparent black

# ── Words per caption event ───────────────────────────────────────────────────
_MIN_WORDS = 2
_MAX_WORDS = 4
_MIN_DURATION = 0.25   # seconds


# ── ASS header ────────────────────────────────────────────────────────────────

_ASS_HEADER = f"""\
[Script Info]
Title: Beyond The Pitch
ScriptType: v4.00+
WrapStyle: 1
PlayResX: {_PLAY_RES_X}
PlayResY: {_PLAY_RES_Y}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: BTP_Caption,Arial,86,{_WHITE},{_WHITE},{_BLACK_OUTLINE},{_SHADOW_COLOUR},-1,0,0,0,100,100,0,0,1,4,2,2,20,20,{_MARGIN_V_CAPTION},1
Style: BTP_Hook,Arial,110,{_GOLD},{_GOLD},{_BLACK_OUTLINE},{_SHADOW_COLOUR},-1,0,0,0,100,100,0,0,1,5,3,2,20,20,{_MARGIN_V_CAPTION + 60},1
Style: BTP_Brand,Arial,38,{_GOLD},{_GOLD},{_BLACK_OUTLINE},{_SHADOW_COLOUR},-1,0,0,0,100,100,0,0,1,2,1,8,20,20,{_MARGIN_V_BRAND},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _ass_time(seconds: float) -> str:
    """Convert fractional seconds to ASS timecode H:MM:SS.cs"""
    cs = int(round(seconds * 100))
    h = cs // 360000
    cs %= 360000
    m = cs // 6000
    cs %= 6000
    s = cs // 100
    cs %= 100
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _group_words(words: list[WordTimestamp]) -> list[tuple[float, float, str]]:
    """
    Group consecutive words into caption chunks of _MIN_WORDS–_MAX_WORDS words.
    Returns list of (start_sec, end_sec, text).
    """
    if not words:
        return []

    groups: list[tuple[float, float, str]] = []
    buf: list[WordTimestamp] = []

    for w in words:
        buf.append(w)
        # Natural break points: punctuation or max words reached
        is_break = (
            len(buf) >= _MAX_WORDS
            or w.word.rstrip().endswith((".", "!", "?", ",", ";", ":"))
        )
        if is_break and len(buf) >= _MIN_WORDS:
            start = buf[0].start
            end = buf[-1].end
            if end - start < _MIN_DURATION:
                end = start + _MIN_DURATION
            text = " ".join(bw.word.strip() for bw in buf)
            groups.append((start, end, text))
            buf = []

    # Flush remaining words
    if buf:
        start = buf[0].start
        end = buf[-1].end
        if end - start < _MIN_DURATION:
            end = start + _MIN_DURATION
        text = " ".join(bw.word.strip() for bw in buf)
        groups.append((start, end, text))

    return groups


def generate_ass(
    words: list[WordTimestamp],
    clip_start: float,
    clip_end: float,
    channel_name: str = "BEYOND THE PITCH",
    hook_duration: float = 5.0,
) -> str:
    """
    Generate a full ASS subtitle file content string.

    words: word-level timestamps (absolute times in source video)
    clip_start: start time of the clip in the source (seconds)
    clip_end: end time of the clip (seconds)
    """
    lines: list[str] = [_ASS_HEADER]

    # Adjust words to clip-relative timestamps
    relative_words: list[WordTimestamp] = []
    for w in words:
        rel_start = max(0.0, w.start - clip_start)
        rel_end = max(rel_start + 0.05, w.end - clip_start)
        if rel_start < (clip_end - clip_start):
            relative_words.append(WordTimestamp(
                start=round(rel_start, 3),
                end=round(rel_end, 3),
                word=w.word,
            ))

    groups = _group_words(relative_words)

    for i, (start, end, text) in enumerate(groups):
        style = "BTP_Hook" if start < hook_duration else "BTP_Caption"
        t_start = _ass_time(start)
        t_end = _ass_time(end)
        # Escape braces and backslashes for ASS
        safe_text = text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
        lines.append(
            f"Dialogue: 0,{t_start},{t_end},{style},,0,0,0,,{safe_text}"
        )

    # Channel branding: entire clip duration at top
    clip_dur = clip_end - clip_start
    t_zero = _ass_time(0.0)
    t_total = _ass_time(clip_dur)
    lines.append(
        f"Dialogue: 0,{t_zero},{t_total},BTP_Brand,,0,0,0,,{channel_name}"
    )

    return "\n".join(lines) + "\n"


def write_ass_file(
    words: list[WordTimestamp],
    clip_start: float,
    clip_end: float,
    output_path: Path,
    **kwargs,
) -> Path:
    """Write the ASS file to disk and return the path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = generate_ass(words, clip_start, clip_end, **kwargs)
    output_path.write_text(content, encoding="utf-8")
    logger.info("ass_file_written", path=output_path.name, events=content.count("Dialogue:"))
    return output_path


# ── PIL fallback helpers ──────────────────────────────────────────────────────

def _parse_ass_time(t: str) -> float:
    """Parse ASS timecode H:MM:SS.cs to seconds."""
    h, m, s_cs = t.strip().split(":")
    s_parts = s_cs.split(".")
    return int(h) * 3600 + int(m) * 60 + int(s_parts[0]) + (int(s_parts[1]) if len(s_parts) > 1 else 0) / 100.0


def _parse_ass_events(ass_path: Path) -> list[dict]:
    """Return list of {start, end, style, text} dicts from an ASS file."""
    events = []
    for line in ass_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("Dialogue:"):
            continue
        parts = line.split(",", 9)
        if len(parts) < 10:
            continue
        try:
            start = _parse_ass_time(parts[1])
            end = _parse_ass_time(parts[2])
        except Exception:
            continue
        style = parts[3].strip()
        text = re.sub(r"\{[^}]*\}", "", parts[9]).strip()
        events.append({"start": start, "end": end, "style": style, "text": text})
    return events


def _load_pil_fonts() -> dict:
    """Load PIL fonts for each caption style, falling back to default."""
    from PIL import ImageFont
    candidates = [
        "/Library/Fonts/Arial Bold.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    bold = next((p for p in candidates if Path(p).exists()), None)

    def _f(size: int):
        return ImageFont.truetype(bold, size) if bold else ImageFont.load_default()

    return {"BTP_Caption": _f(86), "BTP_Hook": _f(110), "BTP_Brand": _f(38)}


def _draw_caption_pil(draw, text: str, style: str, width: int, height: int, fonts: dict) -> None:
    """Render one caption line centered with an outline."""
    font = fonts.get(style, fonts["BTP_Caption"])
    if style == "BTP_Brand":
        y = _MARGIN_V_BRAND
        fill: tuple = (201, 168, 76)
    elif style == "BTP_Hook":
        y = height - _MARGIN_V_CAPTION - 60 - 110
        fill = (201, 168, 76)
    else:
        y = height - _MARGIN_V_CAPTION - 86
        fill = (255, 255, 255)

    bbox = draw.textbbox((0, 0), text, font=font)
    x = (width - (bbox[2] - bbox[0])) // 2
    for dx, dy in [(-3, -3), (0, -3), (3, -3), (-3, 0), (3, 0), (-3, 3), (0, 3), (3, 3)]:
        draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0))
    draw.text((x, y), text, font=font, fill=fill)


def _burn_captions_pil(video_path: Path, ass_path: Path, output_path: Path) -> Path:
    """
    PIL-based caption burner — used when FFmpeg is built without libass.
    Pipes raw frames: FFmpeg → Python/PIL → FFmpeg.
    """
    ff = shutil.which("ffmpeg")
    ffprobe_bin = shutil.which("ffprobe")
    if not ff or not ffprobe_bin:
        raise EnvironmentError("ffmpeg/ffprobe not found")

    events = _parse_ass_events(ass_path)
    if not events:
        shutil.copy2(str(video_path), str(output_path))
        return output_path

    probe = subprocess.run(
        [ffprobe_bin, "-v", "quiet", "-print_format", "json", "-show_streams", str(video_path)],
        capture_output=True, text=True,
    )
    streams = json.loads(probe.stdout)["streams"]
    vs = next(s for s in streams if s["codec_type"] == "video")
    w, h = int(vs["width"]), int(vs["height"])
    fps_n, fps_d = vs["r_frame_rate"].split("/")
    fps = int(fps_n) / int(fps_d)

    from PIL import Image, ImageDraw
    fonts = _load_pil_fonts()
    frame_size = w * h * 3

    extract = [ff, "-v", "quiet", "-i", str(video_path),
               "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"]
    encode = [
        ff, "-y", "-v", "quiet",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "pipe:0",
        "-i", str(video_path),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart",
        str(output_path),
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("burn_captions_pil_start", frames=int(fps * float(vs.get("duration", 0))))
    with (subprocess.Popen(extract, stdout=subprocess.PIPE) as reader,
          subprocess.Popen(encode, stdin=subprocess.PIPE) as writer):
        n = 0
        while True:
            raw = reader.stdout.read(frame_size)
            if len(raw) < frame_size:
                break
            t = n / fps
            frame = Image.frombytes("RGB", (w, h), raw)
            active = [ev for ev in events if ev["start"] <= t < ev["end"]]
            if active:
                draw = ImageDraw.Draw(frame)
                for ev in active:
                    _draw_caption_pil(draw, ev["text"], ev["style"], w, h, fonts)
            try:
                writer.stdin.write(frame.tobytes())
            except BrokenPipeError:
                break
            n += 1
        try:
            writer.stdin.close()
        except Exception:
            pass
        writer.wait()

    logger.info("burn_captions_pil_done", frames=n, output=output_path.name)
    return output_path


# ── Burn captions into video ──────────────────────────────────────────────────

def burn_captions(
    video_path: Path,
    ass_path: Path,
    output_path: Path,
) -> Path:
    """
    Burn ASS captions into the video.

    Tries FFmpeg's 'ass' filter first (requires libass in the FFmpeg build).
    Falls back to a PIL frame-pipe burner when libass is unavailable.
    Returns output_path.
    """
    ff = shutil.which("ffmpeg")
    if not ff:
        raise EnvironmentError("ffmpeg not found on PATH")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Escape chars with meaning in FFmpeg filter-graph syntax (\ : ')
    p = str(ass_path.resolve())
    p = p.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

    cmd = [
        ff, "-y",
        "-i", str(video_path),
        "-vf", f"ass={p}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart",
        str(output_path),
    ]

    logger.info("burn_captions_start", input=video_path.name, ass=ass_path.name)
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        logger.info("burn_captions_done", output=output_path.name)
        return output_path

    # If the error is a missing filter (libass not compiled in), use PIL fallback.
    stderr_lower = result.stderr.lower()
    if "no such filter" in stderr_lower or "no option name" in stderr_lower:
        logger.info("burn_captions_libass_missing_using_pil")
        return _burn_captions_pil(video_path, ass_path, output_path)

    raise RuntimeError(f"Caption burn failed:\n{result.stderr[-600:]}")
