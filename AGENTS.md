# AGENTS.md

Instructions for AI agents working in `/home/dred/Documents`.

## What this directory is

`~/Documents` is the **root of a git repository** that holds one tracked Python
project plus many untracked, unrelated sibling folders.

- Tracked project: `solana-defi-analytics` — a Solana DeFi analytics and risk
  dashboard (`pyproject.toml`, `requires-python = ">=3.11"`).
- Untracked neighbours that are **not** part of it: `bLinder/`, `Cline/`,
  `Qoder/`, `specs/001-dashboard-upgrade/`, `seedream_slow/`, `NEW afent/`, a
  right-to-left-named folder, and loose files like `test.py`, `Bug`, `OllaMa`,
  `edu`.
- Local interpreter is Python 3.13.14 (`.venv/bin/python`), newer than the
  declared floor.

## Git hygiene (read before any commit)

- Never run `git add -A`, `git add .`, or `git commit -a` from this root. With
  this many untracked sibling folders, they will sweep in unrelated material.
- Stage explicit paths only, e.g. `git add src/risk/metrics.py tests/unit/test_risk.py`.
- Never commit `.env` or `.config.yaml` — both are gitignored on purpose
  (secrets). `.env.example` and `.config.yaml.example` are the tracked templates.
- Do not put real RPC endpoints, bot tokens, webhooks, or wallet keys in any
  file, including comments and test fixtures. Use env vars via `src/config.py`.

## Commands

```bash
# tests (verified working: 10 passed as of 2026-09-24)
.venv/bin/python -m pytest tests/ -q

# background data daemon (terminal 1) - takes no arguments
.venv/bin/python -m src.main

# dashboard (terminal 2; streamlit on :8501)
.venv/bin/streamlit run src/dashboard/app.py

# one-off quote lookup
.venv/bin/python -m src.cli quote <TOKEN_IN> <TOKEN_OUT> <AMOUNT>

# deps
.venv/bin/pip install -r requirements.txt
```

There is no configured linter, formatter, or type checker in this repo. Do not
claim a check passed by running a tool that isn't installed.

## Layout

```
src/config.py     YAML + .env loading -> Config dataclass
src/models.py     stdlib @dataclass domain models (Trade, LiquidityPosition, ...)
src/state.py      thread-safe in-memory singleton store
src/utils.py      setup_logging(), @retry exponential backoff, async helpers
src/engines/      slippage.py, liquidity.py  (async, aiohttp clients)
src/risk/         metrics.py (VaR/Sharpe), alerts.py (Telegram/Discord dispatch)
src/dashboard/    app.py + pages/ + components/  (Streamlit)
src/services/     untracked: rpc client, dex aggregator, il_predictor, nlp_parser
src/xyops/        untracked: separate plugin w/ its own config.py + requirements.txt
tests/unit/       the only directory containing real tests
```

Note the collisions: `src/models.py` and `src/models/`, `src/config.py` and the
empty `src/config/`, and a second `config.py` inside `src/xyops/`. Confirm which
one you mean before editing or importing.

## Code conventions in use

- Type hints from `typing` (`List`, `Dict`, `Optional`), not PEP 604 `|` syntax.
- Plain `@dataclass` for models and config — despite what the README says, there
  is **no Pydantic** anywhere in `src/`.
- One-line module and class docstrings on public objects.
- External I/O is `async def` with `aiohttp`, wrapped in `@retry` for transient
  failures; raise `ValueError` for invalid config rather than defaulting silently.
- Logging through `logging.getLogger(__name__)` after `setup_logging()`; no
  bare `print` in library code.
- Match the surrounding style; do not reformat files you are not otherwise editing.

## Spec-driven workflow

Feature work uses the spec-kit layout under `specs/NNN-feature-name/`:
`spec.md`, `plan.md`, `tasks.md`, `research.md`, `data-model.md`, `contracts/`,
`checklists/requirements.md`. Skills live in `.github/skills/speckit-*/`.
When a feature already has a spec folder, read `spec.md` and `tasks.md` before
implementing, and update `tasks.md` as you complete items.

`.specify/memory/constitution.md` is still the **unfilled template** with
placeholder tokens. Do not treat it as project law or quote its placeholders as
decisions.

## Known documentation drift

`README.md` overstates the project. Verify against the code before repeating any
of these claims:

- "Test Coverage ~85%" and "Integration / Contract / End-to-End Tests" — no
  coverage tool is configured, and `tests/integration/` and `tests/contract/`
  are empty directories.
- "Pydantic data models" — actually stdlib dataclasses.
- "Docker Deployment", "DEPLOYMENT.md", `docs/`, `mkdocs`, `docker-compose.yml`
  — none of these files exist.
- README's `.env` block lists SMTP/Telegram chat vars; the tracked
  `.env.example` only defines `TELEGRAM_WEBHOOK_URL` and `DISCORD_WEBHOOK_URL`.
- README shows `python -m src.main --daemon`; `src/main.py` parses no arguments,
  so run it with no flags. Only `src/cli.py` uses argparse.

Fix the code or the README when you notice a mismatch, and say which one you
changed.

## Verifying your own work

Run `pytest tests/ -q` after any change to `src/engines/` or `src/risk/`. For
changes outside those paths there is currently no automated test, so exercise
the code path directly and report what you actually observed. Prefer offline
simulation mode (`simulation_enabled: true` in config) over hitting public RPC
endpoints during development.
