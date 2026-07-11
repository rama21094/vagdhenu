#!/usr/bin/env python3
"""Signal, Sanskrit frontend, meter, and phoneme audit for Narayaneeyam metadata.

Run after ``audit_narayaneeyam.py``. This script requires numpy, soundfile, and
indic-transliteration, but writes only derived reports in the chosen output dir.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import soundfile as sf
from indic_transliteration import sanscript


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from chandas_labeler import identify, scan  # noqa: E402
from prep_text import align_slp1, model_text  # noqa: E402


SLP1_PHONES = set("aAiIuUfFxXeEoOkKgGNcCjJYwWqQRtTdDnpPbBmyrlvSzshMH~")
IMPORTANT_PATTERNS = (
    "kz", "jY", "tr", "dr", "Dra", "dhr", "hm", "hn", "zw", "zW", "rB",
    "rP", "rT", "rD", "rQ", "rS", "rj", "rk", "rg",
)


def db(value: float) -> float:
    return 20.0 * math.log10(max(value, 1e-12))


def window_rms(mono: np.ndarray, sample_rate: int, window_s: float = 0.02) -> np.ndarray:
    width = max(1, round(sample_rate * window_s))
    usable = len(mono) // width * width
    if not usable:
        return np.zeros(0, dtype=np.float32)
    frames = mono[:usable].reshape(-1, width)
    return np.sqrt(np.mean(np.square(frames, dtype=np.float64), axis=1))


def edge_silence(rms: np.ndarray, threshold: float, window_s: float = 0.02) -> tuple[float, float]:
    active = np.flatnonzero(rms >= threshold)
    if not len(active):
        return len(rms) * window_s, len(rms) * window_s
    leading = float(active[0] * window_s)
    trailing = float((len(rms) - 1 - active[-1]) * window_s)
    return leading, trailing


def signal_metrics(path: Path) -> dict:
    audio, sr = sf.read(path, dtype="float32", always_2d=True)
    mono = audio.mean(axis=1)
    peak = float(np.max(np.abs(audio), initial=0.0))
    rms = float(np.sqrt(np.mean(np.square(mono, dtype=np.float64))))
    dc = float(np.mean(mono))
    clipped = float(np.mean(np.abs(audio) >= 0.999))
    wrms = window_rms(mono, sr)
    # Relative gate is robust across differently normalized sessions, with an
    # absolute -50 dBFS floor to avoid treating room tone as speech.
    active_threshold = max(10 ** (-50 / 20), rms * 0.12)
    leading, trailing = edge_silence(wrms, active_threshold)
    silent_fraction = float(np.mean(wrms < active_threshold)) if len(wrms) else 1.0
    stereo_corr = 1.0
    stereo_diff_db = -240.0
    if audio.shape[1] == 2:
        left, right = audio[:, 0], audio[:, 1]
        if np.std(left) > 1e-8 and np.std(right) > 1e-8:
            stereo_corr = float(np.corrcoef(left, right)[0, 1])
        diff_rms = float(np.sqrt(np.mean(np.square(left - right, dtype=np.float64))))
        stereo_diff_db = db(diff_rms)
    return {
        "decoded_frames": len(audio),
        "peak_dbfs": round(db(peak), 3),
        "rms_dbfs": round(db(rms), 3),
        "dc_offset": round(dc, 7),
        "clipped_fraction": round(clipped, 8),
        "leading_silence_s": round(leading, 3),
        "trailing_silence_s": round(trailing, 3),
        "silent_window_fraction": round(silent_fraction, 5),
        "stereo_correlation": round(stereo_corr, 6),
        "stereo_difference_dbfs": round(stereo_diff_db, 3),
    }


def original_lines(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8-sig")
    lines = []
    for line in text.replace("\r", "\n").split("\n"):
        line = unicodedata.normalize("NFC", " ".join(line.split()))
        if line:
            lines.append(line)
    return lines


def text_metrics(text: str, text_path: Path, vocab: set[str]) -> tuple[dict, Counter, Counter, Counter]:
    # ZWJ/ZWNJ are typography controls rather than spoken Sanskrit phones.
    clean = text.replace("\u200c", "").replace("\u200d", "")
    slp = align_slp1(clean)
    model = model_text(clean)
    phone_counts = Counter(ch for ch in slp if ch in SLP1_PHONES)
    pattern_counts = Counter({pat: slp.count(pat) for pat in IMPORTANT_PATTERNS if slp.count(pat)})
    meters: Counter = Counter()
    line_scans = []
    for line in original_lines(text_path):
        line_slp = align_slp1(line)
        weights, syllables = scan(line_slp)
        meter = identify(weights)
        meters[meter] += 1
        line_scans.append({"syllables": syllables, "weights": "".join(weights), "meter": meter})
    oov = Counter(c for c in model if vocab and c not in vocab)
    metrics = {
        "text_clean": clean,
        "text_model_kannada": model,
        "slp1": slp,
        "syllables": sum(1 for ch in slp if ch in set("aAiIuUfFxXeEoO")),
        "line_scans_json": json.dumps(line_scans, ensure_ascii=False, separators=(",", ":")),
        "model_oov": "".join(sorted(oov)),
    }
    return metrics, phone_counts, pattern_counts, meters


def audio_issues(metrics: dict, sample_rate: int) -> list[str]:
    issues = []
    if sample_rate < 24_000:
        issues.append("sample_rate_below_24khz")
    if metrics["peak_dbfs"] > -0.1 or metrics["clipped_fraction"] > 0.00001:
        issues.append("clipping_risk")
    if metrics["peak_dbfs"] < -12:
        issues.append("low_peak")
    if metrics["rms_dbfs"] < -35:
        issues.append("low_rms")
    if abs(metrics["dc_offset"]) > 0.01:
        issues.append("dc_offset")
    if metrics["leading_silence_s"] > 0.5:
        issues.append("long_leading_silence")
    if metrics["trailing_silence_s"] > 0.7:
        issues.append("long_trailing_silence")
    if metrics["silent_window_fraction"] > 0.35:
        issues.append("excess_silence")
    if metrics["stereo_correlation"] < 0.5:
        issues.append("stereo_mismatch")
    return issues


def quantile(rows: list[dict], key: str, q: float) -> float:
    values = np.asarray([float(row[key]) for row in rows], dtype=np.float64)
    return float(np.quantile(values, q)) if len(values) else 0.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("metadata", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--vocab", type=Path, default=REPO / "src/reference_bank/vocab.txt")
    args = parser.parse_args()
    out_dir = (args.out or args.metadata.parent).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    vocab = set(args.vocab.read_text(encoding="utf-8").splitlines()) if args.vocab.exists() else set()

    with args.metadata.open(encoding="utf-8") as handle:
        source_rows = list(csv.DictReader(handle))
    enriched = []
    all_phones: Counter = Counter()
    all_patterns: Counter = Counter()
    all_meters: Counter = Counter()
    issue_counts: Counter = Counter()
    issue_rows = []

    for number, row in enumerate(source_rows, 1):
        signal = signal_metrics(Path(row["audio_path"]))
        text, phones, patterns, meters = text_metrics(
            row["text_devanagari"], Path(row["text_path"]), vocab
        )
        all_phones.update(phones)
        all_patterns.update(patterns)
        all_meters.update(meters)
        issues = audio_issues(signal, int(row["sample_rate"]))
        if text["model_oov"]:
            issues.append("model_vocab_oov")
        for issue in sorted(set(issues)):
            issue_counts[issue] += 1
            issue_rows.append({"clip_id": row["clip_id"], "issue": issue})
        enriched.append(row | signal | text | {"analysis_issues": ";".join(sorted(set(issues)))})
        if number % 200 == 0:
            print(f"analyzed {number}/{len(source_rows)}", flush=True)

    out_csv = out_dir / "metadata_enriched.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(enriched[0]))
        writer.writeheader()
        writer.writerows(enriched)
    with (out_dir / "signal_issues.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["clip_id", "issue"])
        writer.writeheader()
        writer.writerows(issue_rows)

    coverage = {
        "phone_counts": dict(sorted(all_phones.items())),
        "phones_below_100": {p: all_phones[p] for p in sorted(SLP1_PHONES) if all_phones[p] < 100},
        "important_pattern_counts": dict(sorted(all_patterns.items())),
        "line_meter_counts": dict(all_meters.most_common()),
        "model_vocab_oov_characters": sorted(set("".join(row["model_oov"] for row in enriched))),
    }
    (out_dir / "coverage.json").write_text(json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "clips": len(enriched),
        "issue_counts": dict(sorted(issue_counts.items())),
        "peak_dbfs": {q: round(quantile(enriched, "peak_dbfs", v), 3) for q, v in (("p05", .05), ("p50", .5), ("p95", .95))},
        "rms_dbfs": {q: round(quantile(enriched, "rms_dbfs", v), 3) for q, v in (("p05", .05), ("p50", .5), ("p95", .95))},
        "leading_silence_s": {q: round(quantile(enriched, "leading_silence_s", v), 3) for q, v in (("p50", .5), ("p95", .95), ("p99", .99))},
        "trailing_silence_s": {q: round(quantile(enriched, "trailing_silence_s", v), 3) for q, v in (("p50", .5), ("p95", .95), ("p99", .99))},
        "stereo_correlation": {q: round(quantile(enriched, "stereo_correlation", v), 4) for q, v in (("p01", .01), ("p50", .5))},
    }
    (out_dir / "analysis_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
