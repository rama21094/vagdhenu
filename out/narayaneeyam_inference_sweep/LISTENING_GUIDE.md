# Corrected-inference blind comparison

All six candidates use checkpoint 8,000. This comparison changes only inference
conditions: duration, random seed, guidance strength, and/or target-speaker
reference recording.

The Dasakam 10 duration has been corrected from roughly 7 seconds to roughly
11 seconds. Dasakam 50 has also been brought closer to the source recordings.

## How to listen

Compare the same filename across A through F before moving to the next file.
Use headphones if possible. Do not inspect `EXPERIMENT_KEY.md` or the JSON/log
files until you have selected a preferred candidate and runner-up.

Pay particular attention to:

1. Whether the doubled/overlapping voice in Dasakam 10 has disappeared.
2. Whether `eval_nar_010_008_1` now contains every syllable.
3. Whether pauses and cadence occur at metrically sensible positions.
4. Whether Dasakam 50 follows a convincing tune rather than merely speaking
   the Sanskrit clearly.
5. Any tremor, metallic texture, pitch instability, repeated sounds, or dropped
   sounds.

| Candidate | Identity | Sanskrit | Metre/tune | Audio | Notes |
|---|---:|---:|---:|---:|---|
| A | 2| 1| 2| 2|10 is Vasantatilaka and a very common metre in the dataset. The tune is not good enough across any candidate. |
| B | 2| 2| 2| 2| |
| C | 2| 2| 1| 1| eval_nar_050_002_1, at the end of the lines there seems to be two voices. And some elctronic jazz like background noise. This comes in few other candidates, but is most prominent here.|
| D |3 |4 |3 |3 | This is second best. For 50, this is best.|
| E |4 |4 |3 |3 |Best among the candidates. Most others have a metallic sound or some overlapping sound for the speaker on 10. This sounds good. Here too while ausio on 10 begins, the first cuple of words seem to have overlapped voice and then becomes better. |
| F | 2.5|3 |3 |2 | eval_nar_010_008_1, some rpeat of syllable and extra pause before last letter etc.|

eval_nar_010_008_1 - In all candidates, the pausing after quarter is wrongly split. It should stop after 'ca'. But it stops before that or after the next word.
50 is a very unique dasakam. Maybe it should be in training. But it is heartening to see the performance on a completely outlier data. 

Also record the best candidate separately for Dasakam 10 and Dasakam 50; the
best inference condition may differ by metre.

