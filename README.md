# AI Weekly Digest Agent

A scheduled batch pipeline (not an always-on service, not an autonomous agent) that
collects AI news weekly, scores/categorizes/summarizes it with an LLM, and emails a
digest — with a manual approval gate before the full recipient list gets it.

See `CLAUDE.md` for the full design spec this implementation follows.

## Architecture

```
collector -> deduplicator -> scorer -> categorizer -> summarizer -> email_builder -> mailer
```

Two separate `main.py` modes:

- **`--mode build`**: runs the full pipeline, sends a **preview to `MAINTAINER_EMAIL`
  only**, and persists the built email to `data/last_digest.json`. Triggered
  automatically every Monday via cron, or manually.
- **`--mode send`**: loads `data/last_digest.json` (the *exact* email that was
  previewed — it is not regenerated) and sends it to everyone in
  `config/recipients.yaml`. Triggered only by manually clicking "Run workflow" in
  GitHub Actions, after you've reviewed the preview.

## Setup

1. `python -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. `cp .env.example .env` and fill in:
   - `OPENROUTER_API_KEY` — from [openrouter.ai](https://openrouter.ai). `OPENROUTER_MODEL`
     defaults to a current free (`:free`-suffixed) model; check
     [openrouter.ai/models](https://openrouter.ai/models) (Price filter -> Free) if it
     stops working, since free model availability changes over time.
   - `BREVO_API_KEY`, `SENDER_EMAIL` (must be a **verified sender** in your Brevo
     account), `SENDER_NAME`.
   - `MAINTAINER_EMAIL` — gets every preview and every failure alert.
   - `DRY_RUN=true` — keep this while testing. When true, **every** send (preview
     and full) only ever goes to `MAINTAINER_EMAIL`, regardless of
     `config/recipients.yaml`.
4. Edit `config/sources.yaml` / `config/recipients.yaml` as needed — both are seeded
   with reasonable defaults (a handful of AI-focused RSS feeds + Hacker News; the
   recipients list currently has only the maintainer's own address).

## Running locally

```bash
python main.py --mode build   # collect -> score -> ... -> preview to maintainer
python main.py --mode send    # send the last previewed digest to config/recipients.yaml
```

To sanity-check the collector + email layout **without** any API keys:

```bash
python scripts/run_build_local.py   # writes data/preview.html — open it in a browser
```

(This stubs out the scoring/summarizing steps since those need a real LLM key; it's
meant for checking that sources parse and the HTML layout renders correctly.)

## Tests

```bash
pytest tests/
```

Covers URL normalization + fuzzy dedupe (deterministic, no network) and proves the
scorer/categorizer/summarizer/mailer handle both well-formed and malformed LLM output
without crashing (`core.llm.get_llm_response` is mocked — no API key needed).

## Deploying (GitHub Actions)

`.github/workflows/digest.yml` defines two triggers:

- `build`: `cron: '0 2 * * 1'` (02:00 UTC Mondays) + `workflow_dispatch`. **The cron is
  UTC** — the current setting targets 08:00 in a UTC+6 timezone; adjust the hour in the
  workflow file's comment/cron line to match your company's local timezone.
- `send`: `workflow_dispatch` only — this is the manual approval step. After reviewing
  the preview email, go to **Actions -> AI Weekly Digest -> Run workflow**, choose
  mode `send`.

Add all `.env` values as **repository secrets** (Settings -> Secrets and variables ->
Actions) with the same names.

**Persistence approach**: `data/sent_history.json` and `data/last_digest.json` are
committed back to the repo by the workflow itself after each run (see the "Persist...
back to the repo" step in `digest.yml`). This requires `permissions: contents: write`
(already set) and a repo that allows Actions to push commits.

## Known dependency: inbox delivery is an IT problem, not a code problem

During testing, mail from Brevo to internal Outlook addresses will likely land in
**junk** — tell testers to check there. Do not try to engineer around spam filtering.
Scaling beyond the test group requires IT to authenticate the sending domain
(SPF/DKIM/DMARC) or provide an internal relay. The mailer is isolated in
`agents/mailer.py` specifically so swapping Brevo for an IT-approved channel later is a
single-module change.
