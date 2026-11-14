# Chat evaluation `2026-11-14-chat`

- Date (UTC): 2026-11-14 12:41; git commit: c086f4a
- Embedding model: gemini-embedding-001; thresholds (0.64, 0.66); top 5; all handbooks

## A. The 50 questions as the first message of a chat

- Answer modes: extractive 3, llm 39, no_answer 8
- No-answer questions answered "no answer": 8/8
- Answerable questions answered "no answer": 0/42

| First figure = expected (answerable) | Hit@1 | Hit@5 |
| --- | --- | --- |
| retrieval order (score) | 31/42 | 38/42 |
| order shown by the chat (cited first) | 32/42 | 38/42 |

## B. Follow-up questions (10 pairs)

| Follow-up searched | Hit@1 | Hit@5 |
| --- | --- | --- |
| with history (chat, rewritten) | 7/10 | 10/10 |
| without history (search box) | 6/10 | 7/10 |
- Rewrites that fell back (LLM failure): 0/10

| Pair | Follow-up | Rewritten | rank with / without history |
| --- | --- | --- | --- |
| F01 | What is the purpose of its rate gyro? | What is the purpose of the turn coordinator's rate gyro? | 3 / 1 |
| F02 | What components make up its display? | What components make up the attitude indicator's display? | 1 / 1 |
| F03 | How are its radials represented? | How are VOR radials represented? | 1 / 1 |
| F04 | What happens to the airspeed indicator if it gets blocked during a climb? | What happens to the airspeed indicator if the airspeed indicator gets blocked during a climb? | 4 / 4 |
| F05 | What are the stages in its life? | What are the stages in the life of a thunderstorm? | 1 / 1 |
| F06 | How does the oil flow through it? | How does the oil flow through a wet-sump oil system? | 1 / 1 |
| F07 | What do its lights show when I am too high or too low? | What do the PAPI lights indicate when I am too high or too low? | 1 / - |
| F08 | How do I use it to find the landing direction? | How do I use the segmented circle to find the landing direction? | 1 / - |
| F09 | How do I read it? | How do I read the V‑g diagram? | 1 / - |
| F10 | How do I find it from the chart using the temperature and the pressure altitude? | How do I find density altitude from the chart using temperature and pressure altitude? | 2 / 1 |
