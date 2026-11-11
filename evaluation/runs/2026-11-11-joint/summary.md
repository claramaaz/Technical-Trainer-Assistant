# Evaluation run `2026-11-11-joint`

- Date (UTC): 2026-11-11 11:25; git commit: 1fff135
- Model: BAAI/bge-small-en-v1.5; threshold: 0.65; top 5
- Retrieval mode: joint (image model clip-ViT-B-32, RRF k=60, 50 candidates per list)
- Questions: 50 (42 answerable, 8 no-answer)
- own = only the question's handbook; all = every searchable handbook

| Scope | Metric rule | Questions | Hit@1 | Hit@5 | MRR@5 |
| --- | --- | --- | --- | --- | --- |
| own | auto (expected figure) | 42 | 0.167 | 0.381 | 0.260 |
| own | human (scored 2) | 0 of 42 judged | n/a | n/a | n/a |
| all | auto (expected figure) | 42 | 0.167 | 0.381 | 0.238 |
| all | human (scored 2) | 0 of 42 judged | n/a | n/a | n/a |

| Scope | No-answer accuracy | Answerable questions refused by the threshold |
| --- | --- | --- |
| own | 7/8 | 3/42: Q018, Q026, Q031 |
| all | 6/8 | 2/42: Q018, Q026 |

Per question: rank of the expected figure (auto), '-' = not in the top 5; top-1 returned.

| Question | Type | Expected | own rank | all rank | all top-1 (score) |
| --- | --- | --- | --- | --- | --- |
| Q001 | topic | FAA-H-8083-15B 1-1 | - | - | FAA-H-8083-25C 6-4 (0.646) |
| Q002 | topic | FAA-H-8083-15B 3-3 | 2 | 4 | FAA-H-8083-15B 3-4 (0.740) |
| Q003 | topic | FAA-H-8083-15B 3-9 | 2 | - | FAA-H-8083-25C 14-33 (0.635) |
| Q004 | topic | FAA-H-8083-15B 4-2 | 2 | 2 | FAA-H-8083-25C 5-29 (0.758) |
| Q005 | topic | FAA-H-8083-15B 4-5 | 1 | 1 | FAA-H-8083-15B 4-5 (0.714) |
| Q006 | topic | FAA-H-8083-15B 4-7 | 5 | 5 | FAA-H-8083-25C 4-3 (0.694) |
| Q007 | topic | FAA-H-8083-15B 4-3 | 1 | 1 | FAA-H-8083-15B 4-3 (0.845) |
| Q008 | topic | FAA-H-8083-15B 5-7 | - | - | FAA-H-8083-25C 17-19 (0.625) |
| Q009 | topic | FAA-H-8083-15B 5-34 | - | - | FAA-H-8083-25C 5-56 (0.729) |
| Q010 | topic | FAA-H-8083-15B 7-52 | - | - | FAA-H-8083-15B 6-5 (0.738) |
| Q011 | topic | FAA-H-8083-15B 7-73 | 1 | 1 | FAA-H-8083-15B 7-73 (0.729) |
| Q012 | topic | FAA-H-8083-15B 9-1 | - | - | FAA-H-8083-15B 5-48 (0.712) |
| Q013 | topic | FAA-H-8083-15B 9-10 | - | - | FAA-H-8083-25C 16-32 (0.700) |
| Q014 | topic | FAA-H-8083-15B 9-17 | - | - | FAA-H-8083-25C 16-32 (0.664) |
| Q015 | topic | FAA-H-8083-15B 10-13 | - | - | FAA-H-8083-15B 10-12 (0.703) |
| Q016 | topic | FAA-H-8083-15B 10-17 | 2 | - | FAA-H-8083-25C 16-17 (0.714) |
| Q017 | topic | FAA-H-8083-15B 11-2 | - | - | FAA-H-8083-25C 5-21 (0.599) |
| Q018 | topic | FAA-H-8083-15B 11-11 | 2 | 2 | FAA-H-8083-25C 14-54 (0.592) |
| Q019 | topic | FAA-H-8083-15B 11-18 | - | 4 | FAA-H-8083-15B 11-10 (0.640) |
| Q020 | symptom | FAA-H-8083-15B 5-2 | - | - | FAA-H-8083-15B 7-15 (0.701) |
| Q021 | topic | FAA-H-8083-15B 5-40 | 1 | 1 | FAA-H-8083-15B 5-40 (0.911) |
| Q022 | symptom | FAA-H-8083-15B 5-20 | - | - | FAA-H-8083-25C 16-30 (0.669) |
| Q023 | symptom | FAA-H-8083-15B 7-39 | - | 4 | FAA-H-8083-25C 2-4 (0.605) |
| Q024 | no-answer | (no answer) | - | - | FAA-H-8083-25C 1-24 (0.610) |
| Q025 | no-answer | (no answer) | - | - | FAA-H-8083-15B 11-7 (0.590) |
| Q026 | symptom | FAA-H-8083-25C 7-11 | - | - | FAA-H-8083-25C 7-8 (0.567) |
| Q027 | symptom | FAA-H-8083-25C 7-21 | - | - | FAA-H-8083-25C 7-12 (0.593) |
| Q028 | symptom | FAA-H-8083-25C 8-11 | - | - | FAA-H-8083-15B 5-10 (0.697) |
| Q029 | symptom | FAA-H-8083-25C 8-22 | 2 | 3 | FAA-H-8083-15B 7-42 (0.642) |
| Q030 | symptom | FAA-H-8083-25C 17-5 | - | - | FAA-H-8083-15B 10-14 (0.638) |
| Q031 | symptom | FAA-H-8083-25C 12-17 | - | - | FAA-H-8083-15B 7-15 (0.614) |
| Q032 | symptom | FAA-H-8083-25C 5-17 | - | - | FAA-H-8083-25C 12-12 (0.665) |
| Q033 | symptom | FAA-H-8083-25C 6-5 | 5 | 5 | FAA-H-8083-25C 6-8 (0.714) |
| Q034 | symptom | FAA-H-8083-25C 5-51 | - | - | FAA-H-8083-25C 5-28 (0.641) |
| Q035 | topic | FAA-H-8083-25C 7-35 | 1 | 2 | FAA-H-8083-15B 11-4 (0.652) |
| Q036 | topic | FAA-H-8083-25C 14-30 | - | - | FAA-H-8083-25C 14-36 (0.630) |
| Q037 | topic | FAA-H-8083-25C 14-42 | - | - | FAA-H-8083-25C 1-7 (0.627) |
| Q038 | topic | FAA-H-8083-25C 14-38 | - | - | FAA-H-8083-25C 14-11 (0.674) |
| Q039 | topic | FAA-H-8083-25C 16-21 | - | - | FAA-H-8083-25C 16-22 (0.746) |
| Q040 | topic | FAA-H-8083-25C 10-3 | 1 | 1 | FAA-H-8083-25C 10-3 (0.791) |
| Q041 | topic | FAA-H-8083-25C 11-4 | 1 | 1 | FAA-H-8083-25C 11-4 (0.809) |
| Q042 | topic | FAA-H-8083-25C 12-28 | 2 | 1 | FAA-H-8083-25C 12-28 (0.764) |
| Q043 | topic | FAA-H-8083-25C 7-17 | - | - | FAA-H-8083-25C 7-10 (0.654) |
| Q044 | topic | FAA-H-8083-25C 5-55 | - | - | FAA-H-8083-15B 9-15 (0.610) |
| Q045 | no-answer | (no answer) | - | - | FAA-H-8083-25C 7-4 (0.601) |
| Q046 | no-answer | (no answer) | - | - | FAA-H-8083-15B 10-15 (0.651) |
| Q047 | no-answer | (no answer) | - | - | FAA-H-8083-15B 2-6 (0.623) |
| Q048 | no-answer | (no answer) | - | - | FAA-H-8083-15B 4-11 (0.548) |
| Q049 | no-answer | (no answer) | - | - | FAA-H-8083-15B 2-6 (0.568) |
| Q050 | no-answer | (no answer) | - | - | FAA-H-8083-25C 16-26 (0.510) |
