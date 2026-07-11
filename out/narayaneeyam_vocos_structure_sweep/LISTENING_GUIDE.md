# Vocos: whole-half versus explicit-quarter comparison

Every candidate uses checkpoint 8,000, CFG 3.0, and Vocos as the final vocoder.
Vasantatilakā now uses R03 (`nar_008_003_1`), a clean first-half recording with
the standard tune. Dasakam 50 uses its preferred first-half reference `50.3.1`.

The candidates conceal two generation structures and three random seeds. Compare
the same filename across A through F before inspecting `EXPERIMENT_KEY.md`.

## What decides the winner

For Dasakam 10, first decide whether the standard Vasantatilakā tune now transfers.
Then judge whether the quarter boundary occurs naturally and whether any initial
or final syllable is lost, repeated, or distorted.

For `eval_nar_010_008_1`, the expected boundary is after `च`:

`धर्मादिकानभिसृजन्नथ कर्दमं च | वाणीं विधाय विधिरङ्गजसंकुलोऽभूत्`

| Candidate | Standard tune | Correct boundary | Complete Sanskrit | Identity | Audio | Notes |
|---|---:|---:|---:|---:|---:|---|
| A | |eval_nar_050_ - No for both | | | | eval_nar_010_002_1 - the visarga is rendered badly at the end of first quarter. eval_nar_010_008_1 - split before 'ca'.|
| B | |yes | | | | Best splitting. Not considering the tune of vasantatilaka, this seems to be the best of the lot.|
| C | |No. Correct for eval_nar_050_008_1 | | | |eval_nar_010_002_1 - till "mithyaa grahaa" the tune is correct. eval_nar_010_008_1 - tune correct till "dharmaadhikaanabhi", but stops at 'tha'|
| D | | yes| | | | eval_nar_010_008_1 - 'ca' is pulled longer than needed.|
| E | |No. This candidate seems to be joining both pada-s. Not wrong, bit not necessary.| | | | eval_nar_010_002_1 - seems like double visarga. Second quarter end has metallic sound. eval_nar_010_008_1 - pauses at 'vaaNiim'|
| F | | | | | | eval_nar_010_002_1 - seems like double visarga. eval_nar_010_008_1 - two pauses, one after 'tha' and other correctly after 'ca'.|

Please report:

- Best candidate and runner-up for Dasakam 10 - no one is satisfying
- Best candidate for Dasakam 50 - all are similar. Specific comments are given above.
- Whether the correct reference fixes the Vasantatilakā tune - none of them are correct. They seem to have gotten worse.
- Whether the best result pauses correctly without losing a boundary syllable - no recording loses a boundary syllable per se.
- Any remaining metallic, doubled, or continuously jarring sound - nothing very recognisable. Maybe a better recorded dataset will make the voice more natural.

