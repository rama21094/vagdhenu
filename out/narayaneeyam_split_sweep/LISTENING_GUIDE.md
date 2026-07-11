# Quarter-boundary inference comparison

All candidates use checkpoint 8,000, CFG 3.0, the preferred reference from the
previous comparison for Dasakam 10, and the preferred Dasakam 50 reference.
Every half-verse is now rendered as two explicit metrical quarters.

In particular, `eval_nar_010_008_1` is split after `च`:

1. `धर्मादिकानभिसृजन्नथ कर्दमं च`
2. `वाणीं विधाय विधिरङ्गजसंकुलोऽभूत् ।`

## Primary listening pass

Listen only to directories `A` through `F` initially. Compare the same filename
across all candidates. Do not inspect `EXPERIMENT_KEY.md` before scoring.

| Candidate | Identity | Sanskrit | Boundary/pause | Metre/tune | Audio | Notes |
|---|---:|---:|---:|---:|---:|---|
| A | | | | | | eval_nar_010_002_1 - second quarter misses the firs syllable 'a'.|
| B | | | | | | |
| C | | | | | | eval_nar_010_002_1 - a metallic sound around the syllable 'haasmi'. Same for _raw also. But not there in _vocos.|
| D | | | | | | eval_nar_010_002_1 - The strongest voice and most identical to the speaker. But weird tune with intonations at unlikely places. eval_nar_010_008_1 - metallic sound at end of quarter. Both _raw and _vocos are better. eval_nar_050_002_1 - 'vRndaavane tvayi paavane', this has double or metallic. |
| E | | | | | | |
| F | | | | | | |

The tune for Vasantatilaka still doesn't sound like my standard tune.
Across candidates, the strength/amplitude of voice decreases for _raw and _vocos wherever I heard.

The identity has definitely improved across all candidates. 

It is getting difficult to distinguish between candidates in this iteration. Hence have not provided scores, only remarks.


Please record:

- Whether the pause in `010_008_1` is now at the correct word.
- Whether either quarter loses or repeats a syllable.
- Best candidate for Dasakam 10 and for Dasakam 50.
- Whether the doubled opening voice or electronic/metallic sound remains.

## Artifact diagnosis

Only for a file with doubled voice or electronic noise, compare these versions:

- `X/<file>.wav`: final gated and stitched BigVGAN output.
- `X_raw/<file>_raw.wav`: ungated BigVGAN output. It intentionally omits the
  inserted inter-quarter silence, so judge timbre rather than pause length.
- `X_vocos/<file>_vocos.wav`: Vocos decode from the same generated mel.

Interpretation:

- Artifact in both BigVGAN and Vocos: it originates in the generated mel/model.
- Artifact in BigVGAN but absent from Vocos: BigVGAN is introducing it.
- Artifact only in the final file, absent from `raw`: gating/stitching is the cause.

