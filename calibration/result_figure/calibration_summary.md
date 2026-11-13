# Calibration and Test Data Summary

Sources: `calibration/ir.csv`, `ir_filter.csv`, `sonar.csv`, `pot.csv` and `slot.csv` (measured 2026-11-10). The DC encoder CPR was measured and reported by the team on 2026-11-11. All values are physical measurements.

## Table 1: IR rangefinder (Sharp GP2Y0A02) calibration

Each point was sampled for about 5 s. "Converted distance" uses the vendor typical table in the firmware (the team calibration has not been applied yet).

| Actual distance (cm) | Mean ADC | ADC std | Samples | Converted distance (cm) | Error (cm) | Error (%) |
|---|---|---|---|---|---|---|
| 30 | 450.4 | 13.8 | 46 | 24.1 | -5.9 | -19.8% |
| 50 | 279.0 | 15.0 | 46 | 41.9 | -8.1 | -16.2% |
| 80 | 179.3 | 15.2 | 46 | 70.4 | -9.6 | -12.0% |
| 100 | 144.5 | 15.6 | 46 | 87.5 | -12.5 | -12.5% |
| 110 | 132.2 | 15.4 | 46 | 94.2 | -15.8 | -14.4% |

- The ADC decreases as the distance increases, in a nonlinear (roughly inverse) relationship; see `ir_transfer_function.png`.
- The vendor table reads 6–16 cm short across the whole range, so it should be replaced by the team calibration table.
- The ADC noise is about the same at every distance (about 14–16 counts).

## Table 2: IR filter (fixed target at 50 cm, 18.4 s, 167 samples)

| | Mean (cm) | Error (cm) | Error (%) | Std (cm) | Peak-to-peak (cm) |
|---|---|---|---|---|---|
| Raw | 46.16 | -3.84 | -7.7% | 2.34 | 10.6 |
| Filtered (5-sample moving average) | 46.15 | -3.85 | -7.7% | 1.08 | 4.8 |

- The standard deviation drops by about 2.2× (√5 ≈ 2.2 in theory) and the mean is unchanged. The filter delay is about 40 ms (a 5-sample moving average lags by 2 samples at 20 ms per sample).
- The mean offset comes from the vendor table. Filtering cannot remove it; calibration is needed. See `ir_filter_raw_vs_filtered.png`.

## Table 3: Ultrasonic rangefinder (LV-MaxSonar-EZ)

"Converted distance" uses the firmware's 1.27 cm/ADC. Validation rows (stationary flat board) were recorded before the calibration rows (larger flat board).

| Split | Actual distance (cm) | Mean ADC | ADC std | Converted distance (cm) | Error (cm) |
|---|---|---|---|---|---|
| validation | 50 | 32.13 | 12.82 | 45.55 | -4.45 |
| validation | 80 | 46.67 | 19.70 | 63.94 | -16.06 |
| validation | 100 | 49.42 | 27.54 | 60.19 | -39.81 |
| calibration | 30 | 27.70 | 12.63 | 31.67 | +1.67 |
| calibration | 50 | 34.59 | 11.81 | 44.86 | -5.14 |
| calibration | 80 | 53.04 | 21.25 | 60.88 | -19.12 |
| calibration | 100 | 44.37 | 22.94 | 58.72 | -41.28 |
| calibration | 100 | 45.54 | 21.12 | 56.46 | -43.54 |

- Validation error (n = 3, 50–100 cm): mean -20.1 cm, MAE 20.1 cm, RMSE 24.9 cm, max 39.8 cm.
- The ADC at 80 cm is higher than at 100 cm and the ADC spread grows with distance, consistent with echoes from nearby objects during the setup.
- Plots: `../results_20261112/sonar_transfer.svg`, `../results_20261112/sonar_error.svg`.

## Table 4: Other sensors and motor

| Item | Actual value | Measured value | Result |
|---|---|---|---|
| Potentiometer 0° | 0° | ADC 6.5 (std 5.8) → 0.0° | Error 0.0° |
| Potentiometer 90° | 90° | ADC 272.0 (std 3.1) → 76.7° | Error -13.3° |
| Potentiometer 180° | 180° | ADC 629.3 (std 1.0) → 180.0° | Error 0.0° |
| Slot sensor (slow beam breaks, trial 1) | 10 | 11 | Overcounted by 1 |
| Slot sensor (slow beam breaks, trial 2) | 10 | 10 | Correct |
| DC encoder CPR | Output shaft 10 revolutions (10 RPM) | 3600 counts | **CPR = 360**, matches the firmware setting |

Potentiometer angles were converted offline from the measured ADC with the firmware's linear formula (`POT_ADC_MIN` = 6.46, `POT_ADC_MAX` = 629.30, travel 180°).

## Notes

- The team calibration table has not been applied and no IR validation points have been collected yet. After applying it, add a "calibrated error" column to Table 1.
