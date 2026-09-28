# Contributing to Solana DeFi Dashboard

Thanks for taking a look. This is a small, deliberately honest codebase — a
few rules keep it that way.

## Non-negotiables

1. **Read-only.** Nothing in this project may sign, build, or send a
   transaction, or handle private keys. Proposals that change this will not
   be merged.
2. **No fabricated data.** If a value cannot be fetched or computed from real
   data, the code returns `None`/empty and the UI renders an explicit
   "unavailable (reason)" state. No mocks in product paths — fixtures in
   tests are fine (and must be labeled where they came from).
3. **Document every metric.** Any new displayed value gets a row in
   `METRICS.md`: source, refresh cadence, calculation, unavailable state.
4. **Cross-process state is SQLite only.** No new in-process globals shared
   between daemon and dashboard.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.lock.txt && pip install -e .
cp .config.yaml.example .config.yaml
```

## Before opening a PR

```bash
ruff check src tests            # lint gate
python -m pytest tests -q -m "not live"   # deterministic suite
python -m pytest tests -q -m live         # optional: real-endpoint checks
```

Every new module under `src/` must pass the import smoke test
(`tests/test_imports.py`) — if you add optional dependencies, add them to
`requirements.txt` and the lock file.

## Good first contributions

- Fix copy or labeling issues you noticed while using the dashboard.
- Add tests around `risk/metrics.py` edge cases.
- Wire a second CL venue **only if** it has a reachable position-by-owner
  API (see why Raydium was cut, in the changelog).
- Improve polling backpressure and error surfacing in `src/main.py`.

## Process

Fork → branch from `main` → small focused commits with tests → PR describing
what real data you verified it against. Screenshots help for UI changes.
