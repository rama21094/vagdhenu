# Experiment key — inspect only after scoring

Every candidate uses the full-data checkpoint at step 8,000, BigVGAN, NFE 64,
and corrected seconds-per-syllable values of 0.42 for Dasakam 10 and 0.39 for
Dasakam 50.

| Candidate | Seed | CFG | D10 reference | D50 reference | Purpose |
|---|---:|---:|---|---|---|
| A | 50 | 3.0 | 10.1.1 | 50.1.1 | Seed comparison |
| B | 63 | 3.0 | 10.1.1 | 50.1.1 | Corrected baseline |
| C | 63 | 4.0 | 10.1.1 | 50.1.1 | Stronger guidance |
| D | 63 | 3.0 | 6.3.1 | 50.3.1 | Alternate matched references |
| E | 63 | 3.0 | 43.7.2 | 50.7.1 | Alternate matched references |
| F | 63 | 2.0 | 10.1.1 | 50.1.1 | Weaker guidance |

