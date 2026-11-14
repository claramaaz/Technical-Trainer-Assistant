# Evaluation run `2026-11-13-gemini-t`

- Date (UTC): 2026-11-13 18:17; git commit: 900b0d6
- Model: gemini-embedding-001; thresholds (no answer, low confidence): (0.64, 0.66); top 5
- Retrieval mode: text
- Questions: 50 (42 answerable, 8 no-answer)
- own = only the question's handbook; all = every searchable handbook

| Scope | Metric rule | Questions | Hit@1 | Hit@5 | MRR@5 |
| --- | --- | --- | --- | --- | --- |
| own | auto (expected figure) | 42 | 0.881 | 0.929 | 0.905 |
| own | human (scored 2) | 23 of 42 judged | 1.000 | 1.000 | 1.000 |
| all | auto (expected figure) | 42 | 0.738 | 0.905 | 0.808 |
| all | human (scored 2) | 23 of 42 judged | 0.870 | 1.000 | 0.928 |

By question type (auto rule):

| Scope | Type | Questions | Hit@1 | Hit@5 | MRR@5 |
| --- | --- | --- | --- | --- | --- |
| own | topic | 30 | 0.933 | 0.967 | 0.950 |
| own | symptom | 12 | 0.750 | 0.833 | 0.792 |
| all | topic | 30 | 0.833 | 0.933 | 0.878 |
| all | symptom | 12 | 0.500 | 0.833 | 0.632 |

| Scope | No-answer accuracy | Answerable questions refused by the threshold |
| --- | --- | --- |
| own | 7/8 | 0/42: none |
| all | 7/8 | 0/42: none |

Per question: rank of the expected figure (auto), '-' = not in the top 5; top-1 returned.

| Question | Type | Expected | own rank | all rank | all top-1 (score) |
| --- | --- | --- | --- | --- | --- |
| Q001 | topic | FAA-H-8083-15B 1-1 | 1 | 2 | FAA-H-8083-25C 15-1 (0.711) |
| Q002 | topic | FAA-H-8083-15B 3-3 | 1 | 1 | FAA-H-8083-15B 3-3 (0.684) |
| Q003 | topic | FAA-H-8083-15B 3-9 | 1 | 1 | FAA-H-8083-15B 3-9 (0.778) |
| Q004 | topic | FAA-H-8083-15B 4-2 | 1 | 3 | FAA-H-8083-25C 5-5 (0.692) |
| Q005 | topic | FAA-H-8083-15B 4-5 | 1 | 1 | FAA-H-8083-15B 4-5 (0.645) |
| Q006 | topic | FAA-H-8083-15B 4-7 | - | - | FAA-H-8083-25C 12-9 (0.685) |
| Q007 | topic | FAA-H-8083-15B 4-3 | 1 | 1 | FAA-H-8083-15B 4-3 (0.771) |
| Q008 | topic | FAA-H-8083-15B 5-7 | 1 | 1 | FAA-H-8083-15B 5-7 (0.693) |
| Q009 | topic | FAA-H-8083-15B 5-34 | 1 | 1 | FAA-H-8083-15B 5-34 (0.768) |
| Q010 | topic | FAA-H-8083-15B 7-52 | 1 | 1 | FAA-H-8083-15B 7-52 (0.763) |
| Q011 | topic | FAA-H-8083-15B 7-73 | 1 | 1 | FAA-H-8083-15B 7-73 (0.711) |
| Q012 | topic | FAA-H-8083-15B 9-1 | 1 | 1 | FAA-H-8083-15B 9-1 (0.731) |
| Q013 | topic | FAA-H-8083-15B 9-10 | 1 | 1 | FAA-H-8083-15B 9-10 (0.770) |
| Q014 | topic | FAA-H-8083-15B 9-17 | 1 | 1 | FAA-H-8083-15B 9-17 (0.773) |
| Q015 | topic | FAA-H-8083-15B 10-13 | 1 | 1 | FAA-H-8083-15B 10-13 (0.769) |
| Q016 | topic | FAA-H-8083-15B 10-17 | 1 | - | FAA-H-8083-25C 11-19 (0.739) |
| Q017 | topic | FAA-H-8083-15B 11-2 | 1 | 1 | FAA-H-8083-15B 11-2 (0.709) |
| Q018 | topic | FAA-H-8083-15B 11-11 | 1 | 1 | FAA-H-8083-15B 11-11 (0.713) |
| Q019 | topic | FAA-H-8083-15B 11-18 | 1 | 1 | FAA-H-8083-15B 11-18 (0.743) |
| Q020 | symptom | FAA-H-8083-15B 5-2 | 1 | 4 | FAA-H-8083-25C 8-9 (0.727) |
| Q021 | topic | FAA-H-8083-15B 5-40 | 1 | 1 | FAA-H-8083-15B 5-40 (0.779) |
| Q022 | symptom | FAA-H-8083-15B 5-20 | 1 | 2 | FAA-H-8083-25C 8-37 (0.739) |
| Q023 | symptom | FAA-H-8083-15B 7-39 | 1 | 1 | FAA-H-8083-15B 7-39 (0.823) |
| Q024 | no-answer | (no answer) | - | - | FAA-H-8083-25C 7-41 (0.564) |
| Q025 | no-answer | (no answer) | - | - | FAA-H-8083-15B 9-42 (0.652) |
| Q026 | symptom | FAA-H-8083-25C 7-11 | 1 | 1 | FAA-H-8083-25C 7-11 (0.661) |
| Q027 | symptom | FAA-H-8083-25C 7-21 | 1 | 1 | FAA-H-8083-25C 7-21 (0.645) |
| Q028 | symptom | FAA-H-8083-25C 8-11 | 1 | 1 | FAA-H-8083-25C 8-11 (0.748) |
| Q029 | symptom | FAA-H-8083-25C 8-22 | 1 | 1 | FAA-H-8083-25C 8-22 (0.765) |
| Q030 | symptom | FAA-H-8083-25C 17-5 | - | - | FAA-H-8083-15B 7-8 (0.710) |
| Q031 | symptom | FAA-H-8083-25C 12-17 | 1 | 1 | FAA-H-8083-25C 12-17 (0.662) |
| Q032 | symptom | FAA-H-8083-25C 5-17 | - | - | FAA-H-8083-25C 11-18 (0.652) |
| Q033 | symptom | FAA-H-8083-25C 6-5 | 2 | 3 | FAA-H-8083-15B 4-16 (0.698) |
| Q034 | symptom | FAA-H-8083-25C 5-51 | 1 | 2 | FAA-H-8083-15B 4-16 (0.679) |
| Q035 | topic | FAA-H-8083-25C 7-35 | 1 | 1 | FAA-H-8083-25C 7-35 (0.723) |
| Q036 | topic | FAA-H-8083-25C 14-30 | 1 | 1 | FAA-H-8083-25C 14-30 (0.740) |
| Q037 | topic | FAA-H-8083-25C 14-42 | 1 | 1 | FAA-H-8083-25C 14-42 (0.760) |
| Q038 | topic | FAA-H-8083-25C 14-38 | 1 | 1 | FAA-H-8083-25C 14-38 (0.778) |
| Q039 | topic | FAA-H-8083-25C 16-21 | 2 | 2 | FAA-H-8083-25C 16-19 (0.753) |
| Q040 | topic | FAA-H-8083-25C 10-3 | 1 | 1 | FAA-H-8083-25C 10-3 (0.768) |
| Q041 | topic | FAA-H-8083-25C 11-4 | 1 | 1 | FAA-H-8083-25C 11-4 (0.731) |
| Q042 | topic | FAA-H-8083-25C 12-28 | 1 | 1 | FAA-H-8083-25C 12-28 (0.731) |
| Q043 | topic | FAA-H-8083-25C 7-17 | 1 | 1 | FAA-H-8083-25C 7-17 (0.752) |
| Q044 | topic | FAA-H-8083-25C 5-55 | 1 | 1 | FAA-H-8083-25C 5-55 (0.728) |
| Q045 | no-answer | (no answer) | - | - | FAA-H-8083-25C 7-16 (0.624) |
| Q046 | no-answer | (no answer) | - | - | FAA-H-8083-15B 4-17 (0.632) |
| Q047 | no-answer | (no answer) | - | - | FAA-H-8083-25C 17-9 (0.639) |
| Q048 | no-answer | (no answer) | - | - | FAA-H-8083-25C 11-27 (0.632) |
| Q049 | no-answer | (no answer) | - | - | FAA-H-8083-25C 1-22 (0.603) |
| Q050 | no-answer | (no answer) | - | - | FAA-H-8083-25C 1-24 (0.579) |
