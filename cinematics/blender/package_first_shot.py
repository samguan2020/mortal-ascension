"""Package the approved HD shot with titles and locally synthesized ambience.

Run with Python, Pillow and imageio-ffmpeg installed:
    python cinematics\\blender\\package_first_shot.py

Requires Windows Georgia and Microsoft YaHei fonts. Only raster title images
are generated; no font files or external music are copied or distributed.
Outputs are isolated under renders/; Blender scenes and the input stay intact.
"""

from array import array
import hashlib
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import wave

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
RENDERS = HERE / "renders"
SOURCE = RENDERS / "bronze_jade_final.mp4"
OUTPUT = RENDERS / "bronze_jade_teaser.mp4"
SIZE = (1920, 1080)
FPS = 24
DURATION = 12
SAMPLE_RATE = 48000
GAME_TITLE = "\u51e1\u9aa8\u767b\u4ed9"
GAME_TITLE_EN = "Mortal Ascension"
TAGLINE = "\u51e1\u9aa8\u5165\u9053\uff0c\u4e00\u5ff5\u767b\u4ed9"


def validate_source():
    """Reject unexpected framing, timing or existing audio before packaging."""
    if not SOURCE.is_file():
        raise FileNotFoundError(f"Render the approved HD shot first: {SOURCE}")
    frames = imageio_ffmpeg.read_frames(str(SOURCE))
    try:
        metadata = next(frames)
    finally:
        frames.close()
    if metadata["size"] != SIZE or abs(metadata["fps"] - FPS) > 0.01:
        raise ValueError(f"Expected a 1920x1080, 24 fps source: {metadata}")
    if abs(metadata["duration"] - 10) > 0.05:
        raise ValueError(f"Expected a ten-second source: {metadata}")
    if metadata.get("audio_codec") is not None:
        raise ValueError("The source already has audio; refusing to replace it")


def create_titles():
    """Rasterize the approved game name and tagline using installed fonts."""
    fonts = Path(os.environ["WINDIR"]) / "Fonts"
    serif = fonts / "georgia.ttf"
    chinese = fonts / "msyh.ttc"
    for path in (serif, chinese):
        if not path.is_file():
            raise FileNotFoundError(f"Required local title font missing: {path}")
    cream = (233, 225, 202, 255)
    bronze = (183, 149, 90, 255)
    shadow = (17, 28, 27, 240)
    intro = Image.new("RGBA", SIZE)
    draw = ImageDraw.Draw(intro)
    draw.text((115, 104), GAME_TITLE, font=ImageFont.truetype(str(chinese), 64),
              fill=cream, stroke_width=1, stroke_fill=shadow)
    draw.text((118, 189), GAME_TITLE_EN, font=ImageFont.truetype(str(serif), 34),
              fill=cream, stroke_width=1, stroke_fill=shadow)
    draw.line((118, 240, 375, 240), fill=bronze, width=2)
    draw.text((118, 260), TAGLINE, font=ImageFont.truetype(str(chinese), 27),
              fill=cream, stroke_width=1, stroke_fill=shadow)
    intro_path = RENDERS / "teaser_intro.png"
    intro.save(intro_path)

    outro = Image.new("RGBA", SIZE, (6, 15, 15, 240))
    draw = ImageDraw.Draw(outro)
    draw.text((960, 430), GAME_TITLE, anchor="mm",
              font=ImageFont.truetype(str(chinese), 132), fill=cream)
    draw.text((960, 560), GAME_TITLE_EN, anchor="mm",
              font=ImageFont.truetype(str(serif), 54), fill=cream)
    draw.line((755, 616, 1165, 616), fill=bronze, width=2)
    draw.text((960, 679), TAGLINE, anchor="mm",
              font=ImageFont.truetype(str(chinese), 40), fill=cream)
    draw.text((960, 905), "CINEMATIC STUDY", anchor="mm",
              font=ImageFont.truetype(str(serif), 22), fill=bronze)
    outro_path = RENDERS / "teaser_outro.png"
    outro.save(outro_path)
    return intro_path, outro_path


def synthesize_ambience():
    """Generate stereo wind and two soft inharmonic chimes, without samples."""
    rng = random.Random(42)
    samples = array("h")
    low_left = low_right = 0.0
    peak = 0.0
    modes = ((1, 1), (2.76, 0.26), (5.40, 0.08), (8.93, 0.025))
    events = ((1.25, 196.0, -0.16), (7.40, 293.6648, 0.16))
    for index in range(DURATION * SAMPLE_RATE):
        time = index / SAMPLE_RATE
        gust = 0.72 + 0.22 * math.sin(math.tau * 0.12 * time)
        low_left = 0.95 * low_left + 0.05 * rng.uniform(-1, 1)
        low_right = 0.95 * low_right + 0.05 * rng.uniform(-1, 1)
        left = low_left * 0.11 * gust
        right = low_right * 0.11 * gust
        for start, frequency, pan in events:
            elapsed = time - start
            if elapsed < 0:
                continue
            attack = min(elapsed / 0.06, 1)
            chime = sum(
                weight * math.exp(-elapsed * (0.48 + ratio * 0.10))
                * math.sin(math.tau * frequency * ratio * elapsed)
                for ratio, weight in modes
            ) * attack * 0.10
            left += chime * (1 - pan)
            right += chime * (1 + pan)
        fade = min(1, time / 0.8, (DURATION - time) / 1.1)
        left *= fade
        right *= fade
        peak = max(peak, abs(left), abs(right))
        if peak >= 0.95:
            raise RuntimeError("Generated ambience exceeds safe PCM headroom")
        samples.extend((round(left * 32767), round(right * 32767)))
    if peak < 0.01:
        raise RuntimeError("Generated ambience is unexpectedly silent")
    if sys.byteorder != "little":
        samples.byteswap()
    path = RENDERS / "teaser_ambience.wav"
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(2)
        audio.setsampwidth(2)
        audio.setframerate(SAMPLE_RATE)
        audio.writeframes(samples.tobytes())
    print(f"AUDIO_SOURCE_PASS: {DURATION}s stereo PCM, peak {20 * math.log10(peak):.2f} dBFS", flush=True)
    return path


def normalized_audio_filter(audio):
    """Measure the faded mix first so short clips reach the loudness target."""
    preparation = "highpass=f=40,afade=t=in:st=0:d=0.5,afade=t=out:st=10.9:d=1.1"
    meter = subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-nostdin", "-i", str(audio),
         "-af", preparation + ",loudnorm=I=-23:TP=-2:LRA=11:print_format=json",
         "-f", "null", "-"],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
    )
    if meter.returncode:
        raise RuntimeError(f"Audio loudness measurement failed:\n{meter.stderr}")
    measured = json.JSONDecoder().raw_decode(meter.stderr[meter.stderr.rfind("{"):])[0]
    values = {key: float(measured[key]) for key in
              ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")}
    if not all(math.isfinite(value) for value in values.values()):
        raise RuntimeError(f"Invalid loudness measurement: {measured}")
    return (
        preparation + ",loudnorm=I=-23:TP=-2:LRA=11:linear=true"
        f":measured_I={values['input_i']}:measured_TP={values['input_tp']}"
        f":measured_LRA={values['input_lra']}:measured_thresh={values['input_thresh']}"
        f":offset={values['target_offset']}"
    )


def package(intro, outro, audio):
    """Encode a twelve-second branded edit, publishing only on success."""
    temporary = RENDERS / "bronze_jade_teaser.partial.mp4"
    filters = (
        "[0:v]tpad=stop_mode=clone:stop_duration=2,setpts=PTS-STARTPTS,"
        "fade=t=in:st=0:d=0.6[base];"
        "[1:v]format=rgba,fade=t=in:st=0.4:d=0.5:alpha=1,"
        "fade=t=out:st=2.6:d=0.6:alpha=1[intro];"
        "[2:v]format=rgba,fade=t=in:st=9.2:d=0.8:alpha=1[outro];"
        "[base][intro]overlay=0:0:shortest=1[branded];"
        "[branded][outro]overlay=0:0:shortest=1,"
        "fade=t=out:st=11.1:d=0.7,format=yuv420p[video];"
        f"[3:a]{normalized_audio_filter(audio)}[audio]"
    )
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "warning", "-nostdin", "-y",
        "-i", str(SOURCE),
        "-loop", "1", "-framerate", str(FPS), "-i", str(intro),
        "-loop", "1", "-framerate", str(FPS), "-i", str(outro),
        "-i", str(audio),
        "-filter_complex", filters, "-map", "[video]", "-map", "[audio]",
        "-t", str(DURATION), "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k", "-ar", str(SAMPLE_RATE), "-ac", "2",
        "-movflags", "+faststart", str(temporary),
    ]
    subprocess.run(command, check=True)
    temporary.replace(OUTPUT)
    print("TEASER_COMPLETE", OUTPUT, flush=True)


def main():
    validate_source()
    original_hash = hashlib.sha256(SOURCE.read_bytes()).digest()
    intro, outro = create_titles()
    audio = synthesize_ambience()
    package(intro, outro, audio)
    if hashlib.sha256(SOURCE.read_bytes()).digest() != original_hash:
        raise RuntimeError("Approved source video changed during packaging")
    print("SOURCE_PRESERVED", flush=True)


if __name__ == "__main__":
    main()
