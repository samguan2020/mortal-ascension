"""Offline synthetic or imported narration and original score; no network or game imports.

    python -B cinematics\\blender\\narrate_first_shot.py --prepare
    python -B cinematics\\blender\\narrate_first_shot.py --assemble
    python -B cinematics\\blender\\narrate_first_shot.py --prepare --variant clipchamp \
--narration-audio "C:\\Users\\xingu\\Downloads\\Video Project 4.m4a" --cuts 4.46 7.24
    python -B cinematics\\blender\\narrate_first_shot.py --assemble --variant clipchamp

Preparation never needs the source video. Assembly consumes the verified assets
without resynthesizing them or needing the imported original, and refuses to
overwrite an existing film. Imported cuts are explicit, not ASR-derived.
"""

import argparse
from array import array
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import wave

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

sys.dont_write_bytecode = True
from package_first_shot import FPS, GAME_TITLE, GAME_TITLE_EN, SAMPLE_RATE, SIZE, TAGLINE


HERE = Path(__file__).resolve().parent
RENDERS = HERE / "renders"
SOURCE = RENDERS / "bronze_jade_costume.mp4"
OUTPUT = RENDERS / "mortal_ascension_narrated.mp4"
VOICE = "Microsoft Kangkang"
SENTENCES = (
    "\u4e00\u4ecb\u51e1\u4eba\uff0c\u80cc\u8d77\u884c\u56ca\uff0c\u8e0f\u4e0a\u95ee\u9053\u4e4b\u8def\u3002",
    "\u4e91\u6d77\u5c3d\u5934\uff0c\u4ed9\u95e8\u521d\u73b0\u3002",
    TAGLINE + "\u3002",
)
TARGET_LUFS = -18
TRUE_PEAK = -2
NORMALIZATION_PEAK = -2.5
BLACK_FRAMES = 6


def run(command):
    """Run bounded local tools and expose their diagnostic output on failure."""
    result = subprocess.run(command, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=600)
    if result.returncode:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {subprocess.list2cmdline(command)}\n"
            f"{result.stdout}\n{result.stderr}"
        )
    return result


def ffmpeg(*arguments):
    return run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-nostdin",
                "-loglevel", "info", *map(str, arguments)])


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_pcm(path, channels):
    with wave.open(str(path), "rb") as audio:
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(),
                audio.getcomptype()) != (channels, 2, SAMPLE_RATE, "NONE"):
            raise ValueError(f"Expected 48 kHz, PCM16, {channels} channels: {path}")
        count = audio.getnframes()
        values = array("h", audio.readframes(count))
    if sys.byteorder != "little":
        values.byteswap()
    if len(values) != count * channels or not values:
        raise ValueError(f"Incomplete or empty PCM: {path}")
    peak = max(abs(value) for value in values) / 32768
    if not 0.001 < peak < 0.999:
        raise ValueError(f"Silent or clipped PCM ({peak=:.5f}): {path}")
    return values


def write_pcm(path, values, channels=2):
    peak = max(abs(value) for value in values)
    if not 0.001 < peak < 0.99:
        raise ValueError(f"Invalid synthesized PCM headroom ({peak=:.5f}): {path}")
    samples = array("h", (round(value * 32767) for value in values))
    if sys.byteorder != "little":
        samples.byteswap()
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(2)
        audio.setframerate(SAMPLE_RATE)
        audio.writeframes(samples.tobytes())


def prepare_voice(folder):
    takes = []
    for index, text in enumerate(SENTENCES, 1):
        text_path = folder / f"narrated_sentence_{index}.txt"
        path = folder / f"narrated_sentence_{index}.wav"
        text_path.write_text(text, encoding="utf-8")
        result = run([
            "pwsh.exe", "-NoProfile", "-NonInteractive", "-File",
            str(HERE / "synthesize_narration.ps1"),
            "-TextPath", str(text_path), "-OutputPath", str(path),
        ])
        selected = json.loads(result.stdout)
        if selected != {"voice": VOICE, "culture": "zh-CN", "rate": -1, "synthetic": True}:
            raise ValueError(f"Unexpected speech configuration: {selected}")
        samples = read_pcm(path, 1)
        length = len(samples) / SAMPLE_RATE
        if not 1 < length < 10:
            raise ValueError(f"Unexpected sentence duration: {length:.3f}s")
        takes.append(samples)
    segments, frames = schedule_takes(takes)
    for index, segment in enumerate(segments, 1):
        print(f"VOICE_PASS: {VOICE}, sentence {index}, {segment['duration']:.3f}s, "
              f"timeline {segment['start']:.3f}-{segment['end']:.3f}s", flush=True)
    return segments, takes, frames


def schedule_takes(takes, prefix="narrated", channels=1):
    if len(takes) != len(SENTENCES) or channels not in (1, 2):
        raise ValueError("Expected three mono or stereo narration takes")
    segments = []
    start = 0.75
    for index, (text, samples) in enumerate(zip(SENTENCES, takes), 1):
        if not samples or len(samples) % channels:
            raise ValueError("Narration must contain complete, nonempty PCM frames")
        length = len(samples) / channels / SAMPLE_RATE
        if index == 3:
            title_ready = (max(10, segments[1]["end"] + .85)
                           if prefix == "clipchamp" else 10)
            start = max(start, title_ready + .2)
        start_sample = round(start * SAMPLE_RATE)
        start = start_sample / SAMPLE_RATE
        segment = {
            "text": text, "wav": f"{prefix}_sentence_{index}.wav",
            "sample_count": len(samples) // channels,
            "start_sample": start_sample, "start": start,
            "end": start + length, "duration": length,
        }
        segments.append(segment)
        start = segment["end"] + 0.45
    frames = math.ceil(max(12, segments[-1]["end"] + 1.5) * FPS)
    duration = frames / FPS
    if duration > 20:
        raise ValueError(f"Narration requires {duration:.3f}s; exceeds the 20s offline bound")
    return segments, frames


def split_recording(samples, cuts):
    if len(cuts) != 2 or not all(math.isfinite(cut) for cut in cuts):
        raise ValueError("Exactly two finite narration cuts are required")
    if not samples or len(samples) % 2:
        raise ValueError("Expected nonempty stereo narration")
    count = len(samples) // 2
    if not 0 < cuts[0] < cuts[1] < count / SAMPLE_RATE:
        raise ValueError("Cuts must be increasing and strictly inside the decoded audio")
    boundaries = [0, *(round(cut * SAMPLE_RATE) for cut in cuts), count]
    if any(end <= start for start, end in zip(boundaries, boundaries[1:])):
        raise ValueError("Cuts must leave at least one PCM frame in every sentence")
    takes = [samples[start * 2:end * 2]
             for start, end in zip(boundaries, boundaries[1:])]
    return takes, boundaries


def prepare_recording(folder, source, cuts):
    if not source.is_file() or source.suffix.lower() not in (".m4a", ".wav"):
        raise ValueError(f"Narration must be an existing local M4A or WAV file: {source}")
    if not 0 < source.stat().st_size <= 64 * 1024 * 1024:
        raise ValueError("Narration input must be nonempty and at most 64 MiB")
    original = digest(source)
    archived = folder / f"clipchamp_input{source.suffix.lower()}"
    shutil.copyfile(source, archived)
    if digest(archived) != original:
        raise RuntimeError("Narration changed while being copied")
    decoded = folder / "clipchamp_input_decoded.wav"
    result = ffmpeg("-n", "-protocol_whitelist", "file,pipe", "-i", archived,
                    "-map", "0:a:0", "-vn", "-ar", SAMPLE_RATE, "-ac", 2,
                    "-c:a", "pcm_s16le", decoded)
    with wave.open(str(decoded), "rb") as audio:
        if not 0 < audio.getnframes() <= 20 * SAMPLE_RATE:
            raise ValueError("Decoded narration must be nonempty and no longer than 20 seconds")
    samples = read_pcm(decoded, 2)
    takes, boundaries = split_recording(samples, cuts)
    segments, frames = schedule_takes(takes, "clipchamp", 2)
    for index, (segment, take) in enumerate(zip(segments, takes), 1):
        path = folder / segment["wav"]
        stored = array("h", take)
        if sys.byteorder != "little":
            stored.byteswap()
        with wave.open(str(path), "wb") as audio:
            audio.setnchannels(2)
            audio.setsampwidth(2)
            audio.setframerate(SAMPLE_RATE)
            audio.writeframes(stored.tobytes())
        read_pcm(path, 2)
        (folder / f"clipchamp_sentence_{index}.txt").write_text(
            segment["text"], encoding="utf-8")
        segment["source_start_sample"] = boundaries[index - 1]
        segment["source_end_sample"] = boundaries[index]
        print(f"IMPORT_PASS: sentence {index}, {segment['duration']:.6f}s, "
              f"timeline {segment['start']:.6f}-{segment['end']:.6f}s", flush=True)
    if digest(source) != original:
        raise RuntimeError("Original narration changed during preparation")
    encoders = re.findall(r"^\s*encoder\s*:\s*(.+)$", result.stderr, re.MULTILINE)
    provenance = {
        "original_path": str(source.resolve()), "original_sha256": original,
        "original_bytes": archived.stat().st_size, "archived_source": archived.name,
        "encoder_metadata": encoders[0].strip() if encoders else None,
        "decoded_wav": decoded.name, "decoded_sha256": digest(decoded),
        "decoded_format": "pcm_s16le", "channels": 2, "sample_rate": SAMPLE_RATE,
        "sample_count": len(samples) // 2, "duration": len(samples) / 2 / SAMPLE_RATE,
        "cuts_seconds": list(cuts), "boundaries_samples": boundaries,
        "timing_basis": "Explicit supplied cuts; text and sentence boundaries not "
                        "verified by listening or ASR; voice preset unverified",
    }
    return segments, takes, frames, provenance


def smooth(value):
    value = min(1.0, max(0.0, value))
    return value * value * (3 - 2 * value)


def synthesize_music(duration):
    """An original D-major pentatonic phrase, modal plucks and a breathy drone."""
    count = round(duration * SAMPLE_RATE)
    music = array("d", [0.0]) * (count * 2)
    # D E F# A B: two answering phrases and a descending tonic resolution.
    notes = (62, 66, 69, 71, 69, 66, 64, 69, 74, 71, 69, 66, 64, 62)
    events = []
    phrase_end = duration - 2.0
    for index, midi in enumerate(notes):
        start = 0.2 + index * (phrase_end - 0.2) / (len(notes) - 1)
        frequency = 440 * 2 ** ((midi - 69) / 12)
        pan = (-0.24, 0.18, -0.08, 0.28)[index % 4]
        events.append({"start": start, "midi": midi, "frequency": frequency, "pan": pan})
        for sample in range(round(start * SAMPLE_RATE),
                            min(count, round((start + 3.2) * SAMPLE_RATE))):
            elapsed = sample / SAMPLE_RATE - start
            if elapsed < 0:
                continue
            pluck = sum(
                weight * math.exp(-elapsed * decay)
                * math.sin(math.tau * frequency * harmonic * elapsed)
                for harmonic, weight, decay in ((1, 1, 1.8), (2, .32, 3.1), (3, .12, 4.8))
            ) * smooth(elapsed / .012) * .10
            music[2 * sample] += pluck * (1 - pan)
            music[2 * sample + 1] += pluck * (1 + pan)
    for sample in range(count):
        time = sample / SAMPLE_RATE
        breath = .8 + .2 * math.sin(math.tau * .17 * time)
        pad = sum(
            math.sin(math.tau * frequency * time
                     + .10 * math.sin(math.tau * .21 * time)) * weight
            for frequency, weight in ((146.8324, .027), (220, .019), (293.6648, .012))
        ) * breath * smooth(time / 1.8)
        air = .003 * math.sin(math.tau * 587.3296 * time) * breath
        music[2 * sample] += pad + air
        music[2 * sample + 1] += pad - air
        fade = smooth(time / .45) * smooth((duration - BLACK_FRAMES / FPS - time) / 1.1)
        music[2 * sample] *= fade
        music[2 * sample + 1] *= fade
    return music, events


def create_mix(folder, segments, takes, frames, prefix="narrated", channels=1):
    duration = frames / FPS
    voice = array("d", [0.0]) * (frames * (SAMPLE_RATE // FPS) * 2)
    for segment, take in zip(segments, takes):
        rms = math.sqrt(sum((sample / 32768) ** 2 for sample in take) / len(take))
        peak = max(abs(sample) for sample in take) / 32768
        gain = min(.12 / rms, .60 / peak)
        segment["voice_gain_db"] = 20 * math.log10(gain)
        offset = segment["start_sample"] * 2
        for index in range(segment["sample_count"]):
            for channel in range(2):
                sample = take[index * channels + (channel if channels == 2 else 0)]
                voice[offset + index * 2 + channel] = sample / 32768 * gain
    music, events = synthesize_music(duration)
    ducked = array("d", music)
    for index in range(len(voice) // 2):
        time = index / SAMPLE_RATE
        activity = max(
            smooth((time - (segment["start"] - .18)) / .18)
            * smooth((segment["end"] + .40 - time) / .40)
            for segment in segments
        )
        gain = 1 - .80 * activity
        ducked[index * 2] *= gain
        ducked[index * 2 + 1] *= gain
    for segment in segments:
        start = segment["start_sample"] * 2
        end = start + segment["sample_count"] * 2
        voice_energy = sum(value * value for value in voice[start:end])
        music_energy = sum(value * value for value in ducked[start:end])
        ratio = 10 * math.log10(voice_energy / music_energy)
        if ratio < 14:
            raise ValueError(f"Insufficient dialogue/music RMS margin: {ratio:.2f} dB")
        segment["voice_over_music_db"] = round(ratio, 2)
    mix = array("d", (v + m for v, m in zip(voice, ducked)))
    for name, samples in (("voice", voice), ("music", music),
                          ("music_ducked", ducked), ("mix_raw", mix)):
        write_pcm(folder / f"{prefix}_{name}.wav", samples)
    return events


def measure_audio(path):
    result = ffmpeg("-i", path, "-af",
                    f"loudnorm=I={TARGET_LUFS}:TP={NORMALIZATION_PEAK}:LRA=11:print_format=json",
                    "-f", "null", "-")
    position = result.stderr.rfind("{")
    if position < 0:
        raise ValueError(f"No loudness measurement returned:\n{result.stderr}")
    measured = json.JSONDecoder().raw_decode(result.stderr[position:])[0]
    values = {key: float(measured[key]) for key in
              ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")}
    if not all(math.isfinite(value) for value in values.values()):
        raise ValueError(f"Invalid loudness measurement: {measured}")
    return values


def normalize_mix(folder, frames, prefix="narrated"):
    """Use measured two-pass loudnorm, as in the existing teaser packager."""
    raw = folder / f"{prefix}_mix_raw.wav"
    measured = measure_audio(raw)
    filter_text = (
        f"loudnorm=I={TARGET_LUFS}:TP={NORMALIZATION_PEAK}:LRA=11:linear=true"
        f":measured_I={measured['input_i']}:measured_TP={measured['input_tp']}"
        f":measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}"
        f":offset={measured['target_offset']}"
    )
    output = folder / f"{prefix}_mix.wav"
    ffmpeg("-i", raw, "-af", filter_text, "-ar", SAMPLE_RATE, "-ac", 2,
           "-c:a", "pcm_s16le", output)
    samples = read_pcm(output, 2)
    expected = frames * (SAMPLE_RATE // FPS) * 2
    if len(samples) != expected:
        raise ValueError(f"Normalized audio sample count {len(samples)} != {expected}")
    if max(abs(value) for value in samples[-(SAMPLE_RATE // 8) * 2:]) > 2:
        raise ValueError("Final audio must end in silence")
    final = measure_audio(output)
    validate_loudness(final)
    # Also check the actual delivery codec, without retaining a lossy stem.
    aac = folder / f"{prefix}_mix_check.m4a"
    try:
        ffmpeg("-i", output, "-c:a", "aac", "-b:a", "192k", "-ar", SAMPLE_RATE,
               "-ac", 2, aac)
        encoded = measure_audio(aac)
        validate_loudness(encoded)
    finally:
        aac.unlink(missing_ok=True)
    print(f"AUDIO_PASS: PCM {final['input_i']:.2f} LUFS / {final['input_tp']:.2f} dBTP; "
          f"AAC {encoded['input_i']:.2f} LUFS / {encoded['input_tp']:.2f} dBTP", flush=True)
    return {"raw": measured, "pcm": final, "aac_check": encoded}


def validate_loudness(measured):
    if abs(measured["input_i"] - TARGET_LUFS) > .5 or measured["input_tp"] > TRUE_PEAK:
        raise ValueError(f"Mix misses -18 +/-0.5 LUFS / -2 dBTP ceiling: {measured}")


def srt_time(seconds):
    milliseconds = round(seconds * 1000)
    hours, milliseconds = divmod(milliseconds, 3600000)
    minutes, milliseconds = divmod(milliseconds, 60000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


def create_graphics(folder, segments, prefix="narrated"):
    fonts = Path(os.environ["WINDIR"]) / "Fonts"
    chinese = fonts / "msyh.ttc"
    serif = fonts / "georgia.ttf"
    for path in (chinese, serif):
        if not path.is_file():
            raise FileNotFoundError(f"Required local font missing: {path}")
    cream = (233, 225, 202, 255)
    bronze = (183, 149, 90, 255)
    for name, end_card in (("intro", False), ("title", True)):
        image = Image.new("RGBA", SIZE, (6, 15, 15, 240) if end_card else (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        x, y = (960, 430) if end_card else (300, 130)
        draw.text((x, y), GAME_TITLE, anchor="mm", fill=cream,
                  font=ImageFont.truetype(str(chinese), 132 if end_card else 64),
                  stroke_width=1, stroke_fill=(17, 28, 27, 240))
        draw.text((x, y + (130 if end_card else 72)), GAME_TITLE_EN,
                  anchor="mm", fill=cream,
                  font=ImageFont.truetype(str(serif), 54 if end_card else 32),
                  stroke_width=1, stroke_fill=(17, 28, 27, 240))
        if end_card:
            draw.line((755, 616, 1165, 616), fill=bronze, width=2)
            draw.text((960, 679), TAGLINE, anchor="mm", fill=cream,
                      font=ImageFont.truetype(str(chinese), 40))
        image.save(folder / f"{prefix}_{name}.png")
    captions = []
    for index, segment in enumerate(segments, 1):
        image = Image.new("RGBA", SIZE)
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype(str(chinese), 44)
        box = draw.textbbox((960, 958), segment["text"], anchor="mm", font=font)
        if box[0] < 80 or box[2] > SIZE[0] - 80:
            raise ValueError("Subtitle exceeds 1080p title-safe bounds")
        draw.rounded_rectangle((box[0] - 28, box[1] - 16, box[2] + 28, box[3] + 16),
                               radius=12, fill=(5, 10, 12, 190))
        draw.text((960, 958), segment["text"], anchor="mm", font=font, fill=cream,
                  stroke_width=1, stroke_fill=(0, 0, 0, 255))
        image.save(folder / f"{prefix}_caption_{index}.png")
        captions.append(f"{index}\n{srt_time(segment['start'])} --> "
                        f"{srt_time(segment['end'])}\n{segment['text']}\n")
    (folder / f"{prefix}_captions.srt").write_text("\n".join(captions), encoding="utf-8")


def video_filters(report):
    duration = report["duration"]
    black_start = duration - BLACK_FRAMES / FPS
    filters = [
        f"[0:v]tpad=stop_mode=clone:stop_duration={duration - 10},"
        "setpts=PTS-STARTPTS,fade=t=in:st=0:d=0.6[base]",
        "[1:v]format=rgba,fade=t=in:st=0.4:d=0.5:alpha=1,"
        "fade=t=out:st=2.6:d=0.6:alpha=1[intro]",
        f"[2:v]format=rgba,fade=t=in:st={report['end_card_start']}:d=0.8:alpha=1[title]",
        "[base][intro]overlay=0:0:shortest=1[branded]",
        "[branded][title]overlay=0:0:shortest=1[caption0]",
    ]
    for index, segment in enumerate(report["segments"], 1):
        filters.append(
            f"[caption{index - 1}][{index + 2}:v]overlay=0:0:shortest=1:"
            f"enable='gte(t,{segment['start']})*lt(t,{segment['end']})'[caption{index}]"
        )
    filters.append(
        f"[caption3]fade=t=out:st={black_start - .75}:d=0.75,"
        f"trim=end_frame={report['frames']},format=yuv420p[video]"
    )
    return ";".join(filters)


def assembly_command(report, destination):
    prefix = report.get("variant", "narrated")
    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-nostdin", "-n",
               "-i", str(SOURCE)]
    for name in ("intro", "title", "caption_1", "caption_2", "caption_3"):
        command.extend(["-loop", "1", "-framerate", str(FPS), "-i",
                        str(RENDERS / f"{prefix}_{name}.png")])
    command.extend([
        "-i", str(RENDERS / f"{prefix}_mix.wav"), "-filter_complex", video_filters(report),
        "-map", "[video]", "-map", "6:a:0", "-t", str(report["duration"]),
        "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", str(SAMPLE_RATE),
        "-ac", "2", "-movflags", "+faststart", str(destination),
    ])
    return command


def variant_output(variant):
    if variant not in ("narrated", "clipchamp"):
        raise ValueError(f"Unknown narration variant: {variant}")
    return OUTPUT if variant == "narrated" else RENDERS / "mortal_ascension_clipchamp.mp4"


def validate_options(variant, preparing, narration_audio, cuts):
    variant_output(variant)
    if preparing and variant == "clipchamp":
        if narration_audio is None or cuts is None:
            raise ValueError("Clipchamp preparation requires --narration-audio and --cuts")
        if len(cuts) != 2 or not all(math.isfinite(cut) for cut in cuts):
            raise ValueError("Exactly two finite narration cuts are required")
        if not 0 < cuts[0] < cuts[1]:
            raise ValueError("Narration cuts must be positive and increasing")
    elif narration_audio is not None or cuts is not None:
        raise ValueError("Audio input and cuts are only valid for --prepare --variant clipchamp")


def prepare(variant="narrated", narration_audio=None, cuts=None):
    validate_options(variant, True, narration_audio, cuts)
    output = variant_output(variant)
    RENDERS.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"{variant}_prepare_", dir=RENDERS) as staging:
        folder = Path(staging)
        provenance = None
        if variant == "narrated":
            segments, takes, frames = prepare_voice(folder)
        else:
            segments, takes, frames, provenance = prepare_recording(folder, narration_audio, cuts)
        events = create_mix(folder, segments, takes, frames, variant,
                            2 if provenance else 1)
        loudness = normalize_mix(folder, frames, variant)
        create_graphics(folder, segments, variant)
        title_start = max(9.2, segments[1]["end"] + .05) if provenance else 9.2
        assemble_args = ["python", "-B", str(HERE / "narrate_first_shot.py"), "--assemble"]
        if variant != "narrated":
            assemble_args.extend(["--variant", variant])
        report = {
            "schema": 1, "variant": variant,
            "voice": "External narration (preset unverified)" if provenance else VOICE,
            "synthetic_voice": None if provenance else True,
            "speech_rate": None if provenance else -1,
            "score": "Original synthesized D-major pentatonic plucks and warm airy drone",
            "source": str(SOURCE), "output": str(output), "fps": FPS,
            "frames": frames, "duration": frames / FPS, "black_frames": BLACK_FRAMES,
            "end_card_start": title_start, "end_card_fully_visible": title_start + .8,
            "segments": segments, "music_notes": events, "loudness": loudness,
            "assembly_command": subprocess.list2cmdline(assemble_args),
            "verification": "Numerical audio/codec checks only; not a listening review",
            "assets": {path.name: digest(path) for path in sorted(folder.iterdir())},
        }
        if provenance:
            report["narration_source"] = provenance
        report["ffmpeg_command"] = subprocess.list2cmdline(assembly_command(report, output))
        timing = folder / f"{variant}_timing.json"
        timing.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        # Publish the manifest last. Assembly rejects incomplete/mixed generations.
        for path in sorted(folder.iterdir()):
            if path != timing:
                path.replace(RENDERS / path.name)
        timing.replace(RENDERS / timing.name)
    print(f"PREPARE_PASS: {report['duration']:.6f}s, {frames} frames at {FPS} fps; "
          f"end hold {report['duration'] - segments[-1]['end']:.3f}s", flush=True)
    print(f"SOURCE (not required for prepare): {SOURCE}\nOUTPUT: {output}\n"
          f"ASSEMBLE: {report['assembly_command']}\nREPORT: {RENDERS / timing.name}",
          flush=True)


def validate_video(path, duration, frames, audio):
    reader = imageio_ffmpeg.read_frames(str(path))
    try:
        metadata = next(reader)
    finally:
        reader.close()
    if (metadata["size"] != SIZE or abs(metadata["fps"] - FPS) > .001
            or abs(metadata["duration"] - duration) > .06
            or (metadata.get("audio_codec") is not None) != audio):
        raise ValueError(f"Unexpected video metadata: {metadata}")
    if audio and (metadata["codec"] != "h264" or metadata["audio_codec"] != "aac"
                  or metadata["pix_fmt"].split("(")[0].strip() != "yuv420p"):
        raise ValueError(f"Expected H.264 yuv420p / AAC delivery codecs: {metadata}")
    count, _ = imageio_ffmpeg.count_frames_and_secs(str(path))
    if count != frames:
        raise ValueError(f"Expected {frames} frames, found {count}: {path}")
    return metadata


def assemble(variant="narrated"):
    output = variant_output(variant)
    if output.exists():
        raise FileExistsError(f"Preserving existing narrated film; archive it before retrying: {output}")
    timing = RENDERS / f"{variant}_timing.json"
    report = json.loads(timing.read_text(encoding="utf-8"))
    if (report["schema"] != 1 or report["fps"] != FPS
            or report.get("variant", "narrated") != variant
            or not 12 <= report["duration"] <= 20
            or report["frames"] / FPS != report["duration"]
            or [segment["text"] for segment in report["segments"]] != list(SENTENCES)):
        raise ValueError("Prepared timing is incompatible; run --prepare again")
    for name, expected in report["assets"].items():
        if Path(name).name != name or not name.startswith(f"{variant}_"):
            raise ValueError(f"Invalid prepared asset name: {name}")
        if digest(RENDERS / name) != expected:
            raise ValueError(f"Prepared asset changed: {name}; run --prepare again")
    if not SOURCE.is_file():
        raise FileNotFoundError(f"Render FirstShot_Costume.blend to this silent source first: {SOURCE}")
    original = digest(SOURCE)
    validate_video(SOURCE, 10, 240, False)
    with tempfile.TemporaryDirectory(prefix=f"{variant}_assemble_", dir=RENDERS) as staging:
        temporary = Path(staging) / f"{variant}_film.mp4"
        run(assembly_command(report, temporary))
        validate_video(temporary, report["duration"], report["frames"], True)
        ffmpeg("-v", "error", "-xerror", "-i", temporary,
               "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-")
        validate_loudness(measure_audio(temporary))
        black = ffmpeg("-i", temporary, "-an", "-vf",
                       f"select=gte(n\\,{report['frames'] - BLACK_FRAMES}),"
                       "signalstats,metadata=mode=print", "-f", "null", "-")
        for channel, expected in (("Y", 16), ("U", 128), ("V", 128)):
            for bound in ("MIN", "MAX"):
                key = channel + bound
                values = [float(value) for value in re.findall(
                    rf"lavfi.signalstats.{key}=([\d.]+)", black.stderr)]
                if values != [expected] * BLACK_FRAMES:
                    raise ValueError(f"Expected six neutral black frames; {key} was {values}")
        if digest(SOURCE) != original:
            raise RuntimeError("Source changed during assembly; output was not published")
        # On Windows rename is atomic and fails if another process published first.
        temporary.rename(output)
    print(f"ASSEMBLY_PASS: {output}, {report['duration']:.6f}s, {report['frames']} frames",
          flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--assemble", action="store_true")
    parser.add_argument("--variant", choices=("narrated", "clipchamp"), default="narrated")
    parser.add_argument("--narration-audio", type=Path,
                        help="Local M4A/WAV, required for Clipchamp preparation")
    parser.add_argument("--cuts", type=float, nargs=2, metavar=("FIRST", "SECOND"),
                        help="Explicit sentence boundaries in decoded source seconds")
    args = parser.parse_args()
    validate_options(args.variant, args.prepare, args.narration_audio, args.cuts)
    if args.prepare:
        prepare(args.variant, args.narration_audio, args.cuts)
    else:
        assemble(args.variant)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.TimeoutExpired) as error:
        print(f"NARRATED_ERROR: {error}", file=sys.stderr, flush=True)
        sys.exit(1)
