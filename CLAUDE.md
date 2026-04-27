# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Trading guardrails — `.claude-tips/` (LIRE AVANT TOUTE ACTION TRADING)

Avant toute action liée au trading algorithmique (création/modification de stratégie, backtest, hyperopt, diagnostic live, sizing, pairlist, etc.), Claude DOIT :

1. **Consulter `.claude-tips/README.md`** pour identifier les fichiers de tips pertinents selon la demande utilisateur (table de correspondance incluse).
2. **Lire les fichiers identifiés** et appliquer les règles strictes (🚫) sans exception.
3. **Si l'utilisateur propose une approche qui contredit une règle stricte** :
   - Signaler le conflit clairement
   - Citer le tip et sa source (ex: "tips.txt #40, Beetcoin")
   - Expliquer pourquoi c'est problématique
   - Proposer une alternative conforme
4. **Si l'utilisateur insiste malgré l'avertissement** : exécuter, mais documenter l'avertissement dans un commentaire de code ou dans la réponse.
5. **Bonnes pratiques (✅)** : appliquer par défaut, justifier toute exception.
6. **Conseils avancés (💡)** : évaluer si le contexte s'applique avant de proposer.

**Source de vérité** : `tips.txt` à la racine (199 tips complets). Les fichiers `.claude-tips/*.md` sont des index actionnables par catégorie. En cas de divergence, `tips.txt` prime.

**Contexte par défaut** : DCA mean-reversion (long oversold + short overbought) sur Hyperliquid USDC perps en 15m. En cas de doute, prioriser `mean_reversion.md` et `risk_management.md`.

## What is this repo

Fork of [freqtrade/freqtrade](https://github.com/freqtrade/freqtrade) (v2026.3) focused on **Hyperliquid futures trading** with aggressive DCA short strategies. The fork adds liquidation/ADL detection, external position close handling, and a custom pairlist filter.

**Owner:** titouannwtt (private repo)
**Upstream:** `upstream` remote → `https://github.com/freqtrade/freqtrade.git`

## Common commands

```bash
# Install / update after merge
.venv/bin/pip install -e .

# Run a bot (inside a screen session)
./launch_bot.sh hyperliquid_hippo_dynv1_short_sharpe.json

# Run tests
pytest --random-order -n auto

# Run a single test
pytest tests/test_freqtradebot.py::test_function_name -x

# Lint (ruff, line-length=100, max-complexity=12)
ruff check freqtrade/
ruff format freqtrade/

# Type check
mypy freqtrade/

# Query a trade database (no sqlite3 binary, use python)
python3 -c "import sqlite3; c=sqlite3.connect('database/xxx.sqlite').cursor(); ..."
```

## Architecture overview

### Core trading loop
`freqtradebot.py` → `process()` is called each cycle:
1. `create_trades()` → entry signals → `custom_stake_amount()` → place orders
2. `manage_open_orders()` → `update_trade_state()` for pending orders
3. `exit_positions()` → check wallet sync → exit signals → `execute_trade_exit()`

When wallet mismatch detected (position gone from exchange):
- `handle_onexchange_order()` → `_handle_liquidation()` → `_handle_external_close()`

### Strategy parameter loading (important gotcha)
Priority: **JSON file > buy_params dict > DecimalParameter default**

Each strategy `Foo.py` can have a co-located `Foo.json` (hyperopt output) that **silently overrides** `buy_params`/`sell_params` in the Python code. Always check the JSON file for actual live values.

### Position sizing flow (DCA strategies)
```
wallets.py: available_amount = available_capital - capital_withdrawal + total_closed_profit (DB)
wallets.py: proposed_stake = available_amount / max_open_trades
strategy:   custom_stake = (proposed_stake / max_so_multiplier * overbuy_factor) * tradable_balance_ratio
strategy:   DCA orders = custom_stake * safety_order_volume_scale^(n-1)
```

**Critical:** `total_closed_profit` is cumulative from the DB — stake grows with profits and shrinks with losses (silent compounding). After months of gains, the bot may be taking positions 50%+ larger than at startup. See `.claude-tips/live_trading.md` § "Capital & sizing" for the full analysis.

Config's `tradable_balance_ratio` (in live_configs/*.json) is used by `wallets.py`, NOT by the strategy. The strategy has its own `tradable_balance_ratio` class attribute.

**Config coherence rules:** `dry_run_wallet` must equal `available_capital` (otherwise dry-run simulates wrong sizing). `available_capital` must not exceed actual exchange wallet balance. Changing `max_open_trades` directly changes per-trade sizing (MOT 5→3 = +67% stake per trade).

## Custom modifications (fork-specific)

### 1. External close handler (`freqtradebot.py:_handle_external_close`)
Detects positions closed externally (Hyperliquid ADL, manual close on exchange UI). When a trade is open in DB but position is 0 on exchange and it's not a liquidation, closes the trade at market price with `exit_reason="external_close"`.

### 2. Liquidation detection (`exchange/hyperliquid.py:fetch_liquidation_fills`)
Fetches user trades and checks for `liquidationMarkPx` field to detect liquidations. Called by `_handle_liquidation()` in the main bot loop.

### 3. TrendRegularityFilter (`plugins/pairlist/TrendRegularityFilter.py`)
Pairlist filter that excludes pairs with strong linear uptrends (high R² on price regression). Useful for short-only strategies. Registered in `constants.py:AVAILABLE_PAIRLISTS`.

## File layout

| Path | Purpose |
|------|---------|
| `live_configs/` | Bot JSON configs (one per bot instance) |
| `live_configs/_hyperliquid_freqtrade_access.json` | API keys (**gitignored, never commit**) |
| `user_data/strategies/` | All custom strategies (.py) + hyperopt params (.json) |
| `database/` | SQLite trade databases (one per bot) |
| `launch_bot.sh` | Bot launcher with auto-restart loop (60s grace period) |
| `freqtrade/freqtradebot.py` | Core bot logic (custom: `_handle_external_close`) |
| `freqtrade/exchange/hyperliquid.py` | Hyperliquid adapter (custom: liquidation detection) |
| `freqtrade/plugins/pairlist/TrendRegularityFilter.py` | Custom pairlist filter |
| `freqtrade/constants.py` | Pairlist registry (custom: TrendRegularityFilter added) |

## Bots currently running

Bots run in `screen` sessions. List with `screen -ls`. Each bot has:
- A config in `live_configs/`
- A database in `database/`
- A strategy in `user_data/strategies/`

To check a bot's logs: `screen -S <session> -X hardcopy -h /tmp/out.txt && tail -50 /tmp/out.txt`

## Updating from upstream

```bash
git fetch upstream --tags
git merge upstream/stable --no-edit
# Resolve conflicts (usually .github/ CI files → accept theirs)
# Verify custom code preserved: grep _handle_external_close freqtrade/freqtradebot.py
.venv/bin/pip install -e .
```

## Hyperopt methodology

For the staged methodology, red flags, and loss function reference, see [HYPEROPT_PLAYBOOK.md](./HYPEROPT_PLAYBOOK.md).
For the current HippoDCA v5 optimization journal, see [HIPPODCA_V4_STUDY.md](./HIPPODCA_V4_STUDY.md).

### Hard rules

- **Never pipe hyperopt through `tee`**. The user watches the live progress bar in `screen` — `tee` buffers carriage returns and hides it. The `.fthypt` file already persists all epochs.
- **Always use `--timeframe-detail 1m`** for hyperopt and backtests. Without it, fills are simulated at candle open price, which creates "phantom trades" that look profitable on 15m but aren't in reality. The optimizer overfits to these fake fills. With 1m detail, DCA triggers, stoploss hits, and exits are simulated on real intra-candle price movement — params are fewer but higher quality (SQN 12.88 vs 6.76 in our tests). If 1m data is unavailable or compute is too expensive, `--timeframe-detail 5m` is an acceptable fallback but **warn the user** that results may overestimate trade count and profit.
- **Always train on the target exchange.** Params trained on Binance USDT do NOT transfer to Hyperliquid USDC. Different liquidity, spreads, funding rates, and price action. A strategy profitable on Binance can produce -99% drawdown on Hyperliquid with the same params.
- **Always train on recent data (12-18 months max).** Training on 6 years (2020-2026) produces params overfitted to the 2021 bullrun. The massive gains from that period dominate any loss function and produce entries that accept catastrophic losses in current market conditions.
- **Delete the co-located `.json` before running hyperopt on a strategy.** The JSON file silently overrides `buy_params` dict and `DecimalParameter` defaults. If left in place, your hyperopt may not actually vary the params you think it's optimizing.
- **No `logger.info` / `logger.debug` / `logger.warning` in strategy hot paths during hyperopt.** Any message emitted × 28 workers × 40 pairs × thousands of candles saturates the multiprocessing log queue → main thread blocks rendering rich tables → hyperopt runs **3× slower** or appears stalled (epoch counter frozen, fthypt file not updating). For **hyperopt**: only `logger.error` should remain (rare, real errors). For **backtest and live**: all levels are fine — keep them. Pattern when a debug message is genuinely useful: wrap with `if logger.isEnabledFor(logging.DEBUG): logger.debug(...)` so the format string is never built. Always audit `custom_stake_amount`, `confirm_trade_entry`, `adjust_trade_position`, `custom_exit`, `confirm_trade_exit` before launching hyperopt — these are the per-candle hot paths.

### Loss function selection

Pick the loss function based on the strategy's **intended behavior**, not just "what sounds good":

| Strategy behavior | Use | Do NOT use |
|---|---|---|
| Patient (waits days/weeks for setups) | `CalmarHyperOptLoss` | `SharpeHyperOptLossDaily` (penalizes inactivity) |
| Frequent (trades every day) | `SharpeHyperOptLossDaily` | `CalmarHyperOptLoss` (ignores consistency) |
| Safety-first (drawdown kills you) | `MaxDrawDownHyperOptLoss` | Raw profit losses |
| Diversified multi-pair | `Mouton2HyperOptLoss` | Anything without pair diversity penalty |

**Calmar = profit / max drawdown.** Best for DCA strategies that should sit out bear markets. A bot that doesn't trade for 2 weeks but avoids a -50% crash scores better than one that trades daily through the crash.

**Sharpe penalizes zero-return days.** This pushes the optimizer toward params that enter every day — exactly wrong for a mean-reversion strategy that should wait for extreme oversold setups.

### Common traps (learned from real failures)

1. **High win rate ≠ profitable.** A DCA strategy with 97% win rate can still lose -99.7% of capital. The 3% of losing trades at high leverage wipe out everything. A single -100% trade (liquidation) erases months of profits. Always check total profit AND max drawdown, never just win rate.

2. **All epochs identical = param has no effect.** If 500 epochs produce the exact same number of trades and profit regardless of parameter values, those parameters don't influence the outcome. Either the code path is dead, or other conditions dominate so completely that the optimized param is irrelevant.

3. **buy_params dict override trap.** When creating Phase N+1 from Phase N results, you MUST update `buy_params` dict values to match the converged values. The dict overrides `DecimalParameter` defaults. If you freeze a param with `optimize=False` but leave the old value in `buy_params`, freqtrade uses the dict value, not your intended default.

4. **Phase separation can backfire.** Freezing entry params (trained on period A) then optimizing trading params on period B doesn't fix overfitting — the entry signals were already wrong for period B. When entry and trading params are tightly coupled (DCA strategies), optimize them all together on the target period.

5. **`dry_run_wallet` must be realistic.** 100 USDC with 5x leverage and DCA creates absurd sizing dynamics. Each trade gets tiny capital, DCA orders scale to nothing. Use a wallet size that reflects actual deployment (1000+ USDC).

6. **`max_open_trades` changes everything for DCA.** `proposed_stake = wallet / MOT`. Reducing MOT from 5→3 nearly doubles per-trade allocation, completely changing the risk profile and DCA dynamics. Set MOT deliberately, don't leave it as an afterthought.

7. **Concentrated profit = red flag.** If 1-2 trades carry >50% of total holdout profit, the strategy didn't prove edge — it got lucky on one move. Check per-pair breakdown after every walk-forward: compute profit without the top trade. If the strategy collapses to near-zero or negative without its best trade, the params are overfitted to that specific price action (e.g. a single SPX dump). A healthy strategy should show profit spread across multiple pairs and trades. This applies even if win rate is 100% and drawdown is 0%.

### Launching hyperopts

Always run hyperopts in `screen` sessions with Telegram notification:

```bash
screen -S <session> -X stuff $'.venv/bin/freqtrade hyperopt \
  --strategy <Strategy> \
  --config <config.json> \
  --timerange YYYYMMDD-YYYYMMDD \
  --timeframe 15m \
  --timeframe-detail 1m \
  --hyperopt-loss CalmarHyperOptLoss \
  --epochs 1000 \
  --spaces buy sell \
  --sampler TPESampler \
  -j 28 \
  && /home/moutonneux/.config/claude-notify/send.sh "Hyperopt <label> TERMINE"\n'
```

To check progress: `screen -S <session> -X hardcopy -h /tmp/out.txt && tail -20 /tmp/out.txt`
To stop gracefully: `screen -S <session> -X stuff $'\003'` (sends Ctrl+C)

### Walk-forward validation

Always split the data:
- **Training**: 70-80% of available data (e.g. 2025-03 → 2026-01)
- **Holdout**: remaining 20-30% (e.g. 2026-01 → 2026-04)

Run a single backtest (not hyperopt) on the holdout period with the best params. If performance drops > 50% vs training, the params are overfitted.

### Interpreting walk-forward trade frequency drops

A drop in trade frequency on the holdout period is **not necessarily overfitting** — it can simply mean the market gave fewer opportunities. For DCA long oversold strategies, fewer trades in a calmer market is expected and healthy behavior.

Before concluding "overfitted", compare volatility metrics (ATR, daily range, volume) between training and holdout periods. If volatility dropped proportionally to trade count, the params are fine — the bot is correctly waiting for setups that don't exist in calm markets.

**It's better to be calibrated for high volatility than low volatility** — that's where the bot makes its money. In calm markets it waits, and that's exactly what we want (hence CalmarHyperOptLoss which doesn't penalize inactivity).

## Important constraints

- **Never suggest backtests.** Strategy testing is done live with small capital.
- **API keys** are in `_hyperliquid_freqtrade_access.json` — gitignored. If this file is missing, the bot won't start.
- **Never use Hyperliquid sub-accounts.** The user wants to centralize all trading volume on a single wallet (address `0xC234...`). Splitting across sub-accounts would fragment volume and dilute the per-wallet rate-limit earning (1 req per 1 USDC traded). If HL rate-limits become a problem, the fix is IP-level (VPN/proxy), never wallet-level.
- When fixing trade DB issues, use `python3` with `sqlite3` module (no `sqlite3` CLI available).
- Strategies use `"stake_amount": "unlimited"` — position sizing is entirely in `custom_stake_amount()`.
- Bot restart after code changes: `kill <pid>` then `launch_bot.sh` auto-restarts after 60s countdown, or send the command via `screen -S <session> -X stuff './launch_bot.sh ...\n'`.

## Multi-bot portfolio management

### ftcache and rate limits

This fork includes a shared OHLCV cache daemon (`freqtrade/ohlcv_cache/`) that centralizes all API calls across bots. Multiple bots trading the same pairs consume barely more rate limit than a single bot. **Do not argue that running extra bots wastes rate limit — ftcache solves this.** The marginal cost of an additional bot is only capital and server resources (CPU/RAM), not API quota.

The cache auto-disables in BACKTEST and HYPEROPT modes (see `mixin.py:_ftcache_enabled`), so backtests always hit data files directly without interference.

### Strategy tournament (A/B testing in live)

Running multiple variants of the same strategy family in dry/live simultaneously is a deliberate **tournament selection** approach, not naive diversification. Backtests and holdout periods (even with `--timeframe-detail 1m`) cannot capture slippage, fill quality, rate limit behavior, and live market microstructure. Live is the ultimate validator.

When the user launches parallel similar strategies, support it. Don't suggest consolidating prematurely — let the tournament run through a meaningful market period (ideally covering both calm and volatile phases) before drawing conclusions.

### Correlation risk across similar strategies

Multiple DCA mean-reversion bots with different parameters will enter and exit on the **same market conditions** at roughly the same time. They are highly correlated. This is fine for tournament purposes (comparing variants), but creates real risk at the portfolio level:

- **A flash crash hits all DCA short bots simultaneously.** If 5 short bots each have 200 USDC, a -50% event on all 5 is a -500 USDC loss, not a -100 USDC loss. The exposure stacks.
- **Hedging happens at the portfolio level via sizing, not via strategy count.** The user balances total capital equally between short-side and long-side strategies. If 10 short bots and 1 long bot, each short gets 100 USDC and the long gets 1000 USDC.
- **Before deploying a new strategy to live, verify it is not just a clone in disguise.** Compare: entry signals (same indicators? same thresholds?), holding periods, pair overlap, drawdown timing. If two strategies draw down on the same days on the same pairs, they offer zero marginal diversification — they're the same bet twice. A strategy that uses momentum/breakout/funding-rate-arb alongside a DCA mean-reversion bot is real diversification. Two DCA bots with different RSI thresholds is not.

### process_throttle_secs — quick reference

`process_throttle_secs` = minimum seconds between bot loop iterations. With ftcache, the main bottleneck is **detection latency** (fills, DCA, exits), not API load — ftcache shares OHLCV, tickers, and positions across all bots. The only non-cached calls per cycle are `fetch_order` (1 per open order) and `create_order`/`cancel_order` (on signals).

**Decision rule (with ftcache):** pick based on strategy timeframe, not bot count.

| Timeframe | Recommended | Why |
|---|---|---|
| 15m (our default) | **15s** | ~60 cycles/candle, DCA latency 7.5s avg — irrelevant on 15m |
| 1h+ | **30s** | Even less pressure, 30s latency is noise |
| 5m / scalping | **5-10s** | Needs fast signal detection |

**Without ftcache (vanilla freqtrade):** multiply by bot count. 1 bot = 5-10s, 5 bots = 15-20s, 10+ bots = 30-60s.

**Never go below 5s** — no benefit on 15m+, just wastes CPU and floods logs.

For the full analysis (API call breakdown per cycle, cache coverage, latency math), see `.claude-tips/live_trading.md` § "process_throttle_secs".

### entry_pricing / exit_pricing — quick reference

Current default (`_default_spot_usdc.json`): `price_side: "same"`, `price_last_balance: 1.0`, `use_order_book: true`. This is very conservative — `price_last_balance: 1.0` blends fully toward last price, making limit orders behave like taker orders. For DCA strategies with limit orders, `price_last_balance: 0.0` would maximize maker fills (0.02% vs 0.05% on Hyperliquid).

**`price_side` does NOT determine maker vs taker** — that's `order_types["entry"]` in the strategy. Backtests IGNORE entry_pricing entirely (always use candle open price), so live fill rates may differ from backtest expectations.

For the full mapping and recommendations, see `.claude-tips/live_trading.md` § "entry_pricing / exit_pricing".

### Pairlist chaining — quick reference

Standard chain: `VolumePairList(80)` → `PerformanceFilter` → `VolumePairList(40, lookback_days=7)`. First VPL is a fast 24h volume filter; second re-ranks by 7-day smoothed volume and cuts to 40.

**Known bug:** PerformanceFilter reads `min_profit` but configs write `max_profit` — the threshold parameter is silently ignored. Use `"min_profit"` in configs for the filter to actually work.

- **VolumePairList in live, StaticPairList in backtest** — VPL has `SupportsBacktesting.NO`.
- **TrendRegularityFilter only for short-only strategies** — it removes regular uptrends, which hurts long entries.
- **More pairs = more opportunities** for patient DCA strategies that wait for extreme setups.

For the full handler reference and common mistakes, see `.claude-tips/live_trading.md` § "Chaînage pairlist".

### unfilledtimeout — quick reference

Default (`_default_spot_usdc.json`): `entry: 10, exit: 10, exit_timeout_count: 0, unit: "minutes"`. Entry timeout cancels unfilled orders — if it's the only entry, the trade is deleted; if it's a DCA order, the trade stays but the safety order is cancelled. Exit timeout with `exit_timeout_count: 0` means no emergency exit escalation.

For DCA mean-reversion on 15m: **10 min is appropriate**. Shorter timeframes (5m) → 3-5 min. Longer timeframes (1h+) → 30-60 min. See `.claude-tips/live_trading.md` § "unfilledtimeout".

### Pairlist philosophy

- **VolumePairList is preferred in live** — it adapts to market conditions, catching new high-volume pairs and dropping dead ones. StaticPairList is for backtests only.
- **More pairs ≠ worse.** A strategy that only trades on extreme setups benefits from a large pair universe — more chances to find the setup. Don't reduce pair count just because some pairs had 0 trades in a 68-day holdout.
- **TrendRegularityFilter** should be added to strategies that do short without a built-in trend filter. Strategies with their own directional filter (e.g. EMA200 in v6) don't need it — double-filtering removes valid setups.

## Stopping long-running processes in screen sessions

**Never use `pkill`, `kill`, or `kill -9` to stop hyperopt or similar multi-process jobs** — this leaves orphaned joblib/loky worker processes in memory that waste RAM and CPU threads. Instead, send Ctrl+C to the screen session so the process can clean up its workers properly:

```bash
screen -S <session_name> -X stuff $'\003'
```

`$'\003'` is the ASCII code for Ctrl+C. This lets freqtrade shut down its multiprocessing workers gracefully. After sending it, wait a few seconds and verify the process group is gone with `pgrep -af <process_name>`.
