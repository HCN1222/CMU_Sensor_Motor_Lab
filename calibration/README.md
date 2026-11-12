# Sensor Calibration and Error Analysis

The CSV files here contain headers only; no measurements have been recorded yet.

## Procedure

1. **Calibration**: at several reference points covering the sensor's range, record the reference value and the raw ADC reading.
2. **Suggested parameters**: fit conversion parameters from the calibration rows, review them, copy them into `firmware/hardware_config.h`, then regenerate and re-upload the sketch.
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
