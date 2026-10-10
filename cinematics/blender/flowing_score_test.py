"""Offline score, approved archive and isolated packaging regression checks.

    python -B -m unittest discover -s cinematics\\blender -p "*_test.py" -v
"""

from array import array
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

import compose_flowing_score as composer
import narrate_first_shot as narration


def approved_fixture():
    counts = (214080, 133440, 138880)
    takes = [array("h", [4096, 4096]) * count for count in counts]
    segments, frames = narration.schedule_takes(takes, "clipchamp", 2)
    return takes, {
        "segments": segments, "frames": frames,
        "narration_source": {"decoded_sha256": "decoded", "cuts_seconds": [4.46, 7.24]},
    }


class FlowingScoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stems, cls.score, cls.evidence = composer.compose()

    def test_score_format_headroom_and_stem_reconstruction(self):
        self.assertEqual(self.score.shape, (702000, 2))
        self.assertEqual(set(self.stems), {"lead", "plucks", "strings"})
        np.testing.assert_array_equal(self.score, sum(self.stems.values()))
        for samples in (*self.stems.values(), self.score):
            self.assertTrue(np.isfinite(samples).all())
            self.assertGreater(float(np.max(np.abs(samples))), .001)
            self.assertLess(float(np.max(np.abs(samples))), .99)
            np.testing.assert_array_equal(samples[0], [0, 0])
            np.testing.assert_array_equal(samples[-12000:], np.zeros((12000, 2)))
        self.assertLessEqual(self.evidence["metrics"]["peak"], .341)

    def test_score_seeded_render_is_exactly_repeatable(self):
        stems, score, evidence = composer.compose()
        np.testing.assert_array_equal(score, self.score)
        for name in stems:
            np.testing.assert_array_equal(stems[name], self.stems[name])
        self.assertEqual(evidence, self.evidence)

    def test_score_continuity_width_bandwidth_and_clear_lead(self):
        metrics = self.evidence["metrics"]
        self.assertLess(metrics["max_adjacent_step"], .04)
        self.assertGreater(metrics["mono_energy_ratio"], .90)
        self.assertGreater(metrics["stereo_correlation"], .8)
        self.assertLess(metrics["stereo_correlation"], .99)
        self.assertLess(metrics["energy_above_6khz_ratio"], .001)
        self.assertGreater(metrics["stem_rms"]["lead"], metrics["stem_rms"]["strings"])
        self.assertGreater(metrics["stem_rms"]["strings"], .01)

    def test_score_phrases_rests_harmony_and_title_resolution(self):
        first = [event for event in self.evidence["events"]
                 if event["instrument"] == "lead" and event["start"] < 4.65]
        answer = [event for event in self.evidence["events"]
                  if event["instrument"] == "lead" and 4.65 < event["start"] < 10]
        self.assertEqual([note["midi"] for note in first[:2]],
                         [note["midi"] for note in answer[:2]])
        self.assertNotEqual([note["midi"] for note in first],
                            [note["midi"] for note in answer])
        self.assertGreater(answer[0]["start"] - first[-1]["start"] - first[-1]["duration"], .5)
        self.assertEqual(answer[-1]["midi"], 74)
        self.assertLess(abs(answer[-1]["start"] - 9.2), .05)
        chords = [event for event in self.evidence["events"] if event["instrument"] == "strings"]
        self.assertEqual(len({tuple(event["midi"]) for event in chords}), 4)
        self.assertTrue(chords[-1]["harmony"].startswith("D:"))
        for left, right in zip(chords, chords[1:]):
            self.assertGreater(left["start"] + left["duration"], right["start"])
        self.assertGreater(self.evidence["metrics"]["section_rms"]["gate"],
                           self.evidence["metrics"]["section_rms"]["departure"])
        self.assertEqual(self.evidence["external_recordings_or_samples"], [])
        self.assertFalse(self.evidence["traditional_live_instruments"])

    def test_score_envelope_has_smooth_endpoints_and_rejects_retiming(self):
        epsilon = 1e-5
        np.testing.assert_array_equal(composer.smooth(np.array([-1, 0, 1, 2])), [0, 0, 1, 1])
        self.assertLess(float(composer.smooth(epsilon)) / epsilon, .0001)
        self.assertLess(float(1 - composer.smooth(1 - epsilon)) / epsilon, .0001)
        for duration in (0, 10, 14.6, float("nan"), float("inf")):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                composer.compose(duration)


class FlowingPackagingTests(unittest.TestCase):
    def test_variant_routes_source_output_assets_without_downloads(self):
        takes, previous = approved_fixture()
        report = dict(previous, variant="flowing", duration=14.625, end_card_start=9.2)
        command = narration.assembly_command(report, narration.variant_output("flowing"))
        self.assertIn(str(narration.RENDERS / "bronze_jade_flowing.mp4"), command)
        self.assertIn(str(narration.RENDERS / "flowing_mix.wav"), command)
        self.assertIn(str(narration.RENDERS / "flowing_caption_1.png"), command)
        self.assertEqual(command[-1], str(narration.RENDERS / "mortal_ascension_flowing.mp4"))
        self.assertNotIn(str(narration.SOURCE), command)
        self.assertFalse(any("Downloads" in argument for argument in command))
        self.assertIn("-n", command)
        for variant in ("narrated", "clipchamp"):
            self.assertEqual(narration.variant_source(variant), narration.SOURCE)
        for preparing in (True, False):
            narration.validate_options("flowing", preparing, None, None)
            with self.assertRaises(ValueError):
                narration.validate_options("flowing", preparing, Path("other.wav"), (4.46, 7.24))

    def test_completed_flowing_film_blocks_assemble_and_prepare_before_writes(self):
        with patch.object(Path, "exists", return_value=True), \
                patch.object(Path, "mkdir") as mkdir, \
                patch.object(Path, "read_text") as read, \
                patch.object(narration, "run") as run:
            for operation in (narration.prepare, narration.assemble):
                with self.assertRaises(FileExistsError):
                    operation("flowing")
            mkdir.assert_not_called()
            read.assert_not_called()
            run.assert_not_called()

    def test_changed_approved_archive_is_rejected_without_import_or_tts(self):
        for changed in ("clipchamp_timing.json", "clipchamp_input.m4a",
                        "clipchamp_input_decoded.wav"):
            takes, previous = approved_fixture()
            hashes = {
                "clipchamp_timing.json": narration.CLIPCHAMP_TIMING_SHA256,
                "clipchamp_input.m4a": narration.CLIPCHAMP_INPUT_SHA256,
                "clipchamp_input_decoded.wav": "decoded",
            }
            hashes[changed] = "changed"
            with self.subTest(changed=changed), \
                    patch.object(narration, "digest", side_effect=lambda path: hashes[path.name]), \
                    patch.object(Path, "read_text", return_value=json.dumps(previous)), \
                    patch.object(narration, "prepare_recording") as imported, \
                    patch.object(narration, "prepare_voice") as tts:
                with self.assertRaises(ValueError):
                    narration.prepare_flowing_voice(Path("staging"))
                imported.assert_not_called()
                tts.assert_not_called()

    def test_import_proves_unchanged_pcm_center_and_timing(self):
        takes, previous = approved_fixture()
        segments, frames = narration.schedule_takes(takes, "flowing", 2)
        decoded = sum(takes, array("h"))
        hashes = {
            "clipchamp_timing.json": narration.CLIPCHAMP_TIMING_SHA256,
            "clipchamp_input.m4a": narration.CLIPCHAMP_INPUT_SHA256,
            "clipchamp_input_decoded.wav": "decoded",
        }
        provenance = {"decoded_wav": "flowing_input_decoded.wav"}
        with patch.object(narration, "digest", side_effect=lambda path: hashes[path.name]), \
                patch.object(Path, "read_text", return_value=json.dumps(previous)), \
                patch.object(narration, "prepare_recording",
                             return_value=(segments, takes, frames, provenance)) as imported, \
                patch.object(narration, "read_pcm", return_value=decoded), \
                patch.object(narration, "prepare_voice") as tts:
            result = narration.prepare_flowing_voice(Path("staging"))
            self.assertTrue(result[3]["decoded_pcm_exact_match"])
            self.assertTrue(result[3]["centered_dual_mono"])
            imported.assert_called_once_with(
                Path("staging"), narration.RENDERS / "clipchamp_input.m4a", [4.46, 7.24], "flowing")
            tts.assert_not_called()
            with patch.object(narration, "read_pcm", side_effect=[decoded, array("h", [1, 1])]):
                with self.assertRaisesRegex(ValueError, "exact approved decoded PCM"):
                    narration.prepare_flowing_voice(Path("staging"))
            segments[0]["start_sample"] += 1
            with self.assertRaisesRegex(ValueError, "sentence timing"):
                narration.prepare_flowing_voice(Path("staging"))
            segments[0]["start_sample"] -= 1
            takes[0][0] += 1
            with self.assertRaisesRegex(ValueError, "dual-mono"):
                narration.prepare_flowing_voice(Path("staging"))

    def test_changed_prepared_asset_stops_before_source_inspection(self):
        _, previous = approved_fixture()
        report = dict(previous, schema=1, variant="flowing", fps=24, duration=14.625,
                      assets={"flowing_mix.wav": "approved"})
        with patch.object(Path, "exists", return_value=False), \
                patch.object(Path, "read_text", return_value=json.dumps(report)), \
                patch.object(narration, "digest", return_value="changed"), \
                patch.object(narration, "validate_video") as video, \
                patch.object(narration, "run") as run:
            with self.assertRaisesRegex(ValueError, "Prepared asset changed"):
                narration.assemble("flowing")
            video.assert_not_called()
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
