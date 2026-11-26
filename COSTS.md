# Costs

**Actual spend: $0.** Everything ran on free tiers. The numbers below are **measured** from `runs.jsonl` with `python run.py costs`, except where marked *published*. Re-run that command for the current totals.

## Free-tier limits found (checked 2026-11-25/26)

| Provider | Limit as I hit it | Source |
|---|---|---|
| Gemini TTS (each model separately) | **10 requests/day per project per model** (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`), plus a per-minute cap that cleared within 4–8 s | the 429 response body (FAILURES F8) |
| Gemini text (`gemini-3.8-flash`) | not limited by quota: 503 "high demand" and timeouts on the morning of 26 Nov | runs.jsonl (FAILURES F6) |
| Cloudflare Workers AI | 10,000 neurons/day free, resets 00:00 UTC; then $0.011 per 1,000 neurons | *published*, developers.cloudflare.com/workers-ai/platform/pricing |
| FLUX.2 klein 4B, 1024², 4 steps | ≈104 neurons, plus ≈21 per reference image → ≈80–95 images/day free | *published* rate, my arithmetic; logged per call as `cf_neurons` |
| FLUX.1 schnell, 1024², 4 steps | ≈58 neurons → ≈170 images/day, but it cannot be seeded (FAILURES F3) | same |
| Kaggle GPU | ≈30 GPU-hours/week (T4 x2 / P100), with phone verification | kaggle.com account page |

## Measured, per stage (snapshot 26 Nov, 12:41 EAT)

| Stage | Model | Calls | OK | Failed | Median latency (s) | Total latency (s) | Units | List-price USD |
|---|---|---|---|---|---|---|---|---|
| script | gemini-3.8-flash | 3 | 0 | 3 | – | – | – | – |
| script | gemini-2.5-flash | 2 | 1 | 1 | 29.3 | 29 | 9,310 tokens | not priced |
| narration | gemini-3.8-flash-tts | 15 | 12 | 3 | 8.4 | 100 | 4,822 output tokens | not priced |
| narration | gemini-3.8-flash-lite-tts | 13 | 9 | 4 | 5.5 | 47 | 1,650 output tokens | not priced |
| keyframes | flux-2-klein-4b | 26 | 24 | 2 | 11.4 | 282 | 2,716 neurons | $0.030 |
| smoke + experiments | (all providers) | 25 | 13 | 12 | – | – | 705 neurons | $0.008 |
| music | ACE-Step 1.5 turbo (Kaggle T4) | see `kaggle` rows after `run.py import-kaggle` | | | | | GPU minutes | |
| assemble | FFmpeg (local CPU) | – | – | – | – | radio cut 37 s, film (both ratios, from scratch) 225 s | – | $0 |

How to read the failures: most are **quota and capacity events**, not bugs. They are 429s (retried, or failed fast once the cap is daily), 503s (a fallback model was used), one content-filter 400, and one SSL reset (retried). Each one has a line in runs.jsonl and an entry in FAILURES.md.

## What one film costs

- **Images:** 9 keyframes and 2 references, about 125 neurons each with a reference. A full keyframe pass is ≈1,300 neurons, 13% of the daily free allocation. With my 2 rounds of prompt fixes, the whole film used ≈2,700 neurons ≈ **$0.03 at list price**.
- **Narration:** 9 TTS calls per full pass, **90% of one model's daily free quota**. That makes narration the binding constraint, not GPU time or money.
- **Wall-clock:** about 20 minutes of API time in total. A cached re-run of `film` that changes one shot takes about 1–2 minutes, nearly all of it FFmpeg re-encoding the concat and the final pass.

## Gemini list price

Gemini API paid-tier prices for the 3.8 TTS models were not verified, so `pricing.json` leaves them `null` rather than guessing. On the free tier the cost was $0.
