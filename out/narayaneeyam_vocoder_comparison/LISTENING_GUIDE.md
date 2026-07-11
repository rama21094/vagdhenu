# Loudness-matched vocoder comparison

These files are normalized to the same −20 dBFS RMS target, with a −1 dBFS peak
ceiling. This removes the large playback-level difference between BigVGAN and
Vocos. Candidates C and D were selected because the previous listening notes
identified useful artifacts in them.

For each filename, compare:

1. `final`: gated and stitched BigVGAN output.
2. `raw_bigvgan`: BigVGAN before gating and stitching. Quarter silence is absent.
3. `vocos`: Vocos decode of the same generated mel. Quarter silence is absent.

Start with these reported cases:

- C / `eval_nar_010_002_1`: metallic sound near `हास्मि`.
- D / `eval_nar_010_008_1`: metallic ending at the quarter boundary.
- D / `eval_nar_050_002_1`: doubled/metallic `वृन्दावने त्वयि पावने`.

For each case, record which versions contain the artifact and which version has
the most natural speaker identity. Do not compare pause length in `raw_bigvgan`
or `vocos`, because those diagnostic files intentionally contain no inserted
quarter gap.

| Candidate/file | Final artifact? | Raw BigVGAN artifact? | Vocos artifact? | Best identity | Notes |
|---|---:|---:|---:|---|---|
| C / 010.2.1 | Yes| Yes| No, it clearly different | | |
| D / 010.8.1 | Very metallic and jarring around 'ca'| Very metallic and jarring around 'ca'| Very less artifact, best among three. | | But all three have very slight/minimal jarring all through. |
| D / 050.2.1 | Reduced from before, but still slgihtly there| Reduced from before, but still slgihtly there| No artifact. | | |

