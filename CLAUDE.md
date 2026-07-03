# CLAUDE.md — AI Weekly Digest Agent

> Instructions for Claude Code. Read this whole file before writing any code.
> Build the project **incrementally in the order given in "Build Order"** — get a
> crude end-to-end version working before polishing any single stage.

---

## 1. What we are building

A **scheduled batch pipeline** (NOT an always-on service, and NOT an autonomous
reasoning agent) that:

1. Wakes up **every Monday at 08:00** via a scheduled trigger.
2. Collects AI-related news published in the **last 7 days** from a configured list
   of RSS feeds and APIs.
3. Removes duplicates (both within this week and against previously sent items).
4. Uses an LLM to **score**, **categorize**, and **summarize** each item in plain,
   non-technical language.
5. Builds a professional, Outlook-safe **HTML email** (with a plain-text fallback).
6. **Sends a preview to the maintainer only.** After manual approval, sends the
   same email to the full recipient list.
7. Logs the run and alerts the maintainer on failure.

The word "agent" here means a pipeline of LLM-assisted steps. Do not build
autonomous tool-use loops or a multi-agent framework. Plain Python functions
orchestrated by `main.py`.

---

## 2. Audience & content scope (this drives all LLM prompts)

**Audience:** employees at a *general* (non-technical) company — sales, HR, ops,
finance, plus some engineers. Assume the reader is smart but NOT an AI specialist.

**Therefore:**
- Summaries must be in **plain language**. No jargon (no "MoE", "context window",
  "RLHF") without a one-word explanation.
- Every item must answer: **"What is it, and why might it matter to us?"**
- Prefer practical relevance over technical novelty.

**In scope:** new AI model releases, new helpful AI tools/products, new technologies
being adopted in industry, notable new tech stacks/tooling companies are using.

**Out of scope / de-prioritize:** dense academic papers with no practical angle,
incremental version bumps, pure hype with no substance.

---

## 3. Tech stack & hard constraints

| Concern        | Decision                                                              |
|----------------|-----------------------------------------------------------------------|
| Language       | Python 3.11+                                                          |
| Scheduling     | GitHub Actions cron (`0 8 * * 1`) + `workflow_dispatch` for manual runs |
| LLM            | **OpenRouter** (OpenAI-compatible API), a **free** model              |
| RSS parsing    | `feedparser`                                                          |
| HTTP           | `requests`                                                            |
| Fuzzy dedupe   | `rapidfuzz`                                                           |
| Templating     | `Jinja2`                                                              |
| Email sending  | **Brevo** transactional email API                                     |
| Config         | `sources.yaml`, `recipients.yaml` (or `.py` config), `.env` locally   |

**Hard constraints — do not violate:**
- **No secrets in the repo.** All keys/credentials come from environment variables,
  loaded from GitHub Actions Secrets in CI and a git-ignored `.env` locally.
- **Every LLM call goes through one wrapper function** (`get_llm_response`). No stage
  may call the API directly. This makes swapping models a one-file change.
- **Email HTML must be Outlook-safe**: inline styles only, table-based layout, no
  external CSS, no JavaScript, no web fonts. Assume the worst renderer.
- The pipeline must **fail gracefully**: one broken source or one bad LLM response
  must not crash the whole run.

**Note on external APIs:** OpenRouter and Brevo API details (endpoints, request
shapes, free-model names, rate limits) change over time and may be newer than my
training data. **Verify request/response formats against the current official docs**
before finalizing those modules. Do not hard-assume a payload shape I might have
gotten slightly wrong — check.

---

## 4. Environment variables

Create a `.env.example` documenting all of these (with placeholder values), and
load them via `python-dotenv` locally / GitHub Secrets in CI:

```
OPENROUTER_API_KEY=
OPENROUTER_MODEL=            # default to a current free model; make it configurable
BREVO_API_KEY=
SENDER_EMAIL=               # verified sender in Brevo
SENDER_NAME=AI Weekly Digest
MAINTAINER_EMAIL=           # who gets the preview + failure alerts
DRY_RUN=true                # if true, never send to the full list — maintainer only
```

---

## 5. Architecture / data flow

```
GitHub Actions (Mon 08:00, or manual)
        │
        ▼
   main.py  (orchestrator — no AI logic of its own)
        │
        ▼
 collector  →  deduplicator  →  scorer  →  categorizer  →  summarizer  →  email_builder
        │                                                                      │
        │                                                                      ▼
        │                                                          preview email to maintainer
        │                                                          + built email persisted to disk
        │                                                                      │
        │                                                       [ MANUAL APPROVAL GATE ]
        │                                                                      │
        │                                                                      ▼
        │                                                          mailer → full recipient list
        └────────────────────────── logging / failure alerts (throughout) ───────────────┘
```

Each stage takes a Python list of dicts and returns a Python list of dicts. Keep the
data shape consistent (see §7).

---

## 6. File structure

```
ai-weekly-digest/
├── .github/
│   └── workflows/
│       └── digest.yml          # cron + workflow_dispatch; two jobs (build, send)
├── config/
│   ├── sources.yaml            # all RSS feeds + API sources
│   └── recipients.yaml         # static list of recipient emails (test group)
├── agents/
│   ├── __init__.py
│   ├── collector.py
│   ├── deduplicator.py
│   ├── scorer.py
│   ├── categorizer.py
│   ├── summarizer.py
│   ├── email_builder.py
│   └── mailer.py
├── core/
│   ├── __init__.py
│   ├── llm.py                  # get_llm_response() wrapper (OpenRouter)
│   ├── config.py               # loads env + yaml config
│   └── logging_utils.py        # run logging + failure alerts
├── templates/
│   ├── email.html.j2           # Outlook-safe HTML template (Jinja2)
│   └── email.txt.j2            # plain-text fallback
├── data/
│   ├── sent_history.json       # cross-week dedupe store (committed back after run)
│   └── last_digest.json        # the built email, persisted between build & send runs
├── logs/                       # per-run logs (or use GitHub Actions artifacts)
├── main.py                     # orchestrator; supports --mode build|send
├── requirements.txt
├── .env.example
├── .gitignore                  # must ignore .env, __pycache__, local logs
└── README.md
```

---

## 7. Canonical data shape

The collector normalizes every source into this shape. Later stages add fields but
never remove them:

```python
{
    "id": "<stable hash of normalized url>",   # for dedupe + history
    "title": "GPT-6 Released",
    "source": "OpenAI",
    "url": "https://...",
    "published": "2026-06-29T10:00:00Z",       # normalized to UTC ISO-8601
    "raw_content": "...",                       # text pulled from the feed/API
    # added by later stages:
    "score": 9,                                 # scorer (1-10)
    "score_reason": "...",                      # scorer
    "category": "New Models",                   # categorizer
    "summary": "..."                            # summarizer (2-3 plain sentences)
}
```

---

## 8. Module specifications

### 8.1 `core/llm.py` — `get_llm_response(prompt, *, json_mode=False)`

- Calls OpenRouter's OpenAI-compatible chat completions endpoint.
- Reads `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` from env.
- **Retry with backoff on rate-limit (HTTP 429) and transient errors** — free models
  have per-minute limits. Retry a few times with increasing delay before giving up.
- When `json_mode=True`, instruct the model to return **only** valid JSON, and parse
  it defensively (strip code fences, `try/except`, return a safe fallback on failure).
- This is the ONLY place the LLM is called. Everything else imports this.

### 8.2 `agents/collector.py`

- Reads `config/sources.yaml`.
- For RSS sources: use `feedparser`. For API sources (e.g. Hacker News): use `requests`.
- **Wrap each source in try/except** — log and skip a failing source, never crash.
- Normalize every item into the canonical shape (§7), converting all timestamps to UTC.
- **Filter to items published in the last 7 days.**
- Return a flat list of dicts.

### 8.3 `agents/deduplicator.py`

- **Within-week dedupe:** normalize URLs (strip tracking params like `utm_*`), drop
  exact dupes; then fuzzy-match titles with `rapidfuzz` and drop near-duplicates,
  keeping the item from the most authoritative source.
- **Cross-week dedupe:** load `data/sent_history.json` and drop any item whose id/url
  was already sent within a rolling ~4-week window.
- After a successful *send*, append newly sent ids to `sent_history.json`.

### 8.4 `agents/scorer.py`

- Uses `get_llm_response(..., json_mode=True)`.
- **Batch multiple items per prompt** (e.g. 10 at a time) to respect free-tier rate
  limits — do not make one API call per item.
- Prompt asks: rate each item **1–10** for importance to a *general (non-technical)
  company*, with a short reason. Reward practical relevance and clarity; penalize
  dense/niche research.
- Attach `score` and `score_reason`. Then keep roughly the **top 10–15** items.

### 8.5 `agents/categorizer.py`

- Assign each surviving item to one of a fixed set of buckets, e.g.:
  `New Models`, `Tools & Products`, `Industry & Adoption`, `Research`, `Safety & Policy`.
- Batch the LLM calls. Attach `category`.

### 8.6 `agents/summarizer.py`

- For each item, produce a **2–3 sentence plain-language summary** answering
  "what is it + why it matters to us."
- **Ground the summary strictly in the provided `raw_content`** — instruct the model
  not to invent facts or add outside claims. This prevents hallucination.
- Batch where possible. Attach `summary`.

### 8.7 `agents/email_builder.py`

- Renders `templates/email.html.j2` and `templates/email.txt.j2` with the categorized,
  summarized items grouped by category.
- Email must include:
  - A dated header and a short, warm **intro line** ("A few things worth knowing this
    week…") — this makes it feel curated, not automated.
  - A **TL;DR / top picks** block at the top for skimmers (the 2–3 highest-scored items).
  - Category sections with clear headers (an emoji per category is fine).
  - Per item: **bold, hyperlinked headline** → plain-language summary → subtle
    "Read more →" link to the source.
  - A footer.
- **HTML rules:** inline styles only, table-based layout, one accent color
  (make it a config constant so a brand color can be swapped in), no JS, no web fonts,
  no external stylesheets. Include descriptive alt text on any images (assume images
  may be blocked by default in Outlook — the email must read fine with images off).
- Returns `{ "subject": ..., "html": ..., "text": ... }`.
- **Persist this object to `data/last_digest.json`** so the send run uses the *exact*
  email that was previewed (see §9).

### 8.8 `agents/mailer.py`

- `send(email, recipients, *, bcc=True)` using the **Brevo transactional email API**.
- Reads `BREVO_API_KEY`, `SENDER_EMAIL`, `SENDER_NAME` from env.
- Include **both** the HTML and plain-text parts in the send.
- For the test group, send with everyone in **BCC** so recipients don't see each
  other's addresses.
- **Respect `DRY_RUN`:** if `DRY_RUN=true`, only ever send to `MAINTAINER_EMAIL`,
  regardless of the recipient list.
- Verify the Brevo request shape against current Brevo docs (see §3 note).

### 8.9 `core/logging_utils.py`

- Log each run: how many items collected, filtered at each stage, and the send result.
- Write logs to `logs/` and/or emit as GitHub Actions output.
- **On any unhandled failure, send a short alert email to `MAINTAINER_EMAIL`** (via the
  mailer) so a broken Monday run doesn't go unnoticed.

---

## 9. The approval gate (important — two separate runs)

Do NOT send to everyone automatically. Split into two modes controlled by
`main.py --mode`:

- **`build` (runs Monday 08:00 automatically):**
  collect → dedupe → score → categorize → summarize → build email →
  send **preview to `MAINTAINER_EMAIL` only** → save the built email to
  `data/last_digest.json`. Then stop. Does NOT touch the full recipient list.

- **`send` (triggered manually via `workflow_dispatch` after the maintainer approves):**
  load `data/last_digest.json` and send **that exact email** to the recipients in
  `config/recipients.yaml`. Then append sent ids to `sent_history.json`.

The `send` run must reuse the persisted email — it must NOT regenerate it, or the
maintainer would be approving one email and shipping a slightly different one.

For v1, "approval" = the maintainer reviews the preview, then clicks
**"Run workflow"** on the `send` job in the GitHub Actions UI. Do not build a hosted
approval-link endpoint yet; keep it as a manual trigger.

---

## 10. GitHub Actions (`digest.yml`)

- Two jobs (or two workflows): `build` and `send`.
- `build`: triggered by `schedule: cron: '0 8 * * 1'` **and** `workflow_dispatch`.
  - Note: cron is **UTC** — set the hour so 08:00 lands in the company's timezone,
    and add a code comment stating which timezone the cron represents.
  - Scheduled GitHub runs can be delayed a few minutes under load; that's acceptable.
- `send`: triggered by `workflow_dispatch` only (the manual approval step).
- Both jobs read all keys from **GitHub Actions Secrets**.
- If `sent_history.json` / `last_digest.json` need to persist across runs, either
  commit them back to the repo from within the workflow, or store them as workflow
  artifacts — pick one approach and document it in the README.

---

## 11. Build order (do this sequentially)

1. `core/config.py` + `core/llm.py` — prove you can call OpenRouter and get JSON back.
2. `config/sources.yaml` + `collector.py` — prove real AI news flows in (print it).
3. `deduplicator.py` (within-week first; add cross-week history after).
4. `summarizer.py` — print summaries to console.
5. `email_builder.py` + templates — save HTML to a file, open it in a browser to check.
6. `mailer.py` — send a test email **to the maintainer only** (`DRY_RUN=true`) via Brevo.
7. `scorer.py` + `categorizer.py` — add quality filtering and grouping.
8. Wire up `main.py` with `--mode build|send` and the approval split (§9).
9. `logging_utils.py` — logging + failure alerts.
10. `digest.yml` — deploy; test with `workflow_dispatch` first, then enable the cron.

Get steps 1–6 working end-to-end (even ugly) before polishing 7 onward.

---

## 12. Testing

- Provide a `--dry-run` path and keep `DRY_RUN=true` by default so nothing goes to the
  full list during development.
- Add a small unit test for URL normalization and title-dedupe logic (deterministic,
  no network).
- Make the LLM wrapper mockable so pipeline tests can run without hitting the API.
- Include one script/command that runs the full `build` pipeline against real sources
  and writes the HTML to a local file for visual inspection.

---

## 13. Deliverables checklist

- [ ] All modules in §6, each doing exactly one job.
- [ ] `get_llm_response` is the only place the LLM is called, with rate-limit retry.
- [ ] Collector handles per-source failures without crashing.
- [ ] Dedupe works within-week and cross-week.
- [ ] Plain-language, grounded summaries; general-audience scoring.
- [ ] Outlook-safe HTML email + plain-text fallback + TL;DR + intro line.
- [ ] Brevo mailer with `DRY_RUN` and BCC.
- [ ] Two-mode approval gate; `send` reuses the exact previewed email.
- [ ] GitHub Actions with cron + manual dispatch; secrets not in repo.
- [ ] Logging + failure alerts.
- [ ] `README.md` explaining setup, env vars, how to run locally, and how to approve/send.

---

## 14. Known external dependency (document, don't try to code around it)

Company-wide inbox delivery is an **IT dependency**, not a coding problem. During the
test phase, mail from Brevo to internal Outlook addresses will likely land in **junk**;
testers are told to check there. Do **not** attempt to engineer around spam filtering.
The README should clearly state that scaling beyond the test group requires IT to
approve/authenticate the sending domain (SPF/DKIM/DMARC) or provide an internal relay.
Keep the code send-channel-agnostic (via the mailer module) so swapping Brevo for an
IT-approved channel later is a single-module change.
