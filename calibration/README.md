# Sensor Calibration and Error Analysis

The CSV files hold rows recorded with `capture.py`; results are reported in `tests/TEST_REPORT.md`. The unit tests create their own synthetic data in a temporary directory and never write to these files.

## Procedure

1. **Calibration**: at several reference points covering the sensor's range, record the reference value and the raw ADC reading.
2. **Suggested parameters**: `analyze.py` fits the calibration rows and writes `hardware_config_suggestion.txt`. Review it, copy the values into `firmware/hardware_config.h`, then regenerate and re-upload the sketch.
3. **Validation**: record again at positions **different from the calibration points**; this time `measured` is the physical value converted by the firmware. Error statistics use **validation rows only**, so the fitted points are not used to claim accuracy.
4. Once validation data support it, set the matching `*_CALIBRATED` flag to true.

## Data collection

| File | How to collect |
|---|---|
| `pot.csv` | Read the sticker pointer on the knob against a protractor; 0° is the end with the lowest ADC. Cover both ends and the middle, at least 5 points. Leave `measured` empty while the pot is uncalibrated (allowed on calibration rows only). |
| `ir.csv` | White board facing the sensor, distance measured with a tape from the sensor's front face. **20–150 cm**, one point every 10 cm, 2–3 repeats per point. Below 20 cm the output folds back, so keep those points out of the calibration table. |
| `sonar.csv` | Same board and tape, from about 20 cm to the farthest distance the field allows (e.g. 300 cm), at least 6 points. Readings saturate at ≤ 15 cm. |
| `slot.csv` | One row per trial: `reference` = actual number of beam breaks, `measured` = counter increase. Do one slow, one fast and one held-blocked trial. |
| `ir_filter.csv` | Fixed target, recorded after the filter settles; `raw_cm` and `filtered_cm` come from the same frame. Record the lag for a moving target separately. |

Columns: `reference` (independent reference value: cm / ° / count), `raw_adc` (mean ADC), `measured` (physical value shown by the firmware), `split` (calibration / validation), `notes`.

## Analysis

```bash
python calibration/analyze.py --input calibration --output calibration/results_20261109
```

The output directory must be new or empty, so old plots cannot be mistaken for new results.

| Output | Contents |
|---|---|
| `error_summary.csv`, `summary.json` | Per sensor: validation sample count, reference range, mean bias, MAE, RMSE, max error. Empty (not 0) when there is no data. |
| `*_transfer.svg` | **Transfer curve**: independently measured physical quantity on x, raw ADC on y (required by the assignment; show sonar and IR). |
| `*_error.svg` | Validation error vs. reference value. |
| `ir_filter.svg` | Raw and filtered readings on the same time axis (the filter demonstration required by the assignment). |
| `calibration_suggestions.json`, `hardware_config_suggestion.txt` | New IR lookup table, sonar cm/ADC, pot ADC end points and travel angle. **Not written into the firmware automatically.** |

The filter's standard deviation is only meaningful for a fixed target after the filter has settled. Changes caused by motion are not noise, and a smoother curve is not necessarily more accurate.

```bash
cd calibration && python -m unittest test_analysis.py -v     # 7 tests
```
