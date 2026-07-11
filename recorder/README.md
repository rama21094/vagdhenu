# Vāgdhenu Recording Studio

A local, dependency-free recording interface for creating clean quarter-level
Sanskrit speech datasets on macOS. Audio is captured in the browser, converted
to mono 24 kHz PCM WAV, quality-checked, and stored with immutable take metadata.

## Start on macOS

From the repository root:

```bash
python3 recorder/server.py
```

Open <http://127.0.0.1:8765> in Chrome, Edge, or Safari and allow microphone
access. Chrome or Edge is recommended for the most predictable recorder support.

To keep the dataset somewhere else:

```bash
python3 recorder/server.py --data-dir "$HOME/VagdhenuRecordings"
```

The server binds only to `127.0.0.1` by default. Stop it with `Ctrl-C`.

## Recording workflow

1. Select the microphone in Settings.
2. Read the displayed quarter and leave a short natural decay at the end.
3. Stop and listen to the take.
4. Check duration, peak, RMS, clipping, and silence warnings.
5. Accept and advance, save for later review, or discard and retake.

Keyboard shortcuts: `R` starts/stops, Space plays the pending take, and Enter
accepts it and advances.

Every retake is retained as `take_001.wav`, `take_002.wav`, and so on. The latest
accepted take is referenced in `metadata.jsonl` and `metadata.csv`; old takes are
never silently overwritten.

## Dataset layout

```text
recorder_data/projects/narayaneeyam/
├── project.json
├── progress.json
├── metadata.jsonl
├── metadata.csv
└── audio/
    └── nar_001_001_1_q1/
        ├── take_001.wav
        └── take_001.json
```

WAV output is mono, 24 kHz, signed 16-bit PCM. Each JSON sidecar records text,
position, metre, microphone, timestamp, notes, and objective signal measurements.

## Import another work

Choose **Import script**, enter a collection name, and paste one quarter per
non-empty line. Daṇḍas may remain at line endings. Comment lines beginning with
`#` are ignored. The importer groups every four lines into one verse while each
line remains an independent recording item.

## Reliability recommendations

- Use the same microphone, room, distance, input gain, and posture for a session.
- Disable voice isolation, noise suppression, and automatic gain where macOS or
  the device exposes those controls.
- Aim for peaks between −12 and −1 dBFS and zero clipped samples.
- Retake interruptions, network artifacts, metallic sounds, trailing voice,
  pronunciation errors, and unusual tune or tempo.
- Record first/second-half and metre-specific canonical references explicitly;
  do not assume their melodic contours are interchangeable.
- Back up the entire data directory, including rejected and earlier takes.

## Rebuild the bundled Narayaneeyam script

If the audited metadata changes:

```bash
PYTHONPATH=. python3 recorder/build_default_dataset.py
```

This derives two quarter items from every paired half-verse. Ambiguous automatic
splits are retained with `split_exact: false` so they can be reviewed manually.
