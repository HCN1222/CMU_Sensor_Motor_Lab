#!/usr/bin/env python3
"""Analyze measured lab CSVs. Standard library only; never creates sample measurements."""
import argparse
import csv
import html
import json
import math
from pathlib import Path
import statistics

SENSORS = {"pot": "deg", "ir": "cm", "sonar": "cm", "slot": "events"}


def number(value, field, source):
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{source}: {field} must be a number") from exc
    if not math.isfinite(result):
        raise ValueError(f"{source}: {field} must be finite")
    return result


def read_sensor(path, sensor):
    if not path.exists():
        return []
    rows = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"reference", "measured", "split"}
        if sensor != "slot":
            required.add("raw_adc")
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"{path}: missing columns {sorted(required)}")
        for line, row in enumerate(reader, 2):
            if not any((value or "").strip() for value in row.values()):
                continue
            src = f"{path}:{line}"
            split = (row["split"] or "").strip().lower()
            if split not in {"calibration", "validation"}:
                raise ValueError(f"{src}: split must be calibration or validation")
            measured_text = (row["measured"] or "").strip()
            if not measured_text and split == "validation":
                raise ValueError(f"{src}: validation rows need the converted measured value")
            # Calibration rows only need reference + raw ADC (e.g. pot degrees before its travel is known).
            parsed = {"reference": number(row["reference"], "reference", src),
                      "measured": number(measured_text, "measured", src) if measured_text else None,
                      "split": split, "notes": row.get("notes", "")}
            if parsed["reference"] < 0 or (parsed["measured"] is not None and parsed["measured"] < 0):
                raise ValueError(f"{src}: negative physical readings are invalid here")
            if sensor == "slot":
                if parsed["measured"] is None:
                    raise ValueError(f"{src}: slot rows need the counted events")
                if any(parsed[key] != int(parsed[key]) for key in ("reference", "measured")):
                    raise ValueError(f"{src}: event counts must be integers")
            else:
                parsed["raw_adc"] = number(row["raw_adc"], "raw_adc", src)
                if not 0 <= parsed["raw_adc"] <= 1023:
                    raise ValueError(f"{src}: mean Uno ADC value must be within 0..1023")
            rows.append(parsed)
    return rows


def metrics(rows):
    """Only held-out/repeated validation measurements establish reported error."""
    selected = [r for r in rows if r["split"] == "validation"]
    if not selected:
        return {"n": 0, "mean_error": None, "mae": None, "rmse": None,
                "max_abs_error": None, "reference_min": None, "reference_max": None}
    errors = [r["measured"] - r["reference"] for r in selected]
    return {"n": len(selected), "mean_error": statistics.mean(errors),
            "mae": statistics.mean(abs(e) for e in errors),
            "rmse": math.sqrt(statistics.mean(e * e for e in errors)),
            "max_abs_error": max(abs(e) for e in errors),
            "reference_min": min(r["reference"] for r in selected),
            "reference_max": max(r["reference"] for r in selected)}


def fit_line(points):
    if len(points) < 2:
        return None
    mx = statistics.mean(p[0] for p in points)
    my = statistics.mean(p[1] for p in points)
    variance = sum((x - mx) ** 2 for x, _ in points)
    if variance <= 0:
        return None
    slope = sum((x - mx) * (y - my) for x, y in points) / variance
    return {"slope": slope, "intercept": my - slope * mx,
            "formula": "physical_value = slope * raw_adc + intercept"}


def suggestions(sensor, rows):
    calibration = [r for r in rows if r["split"] == "calibration"]
    if sensor == "slot" or not calibration:
        return None
    if sensor in {"pot", "sonar"}:
        fit = fit_line([(r["raw_adc"], r["reference"]) for r in calibration])
        if fit is None:
            return None
        if sensor == "sonar":
            fit["hardware_config"] = (f"const float SONAR_CM_PER_ADC = {fit['slope']:.4f}f;"
                                      f"  // fitted intercept {fit['intercept']:.2f} cm (firmware assumes ~0)")
        else:
            low = min(r["raw_adc"] for r in calibration)
            high = max(r["raw_adc"] for r in calibration)
            travel = abs(fit["slope"]) * (high - low)
            fit["hardware_config"] = (f"const int16_t POT_ADC_MIN = {round(low)}, POT_ADC_MAX = {round(high)};\n"
                                      f"const float POT_TRAVEL_DEG = {travel:.1f}f;"
                                      "  // angle between the two ADC end points; 0 deg at POT_ADC_MIN")
        return fit
    # IR: one table point per reference distance (mean ADC of repeats). No extrapolation.
    grouped = {}
    for row in calibration:
        grouped.setdefault(row["reference"], []).append(row["raw_adc"])
    values = [(cm, statistics.mean(adc)) for cm, adc in sorted(grouped.items())]
    if len(values) < 2:
        return None
    decreasing = all(values[i][1] > values[i + 1][1] for i in range(len(values) - 1))
    result = {"method": "piecewise linear interpolation; do not extrapolate",
              "distance_cm": [v[0] for v in values],
              "mean_adc": [v[1] for v in values],
              "adc_strictly_decreasing": decreasing}
    if decreasing:
        result["hardware_config"] = (
            "const int16_t IR_TABLE_ADC[] = {" + ", ".join(str(round(v[1])) for v in values) + "};\n"
            "const float IR_TABLE_CM[] = {" + ", ".join(f"{v[0]:g}" for v in values) + "};")
    else:
        result["hardware_config"] = None
        result["problem"] = ("ADC is not strictly decreasing with distance: remove points below ~20 cm "
                             "(the GP2Y0A02 output folds back there) or re-measure noisy points.")
    return result


def plot_svg(path, title, xlabel, ylabel, series, connect=False, xticks=None, hlines=()):
    """Write a fully labeled, scalable plot without requiring a plotting install.

    series: (name, points, color[, style[, label]]) where style is "points", "line" or
    "both" and label is a format string ({x}, {y}) written next to each distinct x.
    xticks: put the x grid at these values (e.g. the distances actually measured).
    hlines: (y, text, color) dashed reference lines, e.g. the true target distance.
    """
    all_points = [p for entry in series for p in entry[1]]
    if not all_points:
        return
    xmin, xmax = min(p[0] for p in all_points), max(p[0] for p in all_points)
    ys = [p[1] for p in all_points] + [h[0] for h in hlines]
    ymin, ymax = min(ys), max(ys)
    dx, dy = xmax - xmin, ymax - ymin
    dx = dx if dx > 0 else max(1, abs(xmin) * .1)
    dy = dy if dy > 0 else max(1, abs(ymin) * .1)
    pad = .16 if any(len(entry) > 4 and entry[4] for entry in series) else .08  # room for point labels
    xmin, xmax = xmin - dx * .05, xmax + dx * .05
    ymin, ymax = ymin - dy * pad, ymax + dy * pad
    left, top, width, height = 108, 85, 820, 470
    sx = lambda x: left + (x - xmin) / (xmax - xmin) * width
    sy = lambda y: top + height - (y - ymin) / (ymax - ymin) * height
    esc = html.escape
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="680" viewBox="0 0 1000 680">',
           '<rect width="1000" height="680" fill="white"/>',
           '<g font-family="Arial,sans-serif" fill="#182332">',
           f'<text x="108" y="40" font-size="23" font-weight="bold">{esc(title)}</text>']
    grid_x = sorted(xticks) if xticks else [xmin + (xmax - xmin) * i / 5 for i in range(6)]
    for x in grid_x:
        svg.extend([f'<path d="M {sx(x):.2f} {top} v {height}" stroke="#e3e7ed"/>',
                    f'<text x="{sx(x):.2f}" y="580" text-anchor="middle" font-size="14">{x:.4g}</text>'])
    for i in range(6):
        y = ymin + (ymax - ymin) * i / 5
        svg.extend([f'<path d="M {left} {sy(y):.2f} h {width}" stroke="#e3e7ed"/>',
                    f'<text x="94" y="{sy(y)+5:.2f}" text-anchor="end" font-size="14">{y:.4g}</text>'])
    hline_svg = []  # drawn after the data so the label stays readable over it
    for y, text, color in hlines:
        box = 8.6 * len(text) + 12
        hline_svg.extend([f'<path d="M {left} {sy(y):.2f} h {width}" stroke="{color}" stroke-width="2" stroke-dasharray="8 6"/>',
                          f'<rect x="{left + width - box:.2f}" y="{sy(y) - 26:.2f}" width="{box:.2f}" height="21" '
                          f'fill="white" fill-opacity="0.9" stroke="{color}" stroke-width="1" rx="3"/>',
                          f'<text x="{left + width - 6}" y="{sy(y) - 10:.2f}" text-anchor="end" font-size="15" '
                          f'font-weight="bold" fill="{color}">{esc(text)}</text>'])
    svg.extend([f'<path d="M {left} {top} v {height} h {width}" fill="none" stroke="#273548" stroke-width="1.5"/>',
                f'<text x="518" y="615" text-anchor="middle" font-size="17">{esc(xlabel)}</text>',
                f'<text transform="translate(30 320) rotate(-90)" text-anchor="middle" font-size="17">{esc(ylabel)}</text>'])
    for idx, entry in enumerate(series):
        # Optional 4th element: "points", "line" (in the given order) or "both"
        # (markers plus a line through the mean at each x, so repeats do not zigzag).
        name, points, color = entry[:3]
        style = entry[3] if len(entry) > 3 else ("line" if connect else "points")
        label = entry[4] if len(entry) > 4 else None
        grouped = {}
        for x, y in points:
            grouped.setdefault(x, []).append(y)
        means = [(x, statistics.mean(values)) for x, values in sorted(grouped.items())]
        if style in ("line", "both") and len(points) > 1:
            line = means if style == "both" else points
            coords = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y in line)
            svg.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="2"/>')
        if style in ("points", "both"):
            svg.extend(f'<circle cx="{sx(x):.2f}" cy="{sy(y):.2f}" r="4" fill="{color}"/>' for x, y in points)
        if label:
            # Put each label on the side away from the curve: below/above-left of the
            # incoming segment, or (first point) on the side the outgoing segment leaves free.
            for i, (x, y) in enumerate(means):
                cx, cy = sx(x), sy(y)
                if i:
                    right, below = False, sy(means[i - 1][1]) < cy
                else:
                    right, below = True, len(means) > 1 and sy(means[1][1]) < cy
                lines = label.format(x=x, y=y).split("\n")
                first = cy + 22 if below else cy - 12 - 16 * (len(lines) - 1)
                tx = cx + 10 if right else cx - 10
                # One <text> per line: some SVG renderers (Qt) ignore positioned <tspan>s.
                svg.extend(f'<text x="{tx:.2f}" y="{first + 16 * k:.2f}" text-anchor="{"start" if right else "end"}" '
                           f'font-size="14" fill="{color}">{esc(t)}</text>' for k, t in enumerate(lines))
        legend_x = 108 + 310 * idx
        svg.append(f'<rect x="{legend_x}" y="642" width="20" height="4" fill="{color}"/>')
        svg.append(f'<text x="{legend_x+28}" y="649" font-size="14">{esc(name)}</text>')
    svg.extend(hline_svg)
    svg.append('</g></svg>')
    path.write_text("\n".join(svg), encoding="utf-8")


def analyze_filter(path, output, reference=None):
    """reference: the target distance measured with a tape (cm), drawn as a dashed line."""
    if not path.exists():
        return None
    samples = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not {"time_s", "raw_cm", "filtered_cm"}.issubset(reader.fieldnames or []):
            raise ValueError(f"{path}: missing filter columns")
        for line, row in enumerate(reader, 2):
            if not any((value or "").strip() for value in row.values()):
                continue
            values = tuple(number(row[k], k, f"{path}:{line}") for k in ("time_s", "raw_cm", "filtered_cm"))
            if values[0] < 0 or (samples and values[0] <= samples[-1][0]):
                raise ValueError(f"{path}:{line}: time must increase strictly")
            if min(values[1:]) < 0:
                raise ValueError(f"{path}:{line}: distances must be nonnegative")
            samples.append(values)
    if not samples:
        return None
    plot_svg(output / "ir_filter.svg", "IR raw and filtered measurements",
             "Time (s)", "Distance (cm)",
             [("Raw", [(r[0], r[1]) for r in samples], "#a7adb7"),
              ("Filtered", [(r[0], r[2]) for r in samples], "#1568aa")], connect=True,
             hlines=[(reference, f"Actual target distance {reference:g} cm", "#d35b2a")] if reference is not None else ())
    result = {"n": len(samples),
              "raw_std_cm": statistics.stdev(r[1] for r in samples) if len(samples) > 1 else None,
              "filtered_std_cm": statistics.stdev(r[2] for r in samples) if len(samples) > 1 else None,
              "interpretation": "Compare standard deviations only for a stationary target after filter settling; motion and lag are not noise."}
    if reference is not None:
        result.update(reference_cm=reference,
                      raw_mean_error_cm=statistics.mean(r[1] for r in samples) - reference,
                      filtered_mean_error_cm=statistics.mean(r[2] for r in samples) - reference)
    return result


def analyze(input_dir, output_dir, filter_reference=None):
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"{output_dir}: use a new or empty output directory so old plots cannot be mistaken for new measurements")
    output_dir.mkdir(parents=True, exist_ok=True)
    summary, fits = {}, {}
    for sensor, unit in SENSORS.items():
        rows = read_sensor(input_dir / f"{sensor}.csv", sensor)
        summary[sensor] = {"unit": unit, "rows": len(rows), **metrics(rows)}
        fit = suggestions(sensor, rows)
        if fit is not None:
            fits[sensor] = fit
        if sensor != "slot" and rows:
            plot_svg(output_dir / f"{sensor}_transfer.svg", f"{sensor.upper()} measured transfer function",
                     f"Reference physical quantity ({unit})", "Raw output (ADC counts)",
                     [("Calibration", [(r["reference"], r["raw_adc"]) for r in rows if r["split"] == "calibration"], "#1568aa", "both",
                       f"{{x:g}} {unit}\nADC {{y:.0f}}"),
                      ("Validation", [(r["reference"], r["raw_adc"]) for r in rows if r["split"] == "validation"], "#d35b2a", "points")],
                     xticks=sorted({r["reference"] for r in rows}))
        validation = [r for r in rows if r["split"] == "validation"]
        if validation:
            plot_svg(output_dir / f"{sensor}_error.svg", f"{sensor.upper()} validation error",
                     f"Reference physical quantity ({unit})", f"Measured minus reference ({unit})",
                     [("Independent validation", [(r["reference"], r["measured"] - r["reference"]) for r in validation], "#1568aa")])
    filter_result = analyze_filter(input_dir / "ir_filter.csv", output_dir, filter_reference)
    result = {"data_policy": "Computed only from supplied CSV rows; missing data is null, not zero error.",
              "sensors": summary, "filter": filter_result}
    (output_dir / "summary.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (output_dir / "calibration_suggestions.json").write_text(json.dumps(fits, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    snippet = ["// Suggested firmware/hardware_config.h values from calibration rows (NOT applied automatically).",
               "// Review coverage and the validation error first, then copy, regenerate and re-upload.",
               "// Set the matching *_CALIBRATED flag only when validation data support it."]
    for sensor, fit in fits.items():
        if fit.get("hardware_config"):
            snippet += [f"// {sensor}", fit["hardware_config"]]
        elif fit.get("problem"):
            snippet += [f"// {sensor}: {fit['problem']}"]
    (output_dir / "hardware_config_suggestion.txt").write_text("\n".join(snippet) + "\n", encoding="utf-8")
    with (output_dir / "error_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        columns = ["sensor", "unit", "rows", "n", "reference_min", "reference_max", "mean_error", "mae", "rmse", "max_abs_error"]
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for sensor, row in summary.items():
            writer.writerow({"sensor": sensor, **row})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path(__file__).parent)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--filter-reference", type=float, metavar="CM",
                        help="tape-measured distance of the fixed ir-filter target; drawn as a reference line")
    args = parser.parse_args()
    try:
        result = analyze(args.input, args.output, args.filter_reference)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    for sensor, info in result["sensors"].items():
        print(f"{sensor}: {info['rows']} rows, {info['n']} validation samples" +
              (f", MAE={info['mae']:.4g} {info['unit']}" if info['n'] else "; error not measured yet"))
    print(f"Saved analysis to {args.output.resolve()}")


if __name__ == "__main__":
    main()
