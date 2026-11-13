import csv
import math
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from analyze import analyze, fit_line, metrics, read_sensor


class CalibrationTests(unittest.TestCase):
    def test_validation_only_error(self):
        rows = [{"reference": 10, "measured": 500, "split": "calibration"},
                {"reference": 20, "measured": 22, "split": "validation"},
                {"reference": 40, "measured": 39, "split": "validation"}]
        result = metrics(rows)
        self.assertEqual(result["n"], 2)
        self.assertEqual(result["mae"], 1.5)
        self.assertEqual(result["mean_error"], .5)
        self.assertAlmostEqual(result["rmse"], math.sqrt(2.5))
        self.assertEqual(result["max_abs_error"], 2)

    def test_no_data_is_not_zero_error(self):
        self.assertIsNone(metrics([])["mae"])
        self.assertIsNone(fit_line([(5, 1), (5, 2)]))

    def test_nan_and_bad_adc_rejected(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-calibration-") as temp:
            path = Path(temp) / "ir.csv"
            for raw in ("nan", "1024", "-1"):
                path.write_text(f"reference,raw_adc,measured,split\n20,{raw},21,validation\n")
                with self.assertRaises(ValueError):
                    read_sensor(path, "ir")

    def test_synthetic_end_to_end_outputs(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-calibration-") as temp:
            root = Path(temp)
            (root / "sonar.csv").write_text(
                "reference,raw_adc,measured,split,notes\n"
                "25.4,20,25.4,calibration,SYNTHETIC\n"
                "127,100,127,calibration,SYNTHETIC\n"
                "50,40,50.8,validation,SYNTHETIC\n")
            (root / "ir_filter.csv").write_text(
                "time_s,raw_cm,filtered_cm,notes\n"
                "0,31,30.1,SYNTHETIC\n1,29,30.0,SYNTHETIC\n2,30,30.0,SYNTHETIC\n")
            result = analyze(root, root / "out")
            self.assertAlmostEqual(result["sensors"]["sonar"]["mae"], .8)
            self.assertIsNone(result["sensors"]["pot"]["mae"])
            self.assertGreater(result["filter"]["raw_std_cm"], result["filter"]["filtered_std_cm"])
            files = list((root / "out").glob("*.svg"))
            self.assertEqual(len(files), 3)
            for path in files:
                self.assertTrue(ET.parse(path).getroot().tag.endswith("svg"))
            fit = fit_line([(20, 25.4), (100, 127)])
            self.assertAlmostEqual(fit["slope"], 1.27)
            self.assertAlmostEqual(fit["intercept"], 0)
            with self.assertRaises(ValueError):
                analyze(root, root / "out")


    def test_calibration_rows_may_omit_measured_but_validation_may_not(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-calibration-") as temp:
            path = Path(temp) / "pot.csv"
            path.write_text("reference,raw_adc,measured,split\n0,100,,calibration\n")
            self.assertIsNone(read_sensor(path, "pot")[0]["measured"])
            path.write_text("reference,raw_adc,measured,split\n0,100,,validation\n")
            with self.assertRaises(ValueError):
                read_sensor(path, "pot")

    def test_firmware_suggestions_for_ir_table_and_pot(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-calibration-") as temp:
            root = Path(temp)
            (root / "ir.csv").write_text(
                "reference,raw_adc,measured,split,notes\n"
                "20,500,,calibration,SYNTHETIC\n40,290,,calibration,SYNTHETIC\n40,284,,calibration,SYNTHETIC\n"
                "150,83,,calibration,SYNTHETIC\n")
            (root / "pot.csv").write_text(
                "reference,raw_adc,measured,split,notes\n"
                "0,100,,calibration,SYNTHETIC\n135,500,,calibration,SYNTHETIC\n270,900,,calibration,SYNTHETIC\n")
            analyze(root, root / "out")
            text = (root / "out" / "hardware_config_suggestion.txt").read_text()
            self.assertIn("IR_TABLE_ADC[] = {500, 287, 83}", text)
            self.assertIn("IR_TABLE_CM[] = {20, 40, 150}", text)
            self.assertIn("POT_ADC_MIN = 100, POT_ADC_MAX = 900", text)
            self.assertIn("POT_TRAVEL_DEG = 270.0f", text)

    def test_capture_averages_paired_frames_into_one_row(self):
        import types
        from unittest.mock import patch
        import capture
        from sensor_motor_lab.protocol import parse_line
        state = parse_line("STATE,100,0,-1,50.0,40,40.5,100,0,0,30,0,0,0,RPM,0,0,0,0,0,NONE")
        raws = [parse_line(f"RAW,100,512,{adc},79,0,0,0,0") for adc in (286, 288, 287, 287, 287, 288)]
        with tempfile.TemporaryDirectory(prefix="synthetic-calibration-") as temp:
            root = Path(temp)
            (root / "ir.csv").write_text("reference,raw_adc,measured,split,notes\n")
            args = types.SimpleNamespace(sensor="ir", reference=40.0, split="validation", seconds=1, notes="SYNTHETIC", port="X")
            with patch.object(capture, "HERE", root), patch("builtins.input", lambda *_: ""), \
                    patch.object(capture, "frames", lambda port, seconds: ((state, r) for r in raws)):
                capture.capture_sensor(args)
            row = next(csv.DictReader((root / "ir.csv").open()))
            self.assertEqual((row["reference"], row["raw_adc"], row["measured"], row["split"]), ("40", "287.17", "40.500", "validation"))
            invalid = parse_line("STATE,100,0,-1,50.0,-1,-1,100,0,0,30,0,0,0,RPM,0,0,0,0,0,NONE")
            with patch.object(capture, "HERE", root), patch("builtins.input", lambda *_: ""), \
                    patch.object(capture, "frames", lambda port, seconds: ((invalid, r) for r in raws)), \
                    self.assertRaises(SystemExit):
                capture.capture_sensor(args)

    def test_capture_frames_skip_telemetry_from_before_the_reset(self):
        import capture

        class FakePort:
            """Serial stand-in: hands out scripted chunks, then nothing."""
            def __init__(self, *chunks):
                self.chunks = list(chunks)
            def __enter__(self):
                return self
            def __exit__(self, *exc):
                return False
            def read(self, size):
                return self.chunks.pop(0) if self.chunks else b""

        def pair(ms, slot=0):
            return (f"STATE,{ms},0,-1,50.0,40,40.5,100,{slot},0,30,0,0,0,RPM,0,0,0,0,0,NONE\n"
                    f"RAW,{ms},512,287,79,0,0,0,0\n").encode()

        def run(port, **kwargs):
            return [(s.ms, s.slot_count) for s, _ in capture.frames("X", 0.05, connection=port, **kwargs)]

        # Uno resets on open: the frame left in the USB buffer (old clock, old count) is dropped.
        stale = FakePort(pair(270600, slot=7), b"INFO,BOOT_DISARMED\n", pair(100), pair(200, slot=1))
        self.assertEqual(run(stale), [(100, 0), (200, 1)])
        # Board that does not reset on open: telemetry is used once the grace period ends.
        self.assertEqual(run(FakePort(pair(5000), pair(5100)), boot_grace=-1), [(5000, 0), (5100, 0)])
        # A reset in the middle of a capture aborts instead of mixing old and new data.
        with self.assertRaises(SystemExit):
            run(FakePort(b"INFO,BOOT_DISARMED\n", pair(100), pair(200), b"INFO,BOOT_DISARMED\n", pair(100)))

    def test_folded_ir_curve_is_flagged_not_suggested(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-calibration-") as temp:
            root = Path(temp)
            (root / "ir.csv").write_text("reference,raw_adc,measured,split\n10,400,,calibration\n20,500,,calibration\n"
                                         "40,287,,calibration\n")
            analyze(root, root / "out")
            self.assertIn("not strictly decreasing", (root / "out" / "hardware_config_suggestion.txt").read_text())


if __name__ == "__main__":
    unittest.main()
