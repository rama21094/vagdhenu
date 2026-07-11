#!/usr/bin/env python3
"""Inventory and audit a paired Narayaneeyam FLAC/text corpus.

The source tree is treated as read-only. Files are paired by the final three
numeric components in their names (dasakam, verse, half), deliberately ignoring
the common Dasakam/Dashakam spelling mismatch.

Only the Python standard library is required. FLAC STREAMINFO is parsed directly
to obtain sample rate, channel count, bit depth, sample count, and duration.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import struct
import unicodedata
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path


# Accept the filename punctuation variants present in the corpus, including
# "5.10 .1", "38.5,1", "47 .1.1", and "54,5,2".
KEY_RE = re.compile(r"(?<!\d)(\d+)\s*[.,]\s*(\d+)\s*[.,]\s*(\d+)(?!\d)")
DEVA_RE = re.compile(r"[\u0900-\u097f]")
DROP_FOR_MODEL_RE = re.compile(r"[।॥|/\\\"“”‘’\[\]{}()<>०-९0-9,:;!?…]+")


@dataclass(frozen=True, order=True)
class ClipKey:
    dasakam: int
    verse: int
    half: int

    @property
    def clip_id(self) -> str:
        return f"nar_{self.dasakam:03d}_{self.verse:03d}_{self.half}"


@dataclass
class FlacInfo:
    sample_rate: int
    channels: int
    bit_depth: int
    total_samples: int
    duration_s: float


def key_from_path(path: Path) -> ClipKey | None:
    matches = list(KEY_RE.finditer(path.stem))
    if not matches:
        return None
    d, v, h = map(int, matches[-1].groups())
    return ClipKey(d, v, h)


def read_flac_streaminfo(path: Path) -> FlacInfo:
    with path.open("rb") as handle:
        if handle.read(4) != b"fLaC":
            raise ValueError("missing FLAC signature")
        while True:
            header = handle.read(4)
            if len(header) != 4:
                raise ValueError("truncated FLAC metadata")
            is_last = bool(header[0] & 0x80)
            block_type = header[0] & 0x7F
            length = int.from_bytes(header[1:4], "big")
            payload = handle.read(length)
            if len(payload) != length:
                raise ValueError("truncated FLAC metadata block")
            if block_type == 0:
                if length != 34:
                    raise ValueError(f"invalid STREAMINFO length {length}")
                packed = int.from_bytes(payload[10:18], "big")
                sample_rate = (packed >> 44) & 0xFFFFF
                channels = ((packed >> 41) & 0x7) + 1
                bit_depth = ((packed >> 36) & 0x1F) + 1
                total_samples = packed & ((1 << 36) - 1)
                if not sample_rate:
                    raise ValueError("zero sample rate")
                return FlacInfo(
                    sample_rate=sample_rate,
                    channels=channels,
                    bit_depth=bit_depth,
                    total_samples=total_samples,
                    duration_s=total_samples / sample_rate,
                )
            if is_last:
                raise ValueError("STREAMINFO block not found")


def read_text(path: Path) -> tuple[str, list[str]]:
    issues: list[str] = []
    raw = path.read_bytes()
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        decoded = raw.decode("utf-8-sig", errors="replace")
        issues.append("invalid_utf8")
    text = unicodedata.normalize("NFC", decoded)
    text = " ".join(text.replace("\r", "\n").split())
    if not text:
        issues.append("empty_transcript")
        return text, issues
    if "\ufffd" in text:
        issues.append("replacement_character")
    visible = [c for c in text if not c.isspace()]
    deva_fraction = sum(bool(DEVA_RE.match(c)) for c in visible) / max(1, len(visible))
    if deva_fraction < 0.75:
        issues.append("low_devanagari_fraction")
    controls = [c for c in text if unicodedata.category(c) in {"Cc", "Cf"}]
    if controls:
        issues.append("unicode_control_character")
    return text, issues


def model_character_count(text: str) -> int:
    return len(DROP_FOR_MODEL_RE.sub("", text).replace(" ", ""))


def choose_split(dasakam: int) -> str:
    """Stable, session-like split by whole Dasakam: 54/3/3 for Dasakams 1..60."""
    if dasakam in {10, 30, 50}:
        return "validation"
    if dasakam in {20, 40, 60}:
        return "test"
    return "train"


def index_files(root: Path, suffix: str) -> tuple[dict[ClipKey, Path], list[dict], list[str]]:
    grouped: dict[ClipKey, list[Path]] = defaultdict(list)
    unparsed: list[str] = []
    for path in sorted(root.rglob(f"*{suffix}")):
        key = key_from_path(path)
        if key is None:
            unparsed.append(str(path.resolve()))
        else:
            grouped[key].append(path)
    duplicates = [
        {
            "clip_id": key.clip_id,
            "selected_path": str(select_preferred_path(key, paths).resolve()),
            "paths": [str(p.resolve()) for p in paths],
        }
        for key, paths in grouped.items()
        if len(paths) > 1
    ]
    # Keep one deterministic canonical candidate in the manifest while retaining
    # the duplicate warning for manual listening. Prefer the regular dotted ID.
    unique = {key: select_preferred_path(key, paths) for key, paths in grouped.items()}
    return unique, duplicates, unparsed


def select_preferred_path(key: ClipKey, paths: list[Path]) -> Path:
    dotted = f"{key.dasakam}.{key.verse}.{key.half}"
    exact = [path for path in paths if dotted in path.stem]
    return sorted(exact or paths)[0]


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def write_report(out_dir: Path, summary: dict, issue_counts: Counter, rows: list[dict]) -> None:
    durations = [row["duration_s"] for row in rows]
    split_counts = Counter(row["split"] for row in rows)
    report = [
        "# Narayaneeyam dataset audit",
        "",
        f"- Source: `{summary['source_root']}`",
        f"- Paired clips: **{summary['paired_clips']}**",
        f"- Total paired duration: **{summary['total_hours']:.3f} hours**",
        f"- Audio-only keys: **{summary['audio_without_text']}**",
        f"- Text-only keys: **{summary['text_without_audio']}**",
        f"- Duplicate audio keys: **{summary['duplicate_audio_keys']}**",
        f"- Duplicate text keys: **{summary['duplicate_text_keys']}**",
        f"- Unparseable files: **{summary['unparseable_files']}**",
        "",
        "## Duration distribution",
        "",
        f"- Minimum: {min(durations, default=0):.3f} s",
        f"- P50: {percentile(durations, 0.50):.3f} s",
        f"- P95: {percentile(durations, 0.95):.3f} s",
        f"- Maximum: {max(durations, default=0):.3f} s",
        "",
        "## Split counts",
        "",
    ]
    for name in ("train", "validation", "test"):
        report.append(f"- {name}: {split_counts[name]} clips")
    report.extend(["", "## Issue counts", ""])
    if issue_counts:
        for issue, count in sorted(issue_counts.items()):
            report.append(f"- {issue}: {count}")
    else:
        report.append("- None detected by the structural audit.")
    report.extend(
        [
            "",
            "## Scope",
            "",
            "This pass validates pairing, UTF-8/Devanagari text, FLAC headers, duration, and "
            "coarse text/audio ratios. It does not decode samples, so clipping, loudness, "
            "leading/trailing silence, SNR, and transcript/audio alignment remain pending.",
            "",
        ]
    )
    (out_dir / "AUDIT.md").write_text("\n".join(report), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="Narayaneeyam source directory")
    parser.add_argument("--out", type=Path, default=Path("data/narayaneeyam_audit"))
    args = parser.parse_args()

    root = args.source.expanduser().resolve()
    out_dir = args.out.expanduser().resolve()
    if not root.is_dir():
        parser.error(f"source directory does not exist: {root}")
    out_dir.mkdir(parents=True, exist_ok=True)

    audios, duplicate_audios, unparsed_audios = index_files(root, ".flac")
    texts, duplicate_texts, unparsed_texts = index_files(root, ".txt")
    paired_keys = sorted(audios.keys() & texts.keys())
    audio_only = sorted(audios.keys() - texts.keys())
    text_only = sorted(texts.keys() - audios.keys())

    rows: list[dict] = []
    issues: list[dict] = []
    issue_counts: Counter = Counter()
    for key in paired_keys:
        audio_path = audios[key]
        text_path = texts[key]
        clip_issues: list[str] = []
        try:
            info = read_flac_streaminfo(audio_path)
        except (OSError, ValueError, struct.error) as exc:
            clip_issues.append("invalid_flac")
            info = FlacInfo(0, 0, 0, 0, 0.0)
            issues.append({"clip_id": key.clip_id, "issue": "invalid_flac", "detail": str(exc)})

        text, text_issues = read_text(text_path)
        clip_issues.extend(text_issues)
        char_count = model_character_count(text)
        chars_per_s = char_count / info.duration_s if info.duration_s else 0.0
        if info.duration_s < 1.0:
            clip_issues.append("duration_below_1s")
        if info.duration_s > 30.0:
            clip_issues.append("duration_above_30s")
        if info.sample_rate and info.sample_rate < 24_000:
            clip_issues.append("sample_rate_below_24khz")
        if chars_per_s and not 1.0 <= chars_per_s <= 12.0:
            clip_issues.append("suspicious_text_audio_ratio")

        for issue in sorted(set(clip_issues)):
            issue_counts[issue] += 1
            if not (issue == "invalid_flac" and any(i["clip_id"] == key.clip_id for i in issues)):
                issues.append({"clip_id": key.clip_id, "issue": issue, "detail": ""})

        rows.append(
            {
                "clip_id": key.clip_id,
                "dasakam": key.dasakam,
                "verse": key.verse,
                "half": key.half,
                "split": choose_split(key.dasakam),
                "audio_path": str(audio_path.resolve()),
                "text_path": str(text_path.resolve()),
                "text_devanagari": text,
                "duration_s": round(info.duration_s, 6),
                "sample_rate": info.sample_rate,
                "channels": info.channels,
                "bit_depth": info.bit_depth,
                "model_characters": char_count,
                "characters_per_s": round(chars_per_s, 4),
                "issues": ";".join(sorted(set(clip_issues))),
            }
        )

    fieldnames = list(rows[0].keys()) if rows else ["clip_id"]
    with (out_dir / "metadata.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    with (out_dir / "metadata.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    structural = {
        "audio_without_text": [asdict(k) | {"clip_id": k.clip_id, "path": str(audios[k].resolve())} for k in audio_only],
        "text_without_audio": [asdict(k) | {"clip_id": k.clip_id, "path": str(texts[k].resolve())} for k in text_only],
        "duplicate_audio_keys": duplicate_audios,
        "duplicate_text_keys": duplicate_texts,
        "unparseable_audio_paths": unparsed_audios,
        "unparseable_text_paths": unparsed_texts,
    }
    (out_dir / "structural_issues.json").write_text(
        json.dumps(structural, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (out_dir / "clip_issues.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["clip_id", "issue", "detail"])
        writer.writeheader()
        writer.writerows(issues)

    summary = {
        "source_root": str(root),
        "source_fingerprint": hashlib.sha256(str(root).encode()).hexdigest()[:16],
        "audio_files": len(audios) + sum(len(item["paths"]) - 1 for item in duplicate_audios),
        "text_files": len(texts) + sum(len(item["paths"]) - 1 for item in duplicate_texts),
        "paired_clips": len(rows),
        "total_hours": sum(row["duration_s"] for row in rows) / 3600,
        "audio_without_text": len(audio_only),
        "text_without_audio": len(text_only),
        "duplicate_audio_keys": len(duplicate_audios),
        "duplicate_text_keys": len(duplicate_texts),
        "unparseable_files": len(unparsed_audios) + len(unparsed_texts),
        "issue_counts": dict(sorted(issue_counts.items())),
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_report(out_dir, summary, issue_counts, rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if duplicate_audios or duplicate_texts or unparsed_audios or unparsed_texts else 0


if __name__ == "__main__":
    raise SystemExit(main())
