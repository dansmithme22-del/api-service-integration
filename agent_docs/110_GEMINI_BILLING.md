# Enabling Gemini API billing (and why you should)

## What the free tier gives you

| Model | Free-tier RPM | Free-tier daily requests |
|---|---|---|
| `gemini-2.5-pro` | **0** (effectively unavailable) | 0 |
| `gemini-2.5-flash` | 10 RPM | 250/day |
| `gemini-2.5-flash-image` | very low | trivially low |

In practice, the pipeline currently degrades to Flash on every run, and Flash
sometimes also fails (high demand → 503, or daily cap hit).

## Why this matters for accuracy

- **Pro is meaningfully more accurate** on architectural plan reading. Anchor
  bbox, room polygons, dimension callouts — all improve materially.
- **Pro is faster** for our prompt size (we pack a big system prompt and a
  PNG image).
- **Pro is more consistent** run-to-run. Flash is noticeably noisy on
  identical inputs.

## What enabling billing costs

For Pro at typical pipeline usage (one A3 plan page = ~5K input tokens + ~10K
output tokens) you're looking at roughly:

- ~$0.05–0.10 per plan ingest
- Plus ~$0.04 per Gemini 2.5 Flash Image render call

For a one-person workflow (a few projects a week, dozens of renders), that's
under $5/month. Trivially cheap relative to the time saved.

## How to enable it

1. Visit **<https://aistudio.google.com/apikey>**
2. Click the key row → **Project** → **Set up billing**
3. You'll be sent to **<https://console.cloud.google.com/billing>**
4. Create a billing account if you don't have one (requires a credit card)
5. Link the AI Studio project to it
6. **Wait 1–5 minutes** for the quota change to propagate
7. No code change needed on this side — the pipeline already prefers
   `gemini-2.5-pro` and falls back automatically.

## Verifying it's working

After billing is enabled, run any ingest with `--force vision` and look for:

```
INFO  httpx  HTTP Request: POST .../gemini-2.5-pro:generateContent "HTTP/1.1 200 OK"
INFO  src.ingest.vision_parser  Gemini gemini-2.5-pro returned NNNN chars.
```

If you still see Flash in those log lines, billing hasn't propagated yet.

## Hard ceiling — runaway costs

The `google-genai` SDK doesn't have a built-in spend limit, but Google Cloud
billing does. To cap exposure:

1. Go to <https://console.cloud.google.com/billing/budgets>
2. Create a budget on the linked project: e.g. **$20 / month, alert at 50%
   and 100%**.
3. Optionally **disable the project** when the budget is hit (advanced).
