# Narayaneeyam dataset audit

- Source: `/Users/shankararamasharma/Desktop/Vyoma Linguistic Labs/AI - AI Projects/Narayaneeyam`
- Paired clips: **1231**
- Total paired duration: **3.836 hours**
- Audio-only keys: **0**
- Text-only keys: **5**
- Duplicate audio keys: **0**
- Duplicate text keys: **0**
- Unparseable files: **0**

## Duration distribution

- Minimum: 6.878 s
- P50: 10.665 s
- P95: 16.063 s
- Maximum: 18.491 s

## Split counts

- train: 1109 clips
- validation: 60 clips
- test: 62 clips

## Issue counts

- sample_rate_below_24khz: 60
- unicode_control_character: 8

## Scope

This pass validates pairing, UTF-8/Devanagari text, FLAC headers, duration, and coarse text/audio ratios. It does not decode samples, so clipping, loudness, leading/trailing silence, SNR, and transcript/audio alignment remain pending.
