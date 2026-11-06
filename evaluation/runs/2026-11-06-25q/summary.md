# Evaluation run `2026-11-06-25q`

- Date (UTC): 2026-11-06 09:07; git commit: 3856093
- Model: BAAI/bge-small-en-v1.5; threshold: 0.65; top 5
- Questions: 25 (23 answerable, 2 no-answer)
- own = only the question's handbook; all = every searchable handbook

| Scope | Metric rule | Questions | Hit@1 | Hit@5 | MRR@5 |
| --- | --- | --- | --- | --- | --- |
| own | auto (expected figure) | 23 | 0.652 | 0.870 | 0.743 |
| own | human (scored 2) | 0 of 23 judged | n/a | n/a | n/a |
| all | auto (expected figure) | 23 | 0.478 | 0.826 | 0.634 |
| all | human (scored 2) | 0 of 23 judged | n/a | n/a | n/a |

| Scope | No-answer accuracy | Answerable questions refused by the threshold |
| --- | --- | --- |
| own | 2/2 | 1/23: Q018 |
| all | 2/2 | 1/23: Q018 |

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
