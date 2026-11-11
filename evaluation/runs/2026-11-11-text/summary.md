# Evaluation run `2026-11-11-text`

- Date (UTC): 2026-11-11 11:20; git commit: 1fff135
- Model: BAAI/bge-small-en-v1.5; threshold: 0.65; top 5
- Retrieval mode: text
- Questions: 50 (42 answerable, 8 no-answer)
- own = only the question's handbook; all = every searchable handbook

| Scope | Metric rule | Questions | Hit@1 | Hit@5 | MRR@5 |
| --- | --- | --- | --- | --- | --- |
| own | auto (expected figure) | 42 | 0.643 | 0.833 | 0.720 |
| own | human (scored 2) | 0 of 42 judged | n/a | n/a | n/a |
| all | auto (expected figure) | 42 | 0.524 | 0.786 | 0.639 |
| all | human (scored 2) | 0 of 42 judged | n/a | n/a | n/a |

| Scope | No-answer accuracy | Answerable questions refused by the threshold |
| --- | --- | --- |
| own | 7/8 | 3/42: Q018, Q026, Q031 |
| all | 6/8 | 2/42: Q018, Q026 |

Per question: rank of the expected figure (auto), '-' = not in the top 5; top-1 returned.

| Question | Type | Expected | own rank | all rank | all top-1 (score) |
| --- | --- | --- | --- | --- | --- |
| Q001 | topic | FAA-H-8083-15B 1-1 | 1 | 2 | FAA-H-8083-25C 15-1 (0.793) |
| Q002 | topic | FAA-H-8083-15B 3-3 | 1 | 1 | FAA-H-8083-15B 3-3 (0.747) |
| Q003 | topic | FAA-H-8083-15B 3-9 | 1 | 2 | FAA-H-8083-25C 17-7 (0.875) |
| Q004 | topic | FAA-H-8083-15B 4-2 | 1 | 2 | FAA-H-8083-25C 4-7 (0.784) |
| Q005 | topic | FAA-H-8083-15B 4-5 | 1 | 1 | FAA-H-8083-15B 4-5 (0.714) |
| Q006 | topic | FAA-H-8083-15B 4-7 | - | - | FAA-H-8083-25C 11-13 (0.792) |
| Q007 | topic | FAA-H-8083-15B 4-3 | 1 | 1 | FAA-H-8083-15B 4-3 (0.845) |
| Q008 | topic | FAA-H-8083-15B 5-7 | 1 | 2 | FAA-H-8083-25C 15-8 (0.684) |
| Q009 | topic | FAA-H-8083-15B 5-34 | 1 | 1 | FAA-H-8083-15B 5-34 (0.808) |
| Q010 | topic | FAA-H-8083-15B 7-52 | 1 | 1 | FAA-H-8083-15B 7-52 (0.809) |
| Q011 | topic | FAA-H-8083-15B 7-73 | 4 | 4 | FAA-H-8083-15B 11-3 (0.754) |
| Q012 | topic | FAA-H-8083-15B 9-1 | 2 | 2 | FAA-H-8083-15B 2-1 (0.737) |
| Q013 | topic | FAA-H-8083-15B 9-10 | 1 | 1 | FAA-H-8083-15B 9-10 (0.772) |
| Q014 | topic | FAA-H-8083-15B 9-17 | 2 | 2 | FAA-H-8083-15B 9-19 (0.827) |
| Q015 | topic | FAA-H-8083-15B 10-13 | 3 | 3 | FAA-H-8083-15B 7-45 (0.744) |
| Q016 | topic | FAA-H-8083-15B 10-17 | 2 | - | FAA-H-8083-25C 11-19 (0.836) |
| Q017 | topic | FAA-H-8083-15B 11-2 | 1 | 1 | FAA-H-8083-15B 11-2 (0.653) |
| Q018 | topic | FAA-H-8083-15B 11-11 | - | - | FAA-H-8083-25C 2-18 (0.641) |
| Q019 | topic | FAA-H-8083-15B 11-18 | 1 | 1 | FAA-H-8083-15B 11-18 (0.840) |
| Q020 | symptom | FAA-H-8083-15B 5-2 | - | - | FAA-H-8083-15B 6-8 (0.767) |
| Q021 | topic | FAA-H-8083-15B 5-40 | 1 | 1 | FAA-H-8083-15B 5-40 (0.911) |
| Q022 | symptom | FAA-H-8083-15B 5-20 | 1 | 1 | FAA-H-8083-15B 5-20 (0.794) |
| Q023 | symptom | FAA-H-8083-15B 7-39 | 1 | 1 | FAA-H-8083-15B 7-39 (0.843) |
| Q024 | no-answer | (no answer) | - | - | FAA-H-8083-25C 11-11 (0.614) |
| Q025 | no-answer | (no answer) | - | - | FAA-H-8083-15B 5-37 (0.626) |
| Q026 | symptom | FAA-H-8083-25C 7-11 | 3 | 4 | FAA-H-8083-25C 12-12 (0.609) |
| Q027 | symptom | FAA-H-8083-25C 7-21 | 1 | 1 | FAA-H-8083-25C 7-21 (0.694) |
| Q028 | symptom | FAA-H-8083-25C 8-11 | 1 | 2 | FAA-H-8083-15B 6-8 (0.729) |
| Q029 | symptom | FAA-H-8083-25C 8-22 | 1 | 1 | FAA-H-8083-25C 8-22 (0.788) |
| Q030 | symptom | FAA-H-8083-25C 17-5 | 3 | - | FAA-H-8083-15B 7-7 (0.733) |
| Q031 | symptom | FAA-H-8083-25C 12-17 | - | - | FAA-H-8083-15B 7-21 (0.657) |
| Q032 | symptom | FAA-H-8083-25C 5-17 | - | - | FAA-H-8083-25C 5-15 (0.682) |
| Q033 | symptom | FAA-H-8083-25C 6-5 | - | - | FAA-H-8083-15B 4-16 (0.771) |
| Q034 | symptom | FAA-H-8083-25C 5-51 | - | - | FAA-H-8083-15B 4-16 (0.688) |
| Q035 | topic | FAA-H-8083-25C 7-35 | 1 | 1 | FAA-H-8083-25C 7-35 (0.782) |
| Q036 | topic | FAA-H-8083-25C 14-30 | 1 | 1 | FAA-H-8083-25C 14-30 (0.801) |
| Q037 | topic | FAA-H-8083-25C 14-42 | 1 | 1 | FAA-H-8083-25C 14-42 (0.785) |
| Q038 | topic | FAA-H-8083-25C 14-38 | 1 | 1 | FAA-H-8083-25C 14-38 (0.817) |
| Q039 | topic | FAA-H-8083-25C 16-21 | 1 | 1 | FAA-H-8083-25C 16-21 (0.792) |
| Q040 | topic | FAA-H-8083-25C 10-3 | 2 | 2 | FAA-H-8083-25C 10-4 (0.802) |
| Q041 | topic | FAA-H-8083-25C 11-4 | 1 | 1 | FAA-H-8083-25C 11-4 (0.809) |
| Q042 | topic | FAA-H-8083-25C 12-28 | 1 | 1 | FAA-H-8083-25C 12-28 (0.764) |
| Q043 | topic | FAA-H-8083-25C 7-17 | 1 | 1 | FAA-H-8083-25C 7-17 (0.837) |
| Q044 | topic | FAA-H-8083-25C 5-55 | 1 | 1 | FAA-H-8083-25C 5-55 (0.710) |
| Q045 | no-answer | (no answer) | - | - | FAA-H-8083-25C 5-47 (0.608) |
| Q046 | no-answer | (no answer) | - | - | FAA-H-8083-15B 10-15 (0.651) |
| Q047 | no-answer | (no answer) | - | - | FAA-H-8083-25C 5-15 (0.673) |
| Q048 | no-answer | (no answer) | - | - | FAA-H-8083-25C 11-29 (0.618) |
| Q049 | no-answer | (no answer) | - | - | FAA-H-8083-25C 1-22 (0.601) |
| Q050 | no-answer | (no answer) | - | - | FAA-H-8083-25C 1-24 (0.585) |
