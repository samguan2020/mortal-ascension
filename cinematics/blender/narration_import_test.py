"""Network-free checks for bounded narration import and legacy compatibility.

    python -B -m unittest discover -s cinematics\\blender -p narration_import_test.py -v
"""

from array import array
import contextlib
import io
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import narrate_first_shot as narration


def takes_for(durations, channels=1):
    return [array("h", [4096]) * (round(seconds * narration.SAMPLE_RATE) * channels)
            for seconds in durations]


def legacy_report():
    takes = takes_for((4.5, 3, 3))
    segments, frames = narration.schedule_takes(takes)
    return {
        "schema": 1, "fps": narration.FPS, "duration": frames / narration.FPS,
        "frames": frames, "segments": segments, "end_card_start": 9.2,
        "assets": {"narrated_mix.wav": "original"},
    }


class NarrationImportTests(unittest.TestCase):
    def test_narration_split_preserves_every_stereo_sample(self):
        samples = array("h", range(20))
        cuts = (3 / narration.SAMPLE_RATE, 7 / narration.SAMPLE_RATE)

        takes, boundaries = narration.split_recording(samples, cuts)

        self.assertEqual(boundaries, [0, 3, 7, 10])
        self.assertEqual(sum(takes, array("h")), samples)
        self.assertEqual([len(take) for take in takes], [6, 8, 6])

    def test_narration_invalid_cuts_raise_without_partial_slices(self):
        samples = array("h", range(20))
        rate = narration.SAMPLE_RATE
        cases = (
            (), (1,), (1, 2, 3), (float("nan"), 1), (1, float("inf")),
            (-1, 1), (0, 1), (2 / rate, 1 / rate), (1 / rate, 1 / rate),
            (1 / rate, 10 / rate), (1 / rate, 11 / rate),
            (.1 / rate, 1 / rate), (1.1 / rate, 1.2 / rate),
        )
        for cuts in cases:
            with self.subTest(cuts=cuts), self.assertRaises(ValueError):
                narration.split_recording(samples, cuts)
        for invalid in (array("h"), array("h", [1, 2, 3])):
            with self.subTest(samples=invalid), self.assertRaises(ValueError):
                narration.split_recording(invalid, (1 / rate, 2 / rate))

    def test_narration_default_schedule_preserves_windows_timing(self):
        report = legacy_report()

        self.assertEqual([segment["start"] for segment in report["segments"]],
                         [.75, 5.7, 10.2])
        self.assertEqual(report["frames"], 353)
        self.assertEqual(report["segments"][0]["wav"], "narrated_sentence_1.wav")
        self.assertEqual(narration.variant_output("narrated"), narration.OUTPUT)

    def test_narration_import_schedule_preserves_duration_and_aligns_title(self):
        takes = takes_for((4.46, 2.78, 2.893333333333333), 2)

        segments, frames = narration.schedule_takes(takes, "clipchamp", 2)

        self.assertEqual([segment["start"] for segment in segments], [.75, 5.66, 10.2])
        self.assertEqual(sum(segment["sample_count"] for segment in segments), 486400)
        self.assertEqual(frames, 351)
        self.assertAlmostEqual(segments[-1]["end"], 13.093333333333333)
        self.assertGreaterEqual(frames / narration.FPS - segments[-1]["end"], 1.5)
        longer, _ = narration.schedule_takes(takes_for((6, 4, 2), 2), "clipchamp", 2)
        self.assertGreaterEqual(longer[-1]["start"], longer[1]["end"] + 1.05)

    def test_narration_long_or_incomplete_takes_reject_instead_of_truncating(self):
        with self.assertRaisesRegex(ValueError, "20s offline bound"):
            narration.schedule_takes(takes_for((8, 8, 5), 2), "clipchamp", 2)
        with self.assertRaisesRegex(ValueError, "three mono or stereo"):
            narration.schedule_takes(takes_for((2, 2)))
        with self.assertRaisesRegex(ValueError, "complete, nonempty"):
            narration.schedule_takes([array("h", [1])] * 3, "clipchamp", 2)

    def test_narration_external_options_never_fall_back_to_windows(self):
        source = Path("approved.m4a")
        invalid = (
            ("clipchamp", True, None, None),
            ("clipchamp", True, source, None),
            ("clipchamp", True, source, (float("nan"), 7.24)),
            ("clipchamp", True, source, (7.24, 4.46)),
            ("narrated", True, source, (4.46, 7.24)),
            ("clipchamp", False, source, (4.46, 7.24)),
            ("unapproved", True, source, (4.46, 7.24)),
        )
        for args in invalid:
            with self.subTest(args=args), self.assertRaises(ValueError):
                narration.validate_options(*args)
        narration.validate_options("clipchamp", True, source, (4.46, 7.24))
        narration.validate_options("clipchamp", False, None, None)
        narration.validate_options("narrated", True, None, None)

    def test_narration_invalid_files_fail_without_speech_synthesis(self):
        with patch.object(Path, "is_file", return_value=False), \
                patch.object(narration, "ffmpeg") as ffmpeg, \
                patch.object(narration, "prepare_voice") as windows:
            with self.assertRaisesRegex(ValueError, "existing local"):
                narration.prepare_recording(Path("staging"), Path("missing.m4a"), (4.46, 7.24))
            ffmpeg.assert_not_called()
            windows.assert_not_called()
        with patch.object(Path, "is_file", return_value=True):
            with self.assertRaisesRegex(ValueError, "existing local"):
                narration.prepare_recording(Path("staging"), Path("playlist.m3u8"), (4.46, 7.24))

    def test_narration_windows_voice_configuration_and_mono_takes_are_preserved(self):
        selected = {"voice": narration.VOICE, "culture": "zh-CN", "rate": -1, "synthetic": True}
        result = subprocess.CompletedProcess([], 0, json.dumps(selected), "")
        with patch.object(Path, "write_text"), \
                patch.object(narration, "run", return_value=result) as run, \
                patch.object(narration, "read_pcm", side_effect=takes_for((4.5, 3, 3))) as read, \
                contextlib.redirect_stdout(io.StringIO()):
            segments, takes, frames = narration.prepare_voice(Path("staging"))
        self.assertEqual(len(takes), 3)
        self.assertEqual(frames, 353)
        self.assertEqual([segment["start"] for segment in segments], [.75, 5.7, 10.2])
        self.assertEqual(run.call_count, 3)
        self.assertTrue(all(call.args[0][0] == "pwsh.exe" for call in run.call_args_list))
        self.assertTrue(all(call.args[1] == 1 for call in read.call_args_list))

    def test_narration_assembly_selects_only_prepared_variant_without_original(self):
        report = legacy_report()
        default = narration.assembly_command(report, narration.OUTPUT)
        report["variant"] = "clipchamp"
        report["end_card_start"] = 11.25

        imported = narration.assembly_command(report, narration.variant_output("clipchamp"))

        self.assertIn(str(narration.RENDERS / "narrated_mix.wav"), default)
        self.assertIn(str(narration.RENDERS / "clipchamp_mix.wav"), imported)
        self.assertNotIn(str(narration.RENDERS / "narrated_mix.wav"), imported)
        self.assertIn("fade=t=in:st=11.25:d=0.8", narration.video_filters(report))
        self.assertFalse(any("Downloads" in argument for argument in imported))
        self.assertIn("-n", imported)

    def test_narration_mixer_preserves_stereo_and_legacy_mono_routing(self):
        for channels, take in ((2, array("h", [1000, -2000, 3000, -4000])),
                               (1, array("h", [1000, 3000]))):
            segments = [{"start_sample": 1, "sample_count": 2,
                         "start": 1 / narration.SAMPLE_RATE,
                         "end": 3 / narration.SAMPLE_RATE}]
            count = narration.SAMPLE_RATE // narration.FPS * 2
            stems = {}
            with self.subTest(channels=channels), \
                    patch.object(narration, "synthesize_music",
                                 return_value=(array("d", [.0001]) * count, [])), \
                    patch.object(narration, "write_pcm",
                                 side_effect=lambda path, samples: stems.update({path.name: samples})):
                narration.create_mix(Path("staging"), segments, [take], 1, "clipchamp", channels)
            voice = stems["clipchamp_voice.wav"]
            gain = 10 ** (segments[0]["voice_gain_db"] / 20)
            expected = take if channels == 2 else [1000, 1000, 3000, 3000]
            for mixed, original in zip(voice[2:6], expected):
                self.assertAlmostEqual(mixed, original / 32768 * gain)
            self.assertEqual(list(voice[:2]), [0, 0])
            self.assertTrue(all(value == 0 for value in voice[6:]))
            self.assertGreaterEqual(segments[0]["voice_over_music_db"], 14)

    def test_narration_existing_films_are_never_overwritten(self):
        with patch.object(Path, "exists", return_value=True), \
                patch.object(Path, "read_text") as read, \
                patch.object(narration, "run") as run:
            for variant in ("narrated", "clipchamp"):
                with self.subTest(variant=variant), self.assertRaises(FileExistsError):
                    narration.assemble(variant)
            read.assert_not_called()
            run.assert_not_called()

    def test_narration_variant_and_hash_mismatch_stop_before_assembly(self):
        report = legacy_report()
        with patch.object(Path, "exists", return_value=False), \
                patch.object(Path, "read_text", return_value=json.dumps(report)), \
                patch.object(narration, "run") as run:
            with self.assertRaisesRegex(ValueError, "incompatible"):
                narration.assemble("clipchamp")
            run.assert_not_called()
        with patch.object(Path, "exists", return_value=False), \
                patch.object(Path, "read_text", return_value=json.dumps(report)), \
                patch.object(narration, "digest", return_value="changed"), \
                patch.object(narration, "run") as run:
            with self.assertRaisesRegex(ValueError, "Prepared asset changed"):
                narration.assemble()
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
