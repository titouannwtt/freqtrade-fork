# Upstream sync — freqtrade 2026.7 → 2026.8

**Fork current `__version__`:** `2026.6`
**Upstream latest tag:** `2026.8` (published 2026-08-31, one day ago)
**Range analysed:** `2026.6..2026.8` — 415 non-merge commits, ~20 823 insertions / 8 726 deletions across 239 files (101 of those commits are pure dependency bumps).

The prior port for 2026.7 landed as commit `505bf3812 feat(upstream): port the 2026.7 features the fork was missing` (2026-08-07). The `__version__` marker was never bumped, so 2026.6 in code no longer reflects the actual sync state.

## What the fork already carries

Verified against the current tree:

| Upstream change | Fork status |
|---|---|
| Hyperliquid `balance_includes_unrealized_pnl` (2026.8) | **Present** — `freqtrade/exchange/hyperliquid.py:65` |
| OKX stop-limit orders (2026.7) | **Present** — ported in `505bf3812` |
| FreqAI partial-data backtests (2026.7) | **Present** — ported in `505bf3812` |
| Dynamic pairlist `_sync_pair_index` (2026.7) | **Present** — ported in `505bf3812` |
| `TimeRange.copy()` (2026.7 dep) | **Present** — ported in `505bf3812` |

## What is still missing from 2026.8

Grouped by risk against fork-specific code. Files the fork owns and has non-trivially modified: `freqtrade/freqtradebot.py`, `freqtrade/exchange/exchange.py`, `freqtrade/exchange/hyperliquid.py`, `freqtrade/constants.py`, `freqtrade/plugins/pairlist/`, `freqtrade/rpc/api_server/`, and everything under `freqtrade/replay/` (fork-only).

### High impact — needs careful hand-port

**@informative call caching** — `feat(informative_decorator)` chain (`350a56858`, `059504e8c`, `42e0ff3c4`).
The `@informative` decorator now caches its returned dataframe for 2 candles via a `TLRUCache`. This is enabled by default and is a **behavioural change**: strategies performing non-dataframe side effects inside `@informative`-decorated functions will now see those side effects run less often. Also introduces `freqtrade/candle_columns.py` and reworks `DEFAULT_DATAFRAME_COLUMNS` (now re-exported from `constants.py` for backwards compat).
- Impact on fork: none of the fork's strategies grep-hit for state mutation inside `@informative`, but any user strategy under `user_data/strategies/` needs a quick review. The Exchange refactor (`350a56858 update Exchange code to use new candle col mapping`) rewrites parts of `exchange.py` — the fork's `_guard_shared_wallet_exit` sits in the same file and needs 3-way reconciliation.

**Exchange refactor for candle_type columns** — `350a56858`, `1d8663b1a`, `2776f7274`, `7c4392885`.
Introduces `empty_dataframe()` helper and per-`CandleType` column mapping. `exchange.py` gains 107 additions / 77 deletions upstream; the fork carries 513/188 of its own changes on the same file. A three-way merge is unavoidable.

**Timerange minute support** — `dfa9d0442 feat: improved UX for hour/minute based timeranges`, `762a62c75`, `cb3faa377`, plus `eb334b77d chore: bump api_version to 2.50`.
FreqUI needs api_version ≥ 2.50 to expose the new timerange picker. Our FreqUI fork ships its own picker (fit-to-screen family) — verify no collision before bumping.

### Medium impact — likely portable as-is

**Pairlist `lookback_period` / `lookback_timeframe`** — `6b4dc52ea`, `7307983f1`, `c5508287a`, `a35c3ad68`, `165c0f820`.
VolatilityFilter and RangeStabilityFilter grow explicit `lookback_period` / `lookback_timeframe` parameters, with shared helpers to resolve them. The fork's `TrendRegularityFilter` has its own lookback logic and is unaffected; ports are surgical additions to the two upstream filters.
Behavioural change to flag: VolatilityFilter no longer folds an artificial zero into the first row of the lookback — averages will shift slightly on the same config.

**FreqAI historic prediction repair** — `7d403867f`, `3c64bf187`, `1b91e04a3`, `d8f7fb170`, `73b23ef96`, `047e5cca4`, `4a9401e0e`, `46d87f1a4`, `1fa7e3470`, `e7622ba88`, `90db9286c`, `4286dd9d2`.
Fixes duplicate-candle appending and cuts historic overlap by date rather than row count. Improves FreqAI reliability after bot downtime. The fork does not modify freqai internals — safe to cherry-pick as a block.

**Bug fixes in `freqtradebot.py` / `exchange.py`**:
- `2ffbe8cb3 fix: handle_on_exchange error problematic order attachement` — touches the same `handle_onexchange_order` path where the fork hooks `_handle_external_close`. Manual reconciliation required.
- `234521532 fix: rollback on error in handle_on_exchange_error` — same path.
- `e4092e1b8 fix: keyerror on shutdown` — clean.
- `9112e674e fix: don't reassign log queue in hyperopt unconditionally` — clean.
- `9f829f204 fix: unknown file layouts should be treated as empty when loading files` — clean.
- `7805c1218 fix: slow cache leak when using short timeframes in pairlists` — clean, worth taking.
- `3f0c7915b fix: don't rebuild pair regex per pair` — perf win, clean.

### Low impact — mechanical / mostly safe

**Bitmart delist** — `75b5b1830`, `b9a2c58fc`, `b16477cb3`.
Bitmart shut down end of July 2026. Removes references from `freqtrade/exchange/__init__.py`, `common.py`, `cached_subclasses.py`, docs. Bundled with additions of `BybitEU`, `GateEU` classes and a `kucoineu → kucoin` mapping. The fork does not run on Bitmart — pure cleanup.

**Dependency bumps** — 101 commits. ccxt 4.5.74 → 4.5.76, uvicorn 0.52.1 → 0.52.4, sqlalchemy 2.0.51 → 2.0.52, mypy 2.3.0 → 2.3.1, ruff 0.16.2 → 0.16.3, filelock 3.32.2 → 3.32.3, plus binance leverage-tier refresh (`40ae81ce1`, `b6137585d`) and pre-commit hook updates.
The fork's `pyproject.toml` pinning may diverge — spot check before bulk-bumping.

**Docs, tests, typos** — the remainder.

## Suggested port order

If following the same one-big-commit style as `505bf3812`:

1. Take the clean fixes first (`e4092e1b8`, `9112e674e`, `9f829f204`, `7805c1218`, `3f0c7915b`).
2. Port the pairlist lookback additions (leaves `TrendRegularityFilter` untouched).
3. Port FreqAI historic prediction repair as one block.
4. Manually reconcile `freqtradebot.py` around `_handle_external_close` for the two `handle_on_exchange` fixes.
5. Merge the candle_columns refactor into `exchange.py` alongside `_guard_shared_wallet_exit` — this is the largest, do it isolated with the shared-wallet-guard tests running (`tests/exchange/test_shared_wallet_exit_guard.py`).
6. Port the `@informative` cache + audit fork strategies for side effects inside decorated functions.
7. Bump ccxt / uvicorn / sqlalchemy / mypy / ruff / filelock; refresh binance leverage tiers.
8. Delist Bitmart, add BybitEU / GateEU / kucoineu mapping.
9. Bump `__version__` to `2026.8` and `api_version` to `2.50` — last, once everything above is in.

## Verification checklist before merging

- `ruff check freqtrade/` and `ruff format --check freqtrade/`
- `mypy freqtrade/`
- Full test suite: `pytest --random-order -n auto`
- Fork-critical tests specifically: `tests/exchange/test_shared_wallet_exit_guard.py`, `tests/replay/`
- Verify custom code preserved:
  - `grep _handle_external_close freqtrade/freqtradebot.py`
  - `grep _guard_shared_wallet_exit freqtrade/exchange/exchange.py`
  - `grep fetch_liquidation_fills freqtrade/exchange/hyperliquid.py`
  - `grep TrendRegularityFilter freqtrade/constants.py`
  - `ls freqtrade/replay/` (replay harness intact)
- `pip install -e ".[replay]"` and start one live bot in dry mode to confirm boot.

## Why this PR is analysis-only

The prior 2026.7 port took hand-crafted per-file cherry-picks with per-suite verification — the fork's approach is deliberate, not a blind merge, and CLAUDE.md documents it that way. This PR does the cataloguing so a human port can start from a mapped landscape rather than a raw diff. No code is changed in this branch.
