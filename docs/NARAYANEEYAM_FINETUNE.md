# Narayaneeyam voice fine-tune

This is the reproducible handoff for adapting Vāgdhenu to the Narayaneeyam
speaker. Source recordings remain in the sibling `Narayaneeyam/` directory and
are never modified by these steps.

## Current dataset

Run the structural and signal/frontend audits from the Vāgdhenu root:

```bash
python3 training/audit_narayaneeyam.py ../Narayaneeyam \
  --out data/narayaneeyam_audit

.audit-venv/bin/python training/analyze_narayaneeyam.py \
  data/narayaneeyam_audit/metadata.csv \
  --out data/narayaneeyam_audit

.audit-venv/bin/python training/prepare_narayaneeyam_indicf5.py \
  data/narayaneeyam_audit/metadata_enriched.csv \
  --out data/narayaneeyam_indicf5
```

Prepared sets:

| Set | Clips | Hours | Purpose |
|---|---:|---:|---|
| `all/train` | 1,109 | 3.489 | Main training arm |
| `high_bandwidth/train` | 1,049 | 3.302 | Excludes the 60 source clips below 24 kHz |
| `validation` | 60 | 0.196 | Daśakams 10, 30, 50 |
| `test` | 62 | 0.151 | Daśakams 20, 40, 60; final comparison only |

The split is by whole Daśakam, not random clip. This prevents two halves of the
same verse, and nearby recordings from the same session, leaking between train
and evaluation.

## Data findings

- Every audio file has a paired transcript.
- Five transcript-only files are excluded automatically.
- All model-normalized Kannada characters exist in the IndicF5 vocabulary.
- Difficult-cluster coverage includes `kṣ=305`, `jñ=39`, `tr=228`, and `dr=158`.
- There are no clipping, DC-offset, stereo-mismatch, or excessive-silence flags.
- Four files have 0.74–0.98 seconds of trailing silence. Keep them for the first
  smoke test; trimming is an ablation, not a source edit.
- Sixty files (Daśakams 15, 39, 47) are 16 kHz. IndicF5 can upsample them while
  loading, but they contain no information above 8 kHz. Compare the two training
  arms rather than assuming whether they help.

## Required GPU environment

Use Python 3.10, CUDA 12.1, PyTorch/torchaudio 2.4.1, and the repository's pinned
IndicF5 commit. The documented reference configuration is two 48 GB A6000 GPUs.
A single 48 GB GPU can be used with a smaller frame batch. CPU or Apple Silicon
training is not a useful path for this 337M-parameter DiT.

Copy both the source `Narayaneeyam/` tree and this repository to the GPU host
without changing their relative relationship. The Arrow files contain absolute
audio paths, so regenerate them on the GPU host after copying, or rewrite and
revalidate those paths there.

## Experiment order

1. Render a fixed zero-shot baseline using base IndicF5 and 6–10 clean speaker
   references from held-out Daśakams.
2. Run a 20-update training smoke test and render one held-out verse.
3. Fine-tune **Arm A from base IndicF5** on `all/train`.
4. Repeat Arm A on `high_bandwidth/train`; change no other parameter.
5. Only after choosing the better bandwidth arm, optionally run **Arm B from the
   Vāgdhenu chant checkpoint**. This may acquire chant behavior faster but risks
   retaining the original production speaker's identity.
6. Select checkpoints by blinded held-out listening, not training loss.
7. Keep `test/` sealed until learning rate, training duration, source arm, and
   inference settings are fixed.

## Starting training parameters

Use the settings demonstrated by this repository before tuning them:

- Kannada-routed text already stored in `raw.arrow`.
- Vocos 100-band mel, 24 kHz, hop 256.
- Learning rate `1e-5`.
- Frame batch `12,800` per GPU initially; raise only after measuring memory.
- BF16 mixed precision.
- Warmup 500 updates.
- Gradient norm 1.0.
- Save every 500 updates for this corpus; render the same validation suite at
  each save.
- Use EMA for the production candidate, while also evaluating non-EMA early in
  training because EMA can remain dominated by the warm start.

Example launch after the base warm checkpoint and tokenizer vocab are present:

```bash
accelerate launch --multi_gpu --num_processes 2 --mixed_precision bf16 \
  training/finetune_indicf5.py \
  --vocab /path/to/IndicF5/checkpoints/vocab.txt \
  --warm /path/to/grn-corrected-indicf5-warm.pt \
  --data_dir "$PWD/data/narayaneeyam_indicf5/all/train" \
  --save_dir /path/to/checkpoints/narayaneeyam_base_all \
  --wandb_name narayaneeyam_base_all \
  --lr 1e-5 --bs 12800 --warmup 500 --save_per 500
```

Do not launch the full run until the warm checkpoint loads with no unexpected
non-mel tensors and a generated held-out sample succeeds after the smoke test.

## Evaluation gate

For every candidate checkpoint, use identical reference audio, reference text,
target verses, seeds, CFG, NFE, speed, and BigVGAN checkpoint. Score separately:

- speaker identity;
- Sanskrit content and conjunct accuracy;
- long/short vowel timing;
- melodic and metrical delivery;
- omissions or repetitions;
- tremor, shimmer, and other audio artifacts.

The current BigVGAN should remain fixed during acoustic-model selection. Fine-
tune the vocoder only if the winning acoustic checkpoint has persistent waveform
artifacts that do not exist in its generated mel.
