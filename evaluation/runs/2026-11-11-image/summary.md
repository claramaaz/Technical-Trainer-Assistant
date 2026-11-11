# Evaluation run `2026-11-11-image`

- Date (UTC): 2026-11-11 11:23; git commit: 1fff135
- Model: BAAI/bge-small-en-v1.5; threshold: 0.65; top 5
- Retrieval mode: image (image model clip-ViT-B-32, RRF k=60, 50 candidates per list)
- Questions: 50 (42 answerable, 8 no-answer)
- own = only the question's handbook; all = every searchable handbook

| Scope | Metric rule | Questions | Hit@1 | Hit@5 | MRR@5 |
| --- | --- | --- | --- | --- | --- |
| own | auto (expected figure) | 42 | 0.071 | 0.190 | 0.115 |
| own | human (scored 2) | 0 of 42 judged | n/a | n/a | n/a |
| all | auto (expected figure) | 42 | 0.048 | 0.143 | 0.080 |
| all | human (scored 2) | 0 of 42 judged | n/a | n/a | n/a |

| Scope | No-answer accuracy | Answerable questions refused by the threshold |
| --- | --- | --- |
| own | 7/8 | 3/42: Q018, Q026, Q031 |
| all | 6/8 | 2/42: Q018, Q026 |

Per question: rank of the expected figure (auto), '-' = not in the top 5; top-1 returned.

| Question | Type | Expected | own rank | all rank | all top-1 (score) |
| --- | --- | --- | --- | --- | --- |
| Q001 | topic | FAA-H-8083-15B 1-1 | - | - | FAA-H-8083-15B 4-10 (0.572) |
| Q002 | topic | FAA-H-8083-15B 3-3 | 4 | - | FAA-H-8083-25C 17-2 (0.660) |
| Q003 | topic | FAA-H-8083-15B 3-9 | - | - | FAA-H-8083-25C 14-13 (0.585) |
| Q004 | topic | FAA-H-8083-15B 4-2 | 4 | - | FAA-H-8083-25C 5-29 (0.758) |
| Q005 | topic | FAA-H-8083-15B 4-5 | 1 | 2 | FAA-H-8083-25C 11-14 (0.502) |
| Q006 | topic | FAA-H-8083-15B 4-7 | 1 | 1 | FAA-H-8083-15B 4-7 (0.605) |
| Q007 | topic | FAA-H-8083-15B 4-3 | - | - | FAA-H-8083-25C 5-10 (0.656) |
| Q008 | topic | FAA-H-8083-15B 5-7 | - | - | FAA-H-8083-15B 5-15 (0.534) |
| Q009 | topic | FAA-H-8083-15B 5-34 | - | - | FAA-H-8083-25C 9-3 (0.517) |
| Q010 | topic | FAA-H-8083-15B 7-52 | - | - | FAA-H-8083-25C 9-2 (0.604) |
| Q011 | topic | FAA-H-8083-15B 7-73 | - | - | FAA-H-8083-15B 5-49 (0.628) |
| Q012 | topic | FAA-H-8083-15B 9-1 | - | - | FAA-H-8083-25C 17-5 (0.547) |
| Q013 | topic | FAA-H-8083-15B 9-10 | - | - | FAA-H-8083-25C 5-60 (0.575) |
| Q014 | topic | FAA-H-8083-15B 9-17 | - | - | FAA-H-8083-25C 17-24 (0.550) |
| Q015 | topic | FAA-H-8083-15B 10-13 | - | - | FAA-H-8083-25C 5-10 (0.564) |
| Q016 | topic | FAA-H-8083-15B 10-17 | - | - | FAA-H-8083-25C 5-3 (0.686) |
| Q017 | topic | FAA-H-8083-15B 11-2 | - | - | FAA-H-8083-25C 5-22 (0.542) |
| Q018 | topic | FAA-H-8083-15B 11-11 | 2 | 5 | FAA-H-8083-25C 8-4 (0.452) |
| Q019 | topic | FAA-H-8083-15B 11-18 | - | - | FAA-H-8083-15B 2-4 (0.560) |
| Q020 | symptom | FAA-H-8083-15B 5-2 | - | - | FAA-H-8083-25C 9-2 (0.691) |
| Q021 | topic | FAA-H-8083-15B 5-40 | - | - | FAA-H-8083-15B 2-11 (0.594) |
| Q022 | symptom | FAA-H-8083-15B 5-20 | - | - | FAA-H-8083-25C 8-38 (0.649) |
| Q023 | symptom | FAA-H-8083-15B 7-39 | - | - | FAA-H-8083-15B 3-6 (0.506) |
| Q024 | no-answer | (no answer) | - | - | FAA-H-8083-15B 4-5 (0.431) |
| Q025 | no-answer | (no answer) | - | - | FAA-H-8083-15B 11-10 (0.527) |
| Q026 | symptom | FAA-H-8083-25C 7-11 | - | - | FAA-H-8083-25C 11-28 (0.562) |
| Q027 | symptom | FAA-H-8083-25C 7-21 | - | - | FAA-H-8083-25C 4-4 (0.535) |
| Q028 | symptom | FAA-H-8083-25C 8-11 | - | - | FAA-H-8083-15B 5-26 (0.574) |
| Q029 | symptom | FAA-H-8083-25C 8-22 | - | - | FAA-H-8083-15B 7-42 (0.642) |
| Q030 | symptom | FAA-H-8083-25C 17-5 | - | - | FAA-H-8083-15B 6-39 (0.516) |
| Q031 | symptom | FAA-H-8083-25C 12-17 | - | - | FAA-H-8083-15B 11-10 (0.440) |
| Q032 | symptom | FAA-H-8083-25C 5-17 | - | - | FAA-H-8083-25C 14-35 (0.554) |
| Q033 | symptom | FAA-H-8083-25C 6-5 | - | - | FAA-H-8083-25C 3-11 (0.529) |
| Q034 | symptom | FAA-H-8083-25C 5-51 | - | - | FAA-H-8083-25C 11-3 (0.537) |
| Q035 | topic | FAA-H-8083-25C 7-35 | - | - | FAA-H-8083-15B 11-4 (0.652) |
| Q036 | topic | FAA-H-8083-25C 14-30 | - | - | FAA-H-8083-15B 2-4 (0.472) |
| Q037 | topic | FAA-H-8083-25C 14-42 | - | - | FAA-H-8083-25C 16-38 (0.496) |
| Q038 | topic | FAA-H-8083-25C 14-38 | - | - | FAA-H-8083-25C 14-26 (0.645) |
| Q039 | topic | FAA-H-8083-25C 16-21 | - | - | FAA-H-8083-25C 11-32 (0.560) |
| Q040 | topic | FAA-H-8083-25C 10-3 | 1 | 1 | FAA-H-8083-25C 10-3 (0.791) |
| Q041 | topic | FAA-H-8083-25C 11-4 | 2 | 3 | FAA-H-8083-25C 4-3 (0.725) |
| Q042 | topic | FAA-H-8083-25C 12-28 | 3 | 3 | FAA-H-8083-25C 12-29 (0.703) |
| Q043 | topic | FAA-H-8083-25C 7-17 | - | - | FAA-H-8083-25C 8-1 (0.533) |
| Q044 | topic | FAA-H-8083-25C 5-55 | - | - | FAA-H-8083-15B 10-3 (0.499) |
| Q045 | no-answer | (no answer) | - | - | FAA-H-8083-25C 10-6 (0.408) |
| Q046 | no-answer | (no answer) | - | - | FAA-H-8083-25C 16-34 (0.503) |
| Q047 | no-answer | (no answer) | - | - | FAA-H-8083-15B 2-6 (0.623) |
| Q048 | no-answer | (no answer) | - | - | FAA-H-8083-25C 5-3 (0.460) |
| Q049 | no-answer | (no answer) | - | - | FAA-H-8083-15B 2-6 (0.568) |
| Q050 | no-answer | (no answer) | - | - | FAA-H-8083-15B 5-7 (0.440) |
