"""Original offline short score: procedural instruments, no recordings or services."""

import math

import numpy as np


SAMPLE_RATE = 48000
DURATION = 14.625
SEED = 104729
DESCRIPTION = (
    "Original 'Beyond the Cloud Gate' cue: modal damped-string plucks, "
    "breathy synthesized flute and warm bowed-string ensemble; no external samples"
)

# Deliberate gaps leave space for the fixed narration; the answer opens at the gate.
PLUCKS = (
    (.10, 50, .88, -.26), (.36, 57, .62, .20), (.64, 62, .70, -.12),
    (2.52, 69, .46, .23), (3.90, 66, .40, -.20),
    (5.24, 55, .66, -.25), (5.46, 62, .45, .22),
    (8.53, 57, .65, -.22), (8.76, 64, .48, .24),
    (9.26, 50, .82, -.24), (9.52, 57, .55, .24),
    (12.99, 62, .54, -.16),
)
FLUTE = (
    # A: rising question, then a breath instead of an endless arpeggio.
    (1.05, .72, 69, .62), (1.94, .40, 71, .57),
    (2.52, 1.05, 74, .74), (3.88, .74, 73, .54),
    # B: recognisable rhythm, wider rise and a tonic landing under the title.
    (5.34, .73, 69, .73), (6.23, .40, 71, .65),
    (6.81, 1.12, 78, .85), (8.09, .68, 76, .72),
    (9.24, 1.39, 74, .82),
    # Quiet coda responds downwards, leaving the final word unobscured.
    (11.15, .48, 71, .47), (11.87, .62, 69, .44),
    (13.10, .72, 74, .56),
)
CHORDS = (
    (.0, 5.25, (47, 54, 62, 66), .56, "Bm7: departure"),
    (4.65, 4.10, (43, 55, 62, 69), .69, "Gadd9: cloud gate"),
    (7.95, 1.85, (45, 57, 64, 67), .64, "A7: threshold"),
    (9.18, 5.10, (50, 57, 62, 66), .88, "D: title resolution"),
)


def smooth(values):
    """C1-continuous envelope, including exact zero/one endpoints."""
    clipped = np.clip(values, 0, 1)
    return clipped * clipped * (3 - 2 * clipped)


def frequency(midi):
    """Convert an equal-tempered MIDI pitch to Hz."""
    return 440 * 2 ** ((midi - 69) / 12)


def filtered_noise(count, rng, cutoff):
    """Band-limit deterministic excitation/breath without a third-party sample."""
    noise = rng.normal(0, 1, count)
    spectrum = np.fft.rfft(noise)
    frequencies = np.fft.rfftfreq(count, 1 / SAMPLE_RATE)
    spectrum *= 1 / (1 + (frequencies / cutoff) ** 4)
    result = np.fft.irfft(spectrum, n=count)
    return result / max(float(np.std(result)), 1e-12)


def plucked_string(midi, velocity):
    """Modal string displacement with pluck-position nulls and faster upper decay."""
    time = np.arange(round(3.8 * SAMPLE_RATE)) / SAMPLE_RATE
    fundamental = frequency(midi)
    result = np.zeros(len(time))
    for mode in range(1, 25):
        partial = fundamental * mode * math.sqrt(1 + .000035 * mode * mode)
        position = math.sin(math.pi * mode * .21)
        # Body resonances around 240/680 Hz round out the otherwise dry string.
        body = 1 + .35 * math.exp(-((partial - 240) / 180) ** 2)
        body += .22 * math.exp(-((partial - 680) / 280) ** 2)
        weight = position * body / mode ** (1.40 + .22 * (1 - velocity))
        decay = .75 + .17 * mode + .025 * mode * mode
        result += weight * np.sin(math.tau * partial * time) * np.exp(-decay * time)
    return result * velocity * smooth(time / .004) * smooth((3.8 - time) / .24)


def flute(midi, duration, velocity, rng):
    """Soft air-column tone with delayed vibrato, breath and shaped articulation."""
    length = duration + .16
    time = np.arange(round(length * SAMPLE_RATE)) / SAMPLE_RATE
    vibrato = .0028 * np.sin(math.tau * 4.7 * time) * smooth((time - .16) / .35)
    scoop = -.008 * np.exp(-time / .045)
    phase = math.tau * np.cumsum(frequency(midi) * (1 + vibrato + scoop)) / SAMPLE_RATE
    tone = (np.sin(phase) + .23 * np.sin(2 * phase + .2)
            + .095 * np.sin(3 * phase) + .025 * np.sin(4 * phase + .4))
    breath = filtered_noise(len(time), rng, 2200)
    air = .026 * breath * (.7 + .3 * np.sin(phase))
    envelope = smooth(time / .085) * smooth((length - time) / .20)
    envelope *= .85 + .15 * np.sin(math.pi * np.minimum(time / duration, 1))
    return (tone + air) * envelope * velocity * .28


def bowed_strings(notes, duration, velocity, rng):
    """Four gently detuned bowed players per note, with a slow attack/release."""
    time = np.arange(round(duration * SAMPLE_RATE)) / SAMPLE_RATE
    stereo = np.zeros((len(time), 2))
    envelope = smooth(time / .80) * smooth((duration - time) / .85)
    envelope *= .84 + .16 * np.sin(math.pi * time / duration)
    for note_index, midi in enumerate(notes):
        for player, cents in enumerate((-7, -2, 3, 8)):
            phase_offset = rng.uniform(0, math.tau)
            vibrato = .0018 * np.sin(math.tau * (4.4 + .19 * player) * time + phase_offset)
            hz = frequency(midi) * 2 ** (cents / 1200)
            phase = math.tau * np.cumsum(hz * (1 + vibrato)) / SAMPLE_RATE
            tone = np.zeros(len(time))
            for harmonic in range(1, 10):
                tone += np.sin(harmonic * phase + phase_offset) / harmonic ** 1.65
            pan = (-.38, -.14, .14, .38)[player]
            weight = (.95, .62, .57, .48)[note_index] * velocity * .043
            stereo += pan_mono(tone * envelope * weight, pan)
    return stereo


def pan_mono(samples, pan):
    """Equal-power panning without phase inversion or Haas-delay mono loss."""
    angle = (pan + 1) * math.pi / 4
    return samples[:, None] * np.array([math.cos(angle), math.sin(angle)])


def place(destination, samples, start):
    """Add a note without changing the fixed film sample count."""
    offset = round(start * SAMPLE_RATE)
    length = min(len(samples), len(destination) - offset)
    destination[offset:offset + length] += samples[:length]


def room(samples, rng):
    """Quiet, band-limited diffuse reflections; no tempo-synced repeating delay."""
    count = len(samples)
    spectrum = np.fft.rfft(samples, axis=0)
    hz = np.fft.rfftfreq(count, 1 / SAMPLE_RATE)
    spectrum *= (1 / (1 + (hz / 3100) ** 4))[:, None]
    softened = np.fft.irfft(spectrum, n=count, axis=0)
    wet = np.zeros_like(samples)
    for delay in np.linspace(.037, 1.18, 43) + rng.uniform(-.009, .009, 43):
        offset = round(delay * SAMPLE_RATE)
        # Positive crossfeed keeps reflections useful in mono.
        reflected = .72 * softened[:-offset] + .28 * softened[:-offset, ::-1]
        wet[offset:] += reflected * (.040 * math.exp(-delay / .44))
    return samples + wet


def analyze(stems, score):
    """Measure continuity, bandwidth and mono compatibility of the actual cue."""
    spectrum = np.fft.rfft(score, axis=0)
    power = np.sum(np.abs(spectrum) ** 2, axis=1)
    hz = np.fft.rfftfreq(len(score), 1 / SAMPLE_RATE)
    stereo_energy = float(np.mean(score ** 2))
    mono_energy = float(np.mean(np.mean(score, axis=1) ** 2))
    return {
        "sample_frames": len(score), "channels": 2, "sample_rate": SAMPLE_RATE,
        "finite": bool(np.isfinite(score).all()),
        "peak": float(np.max(np.abs(score))),
        "rms": math.sqrt(stereo_energy),
        "max_adjacent_step": float(np.max(np.abs(np.diff(score, axis=0)))),
        "stereo_correlation": float(np.corrcoef(score.T)[0, 1]),
        "mono_energy_ratio": mono_energy / stereo_energy,
        "energy_above_6khz_ratio": float(np.sum(power[hz > 6000]) / np.sum(power)),
        "stem_rms": {name: float(np.sqrt(np.mean(stem ** 2)))
                     for name, stem in stems.items()},
        "section_rms": {
            name: float(np.sqrt(np.mean(score[round(start * SAMPLE_RATE):
                                                round(end * SAMPLE_RATE)] ** 2)))
            for name, start, end in (("departure", 0, 4.65), ("gate", 4.65, 9.18),
                                     ("title", 9.18, 13.1), ("tail", 13.1, DURATION))
        },
    }


def compose(duration=DURATION):
    """Return independent stereo stems, their sum and reproducible score evidence."""
    if not math.isfinite(duration) or duration != DURATION:
        raise ValueError("Flowing cue requires the approved 14.625-second narration timeline")
    rng = np.random.default_rng(SEED)
    count = round(duration * SAMPLE_RATE)
    stems = {name: np.zeros((count, 2)) for name in ("plucks", "lead", "strings")}
    events = []
    for start, midi, velocity, pan in PLUCKS:
        place(stems["plucks"], pan_mono(plucked_string(midi, velocity) * .25, pan), start)
        events.append({"instrument": "plucks", "start": start, "midi": midi,
                       "velocity": velocity, "pan": pan, "duration": 3.8})
    for start, length, midi, velocity in FLUTE:
        place(stems["lead"], pan_mono(flute(midi, length, velocity, rng), .06), start)
        events.append({"instrument": "lead", "start": start, "midi": midi,
                       "velocity": velocity, "duration": length})
    for start, length, notes, velocity, name in CHORDS:
        place(stems["strings"], bowed_strings(notes, length, velocity, rng), start)
        events.append({"instrument": "strings", "start": start, "duration": length,
                       "midi": list(notes), "velocity": velocity, "harmony": name})
    time = np.arange(count) / SAMPLE_RATE
    fade = smooth(time / .075) * smooth((duration - .25 - time) / 1.02)
    for name in stems:
        stems[name] = room(stems[name], rng) * fade[:, None]
    score = sum(stems.values())
    # A shared gain retains the composed balance and exact stem reconstruction.
    gain = min(.34 / np.max(np.abs(score)), .092 / np.sqrt(np.mean(score ** 2)))
    for name in stems:
        stems[name] *= gain
    score = sum(stems.values())
    metrics = analyze(stems, score)
    if (not metrics["finite"] or metrics["peak"] > .341
            or metrics["max_adjacent_step"] > .08 or metrics["mono_energy_ratio"] < .8):
        raise ValueError(f"Flowing score failed technical validation: {metrics}")
    evidence = {
        "title": "Beyond the Cloud Gate", "description": DESCRIPTION,
        "credit": "Original composition and procedural synthesis for Mortal Ascension",
        "source": "New note events and physical/modal/additive synthesis in compose_flowing_score.py",
        "external_recordings_or_samples": [], "traditional_live_instruments": False,
        "seed": SEED, "duration": duration,
        "sections": [
            {"start": 0, "end": 4.65, "name": "Departure: plucked pickup and flute question"},
            {"start": 4.65, "end": 9.18, "name": "Gate: varied rising answer, expanding strings"},
            {"start": 9.18, "end": 13.10, "name": "Title: dominant to D resolution, descending coda"},
            {"start": 13.10, "end": duration, "name": "Tonic echo and diffuse fading tail"},
        ],
        "events": sorted(events, key=lambda event: event["start"]),
        "metrics": metrics,
        "review": "Numerical validation only; subjective musical quality requires audition",
    }
    return stems, score, evidence
