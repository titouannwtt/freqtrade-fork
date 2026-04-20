# Freqtrade — Fork (Freqtrade France)

A fork of [freqtrade/freqtrade](https://github.com/freqtrade/freqtrade) (based on v2026.3) focused on **real-world algorithmic trading on Hyperliquid and other futures-capable exchanges**, with aggressive DCA strategies (short & long) and a few quality-of-life features that vanilla Freqtrade does not ship with yet.

I've been running Freqtrade in production for **four years now**. Over that time I've accumulated a handful of changes that made my life easier — but that are often too opinionated, too specific, or too niche to be worth submitting as features to the official Freqtrade repo. Rather than maintaining a pile of out-of-tree patches, I decided to keep them in a public fork, so that:

- I can iterate freely on the parts that matter to my stack (Hyperliquid, DCA, fleet monitoring) without waiting for upstream review.
- Anyone who finds one of these changes useful can **cherry-pick it into their own setup** — or use this whole fork as a drop-in replacement. Everything here is GPL-3.0, just like upstream.

Upstream Freqtrade is already excellent as a general-purpose trading framework. This fork adds the handful of things I've needed while running several bots in production: automatic recovery when a position is closed externally (ADL, manual close on the exchange UI), first-class liquidation detection on Hyperliquid, a pairlist filter built for short-only strategies, a custom hyperopt loss, a more ergonomic hyperopt CLI, and a redirect so `freqtrade install-ui` pulls my companion FreqUI fork.

<p align="center">
  <img src=".readme_illustrations/frequi-dashboard-overview.png" alt="FreqUI fork dashboard — pulled automatically by 'freqtrade install-ui' in this fork" width="900">
</p>

> Screenshot above: the FreqUI fork that `freqtrade install-ui` pulls in this fork. See [titouannwtt/frequi-fork](https://github.com/titouannwtt/frequi-fork) for the full UI inventory.

---

## English

### Why this fork?

Five concrete motivations on top of the rationale above:

1. **Hyperliquid-grade resiliency.** On DEXes (and sometimes on CEXes too) a position can disappear from under you — ADL, manual close from the web UI, liquidation. Vanilla Freqtrade loses sync in those cases and keeps looping. This fork detects all three cases and closes the trade cleanly in the DB.
2. **A complete FreqUI overhaul.** The stock FreqUI is functional but minimal. I wanted fleet-level monitoring, rich popovers with market context (BTC/ETH benchmarks, Fear & Greed index), per-bot alerts, drag-and-drop dashboard layout, and full i18n. So I built [titouannwtt/frequi-fork](https://github.com/titouannwtt/frequi-fork) — a near-complete rewrite of the UI. In this fork, `freqtrade install-ui` pulls it automatically, no extra setup needed.
3. **Short-DCA friendly tools.** A pairlist filter that excludes pairs with a strong linear uptrend (high R² on price regression), a custom hyperopt loss tuned for DCA strategies, and a hyperopt CLI that lets you swap Optuna samplers without touching your strategy file.
4. **A more powerful hyperopt CLI.** Vanilla Freqtrade hardcodes the Optuna sampler. This fork adds a `--sampler` flag that lets you pick from six samplers (TPE, NSGA-II, NSGA-III, CMA-ES, GP, QMC) without editing your strategy — useful for A/B testing convergence approaches across different loss functions.
5. **Sensible defaults for a full stack.** Launch scripts with auto-restart, a download script for recent data, ready-to-use backtest configs for 6 exchanges, and live config templates with API key placeholders.

### What's added on top of upstream freqtrade/stable

Concrete list of fork-only changes (27 files, +832 / -213 lines vs. `upstream/stable`):

#### Trading engine

| File | Added | Purpose |
|------|-------|---------|
| `freqtrade/freqtradebot.py` | +139 lines | **`_handle_external_close()`** — detects positions closed externally (ADL on Hyperliquid, manual close from the exchange UI) and closes the trade in the DB at market price with `exit_reason="external_close"`. Without this, vanilla Freqtrade loses sync and loops indefinitely trying to manage a position that no longer exists. |
| `freqtrade/exchange/hyperliquid.py` | +77 lines | **`fetch_liquidation_fills()`** — polls Hyperliquid for user trades containing a `liquidationMarkPx` field, so the bot knows when a position has actually been liquidated and closes the trade with the correct price instead of hanging. |
| `freqtrade/wallets.py` | +27 lines | Support changes for external-close & liquidation paths (balance refresh, closed-profit accounting). |
| `freqtrade/rpc/rpc.py` | +19 lines | Expose the new exit reasons to the API / Telegram layer. |
| `freqtrade/rpc/telegram.py` | +9 lines | Telegram messages for `external_close` and liquidation events. |
| `freqtrade/rpc/api_server/api_schemas.py` | +2 lines | Schema additions for the new exit reasons. |
| `freqtrade/exchange/exchange.py` | +12 lines | Hook points consumed by `hyperliquid.py`. |
| `freqtrade/data/metrics.py` | +7 lines | Small adjustments consumed by the custom hyperopt loss. |

#### Pairlist filters

| File | Added | Purpose |
|------|-------|---------|
| `freqtrade/plugins/pairlist/TrendRegularityFilter.py` | +222 lines | **New filter** — excludes pairs whose price has a strong linear uptrend (high R² on linear regression). Meant for short-only strategies: you don't want to short a coin that's trending straight up. |
| `freqtrade/constants.py` | +1 line | Registers `TrendRegularityFilter` in `AVAILABLE_PAIRLISTS`. |

#### Hyperopt

| File | Added | Purpose |
|------|-------|---------|
| `freqtrade/optimize/hyperopt_loss/hyperopt_loss_my_profit_drawdown.py` | +54 lines | **New hyperopt loss** — profit × drawdown-penalty with a configurable `DRAWDOWN_MULT`. Used as a baseline when tuning DCA strategies. |
| `freqtrade/commands/cli_options.py` | +21 lines | **New `--sampler` CLI option** for `freqtrade hyperopt`. Choices: `NSGAIIISampler` (default, genetic multi-objective — good Pareto diversity), `NSGAIISampler` (older variant), `TPESampler` (Bayesian, fast convergence on single-objective losses), `CmaEsSampler` (gradient-free for continuous spaces), `GPSampler` (Gaussian-Process Bayesian), `QMCSampler` (Quasi-Monte Carlo — pure exploration). Overrides whatever `HyperOpt.generate_estimator()` returns, so you can A/B samplers without editing the strategy. |
| `freqtrade/commands/arguments.py` | +1 line | Wires `--sampler` into `ARGS_HYPEROPT`. |
| `freqtrade/configuration/configuration.py` | +1 line | Logs the selected sampler when `--sampler` is used. |
| `freqtrade/optimize/hyperopt/hyperopt_optimizer.py` | 1-line change | `get_optimizer()` uses the CLI-selected sampler when present, falls back to the strategy's default otherwise. |

#### FreqUI integration

| File | Added | Purpose |
|------|-------|---------|
| `freqtrade/commands/deploy_ui.py` | 1-line change | `freqtrade install-ui` now fetches FreqUI from [titouannwtt/frequi-fork](https://github.com/titouannwtt/frequi-fork) instead of the upstream repo. That companion fork is a near-complete UI overhaul with fleet-level monitoring, rich popovers, market context, per-bot alerts, and i18n — see its README for the full inventory. |
| `docs/freq-ui.md` | 2-line change | Doc links updated accordingly. |

#### Config & scripts

| File | Added | Purpose |
|------|-------|---------|
| `freqtrade/config_schema/config_schema.py` | +12 lines | Schema additions for the new features. |
| `config_examples/config_full.example.json` | +1 line | Example of the new config keys. |
| `build_helpers/schema.json` | +3 lines | Same as above. |
| `launch_bot.sh` | new file | Runs a bot with an auto-restart loop + 60 s grace period (Ctrl-C before the countdown to stop). |
| `launch_dashboard.sh` | new file | Same, but for `freqtrade webserver` (UI-only mode — no trading). |
| `download.sh` | new file | Downloads the last 10 days of candles for all configs in `backtest_configs/`. |
| `.gitignore` | +32 lines | Keeps your `live_configs/`, `backtest_configs/`, `database/`, `.claude/` and any `*access*.json` / `*credentials*` / `*secret*` / `*.key` / `*.pem` strictly local. |

### How to use this fork

```bash
git clone https://github.com/titouannwtt/freqtrade-fork.git
cd freqtrade-fork
./setup.sh -i                     # same setup flow as upstream

# Install the companion FreqUI fork (pulled automatically from titouannwtt/frequi-fork)
freqtrade install-ui

# Put your bot configs in live_configs/ (it's gitignored — your API keys stay local)
cp /path/to/my_bot.json live_configs/

# Run a bot with auto-restart — its own FreqUI is served on the API port by default
./launch_bot.sh my_bot.json

# Optional: run a dedicated "master" instance in webserver-only mode, no trading
# Handy when you have several trading bots and want one central UI to drive them all
./launch_dashboard.sh my_bot.json
```

About the FreqUI host: by default, **every `freqtrade trade` instance already hosts FreqUI on its own API port** (set by `api_server.listen_ip_address` / `listen_port` in its config). So if you're running a single bot, you don't need anything special — just open its API URL in a browser. If you run several bots, you have two equivalent options:

- **Master-bot approach**: use one of your regular trading bots as the "host". Point FreqUI at all the other bots' API ports via the UI login screen. Nothing extra to deploy.
- **Dedicated dashboard approach**: run an extra process in [webserver mode](https://www.freqtrade.io/en/stable/utils/#webserver-mode) (no trading, just serving the UI) — that's what `launch_dashboard.sh` does. Useful if you'd rather not have a trading bot be responsible for serving your UI.

Either way, the UI is the same FreqUI fork that `install-ui` pulled.

Everything else (pairlists, strategies, hyperopt, backtesting) works exactly like upstream — check the [official Freqtrade docs](https://www.freqtrade.io/en/stable/). The fork only adds features, it does not change existing behavior.

#### Using the `--sampler` option

```bash
# Default (NSGA-III, as before)
freqtrade hyperopt --strategy MyStrategy --spaces buy sell --epochs 500

# Swap the sampler without touching the strategy
freqtrade hyperopt --strategy MyStrategy --spaces buy sell --epochs 500 --sampler TPESampler
freqtrade hyperopt --strategy MyStrategy --spaces buy sell --epochs 500 --sampler CmaEsSampler
```

Rule of thumb: TPE converges faster on single-objective losses, NSGA-III keeps more diversity across the Pareto front.

#### Using `TrendRegularityFilter`

In your config's `pairlists` section:

```json
{
  "method": "TrendRegularityFilter",
  "lookback_days": 30,
  "max_r_squared": 0.85,
  "min_slope": 0
}
```

Pairs whose 30-day price regression has an R² above `0.85` and a positive slope get filtered out — good hygiene for short-only strategies.

### Companion repos

- **[titouannwtt/frequi-fork](https://github.com/titouannwtt/frequi-fork)** — my FreqUI fork. Fleet monitoring, rich popovers, market context (BTC/ETH benchmarks, Fear & Greed), per-bot alerts, drag-and-drop dashboard, full i18n. `freqtrade install-ui` in this fork already points here.
- **[titouannwtt/freqtrade-france-strategies_simple_vwap](https://github.com/titouannwtt/freqtrade-france-strategies_simple_vwap)** — a simple VWAP-based strategy with all its backtesting / hyperopt scaffolding.
- **[titouannwtt/freqtrade-france-strategies-kac-index](https://github.com/titouannwtt/freqtrade-france-strategies-kac-index)** — KAC-Index strategies and associated research.
- **[titouannwtt/freqtrade_basics](https://github.com/titouannwtt/freqtrade_basics)** — basic strategy templates, useful to get started.

### Freqtrade France — tutorials & community (FR)

I publish French-language tutorials on algorithmic trading with Freqtrade here:

**<https://buymeacoffee.com/freqtrade_france/posts>**

Free guides covering installation, config files, strategy files, order types, backtests, hyperopt, compounding, and connecting Freqtrade to Hyperliquid. A paid membership (9 EUR / month) unlocks access to my strategies, a Discord server, and all premium content.

### A note on French regulation

If you're trading from France:

- **PSAN-registered exchanges** (recommended): Binance, Kraken, Bitget, Bybit, OKX (via MyOKX EEA), Gate.io, Bitvavo.
- **Hyperliquid** is a DEX with no KYC — not subject to PSAN/DASP registration. It is the primary exchange this fork is tested against. Referral link: <https://app.hyperliquid.xyz/join/MOUTON>.
- **Not recommended for French residents**: HTX (ex-Huobi), Bitmart — not PSAN-registered.

Rules evolve — always check the [AMF PSAN registry](https://www.amf-france.org/fr/espace-professionnels/fintech/mes-relations-avec-lamf/obtenir-un-enregistrement-un-agrement-psan) before committing real money.

### Disclaimer

This software is for educational purposes only. Do not risk money you cannot afford to lose. **THE AUTHORS ASSUME NO LIABILITY FOR YOUR TRADING RESULTS.**

### License

Same license as upstream Freqtrade (GPL-3.0).

---

## Français

### Pourquoi ce fork ?

J'utilise Freqtrade en production depuis **quatre ans**. Au fil du temps, j'ai accumulé un petit lot de modifications qui me simplifient la vie — mais qui sont souvent trop spécifiques, trop orientées par mon usage, ou trop de niche pour mériter d'être proposées en tant que features au repo Freqtrade officiel. Plutôt que de maintenir une pile de patches hors de l'arbre, j'ai choisi de tout garder dans un fork public, pour que :

- Je puisse itérer librement sur les parties qui comptent pour ma stack (Hyperliquid, DCA, monitoring multi-bots) sans attendre de review upstream.
- N'importe qui qui trouve une de ces modifs utile puisse **la reprendre dans son propre setup** — ou utiliser ce fork entier comme remplacement direct. Tout est sous GPL-3.0, comme l'upstream.

Au-delà de ça, cinq motivations concrètes :

1. **Résilience type Hyperliquid.** Sur les DEX (et parfois sur CEX aussi), une position peut disparaître sous tes pieds — ADL, fermeture manuelle depuis l'UI de l'exchange, liquidation. Freqtrade vanilla perd la sync dans ces cas-là et boucle indéfiniment. Ce fork détecte les trois cas et ferme proprement le trade dans la DB.
2. **Une refonte complète de FreqUI.** L'interface stock de FreqUI est fonctionnelle mais minimaliste. Je voulais du monitoring de flotte, des popovers riches avec contexte de marché (benchmarks BTC/ETH, indice Fear & Greed), des alertes par bot, un dashboard drag-and-drop, et une i18n complète. J'ai donc construit [titouannwtt/frequi-fork](https://github.com/titouannwtt/frequi-fork) — une réécriture quasi-totale de l'UI. Dans ce fork, `freqtrade install-ui` la récupère automatiquement, aucun setup supplémentaire.
3. **Outils pensés pour le DCA short.** Un filtre de pairlist qui exclut les paires en tendance haussière régulière (R² élevé sur régression linéaire du prix), une loss hyperopt custom calibrée pour les stratégies DCA, et une CLI hyperopt qui permet de changer de sampler Optuna sans toucher au fichier de stratégie.
4. **Un CLI hyperopt plus puissant.** Freqtrade vanilla hardcode le sampler Optuna. Ce fork ajoute un flag `--sampler` qui permet de choisir parmi six samplers (TPE, NSGA-II, NSGA-III, CMA-ES, GP, QMC) sans éditer la stratégie — utile pour A/B tester les approches de convergence selon la loss function utilisée.
5. **Stack complet utilisable d'emblée.** Scripts de lancement avec auto-restart, script de téléchargement des données récentes, configs de backtest prêtes à l'emploi pour 6 exchanges, et templates de configs live avec placeholders pour les clés API.

### Ce que ce fork apporte vs. upstream freqtrade/stable

Liste concrète des changements (27 fichiers, +832 / -213 lignes vs. `upstream/stable`) :

#### Moteur de trading

| Fichier | Ajouté | Rôle |
|---------|--------|------|
| `freqtrade/freqtradebot.py` | +139 lignes | **`_handle_external_close()`** — détecte les positions fermées en externe (ADL Hyperliquid, fermeture manuelle via l'UI) et ferme le trade en DB au prix marché avec `exit_reason="external_close"`. Sans ça, Freqtrade vanilla perd la sync et boucle à l'infini sur une position qui n'existe plus. |
| `freqtrade/exchange/hyperliquid.py` | +77 lignes | **`fetch_liquidation_fills()`** — interroge Hyperliquid pour les trades utilisateur contenant un champ `liquidationMarkPx`, pour que le bot sache quand une position a été liquidée et ferme le trade au bon prix au lieu de rester bloqué. |
| `freqtrade/wallets.py` | +27 lignes | Support pour les chemins external-close & liquidation (refresh du solde, comptabilité des closed profits). |
| `freqtrade/rpc/rpc.py` | +19 lignes | Expose les nouveaux exit reasons à la couche API / Telegram. |
| `freqtrade/rpc/telegram.py` | +9 lignes | Messages Telegram pour `external_close` et les liquidations. |
| `freqtrade/rpc/api_server/api_schemas.py` | +2 lignes | Schemas pour les nouveaux exit reasons. |
| `freqtrade/exchange/exchange.py` | +12 lignes | Hooks utilisés par `hyperliquid.py`. |
| `freqtrade/data/metrics.py` | +7 lignes | Petits ajustements utilisés par la loss hyperopt custom. |

#### Filtres de pairlist

| Fichier | Ajouté | Rôle |
|---------|--------|------|
| `freqtrade/plugins/pairlist/TrendRegularityFilter.py` | +222 lignes | **Nouveau filtre** — exclut les paires dont le prix a une tendance haussière linéaire forte (R² élevé sur régression linéaire). Pensé pour les stratégies short : on ne veut pas shorter un coin qui monte droit. |
| `freqtrade/constants.py` | +1 ligne | Enregistre `TrendRegularityFilter` dans `AVAILABLE_PAIRLISTS`. |

#### Hyperopt

| Fichier | Ajouté | Rôle |
|---------|--------|------|
| `freqtrade/optimize/hyperopt_loss/hyperopt_loss_my_profit_drawdown.py` | +54 lignes | **Nouvelle loss hyperopt** — profit × pénalité drawdown avec `DRAWDOWN_MULT` configurable. Utilisée comme baseline pour tuner les stratégies DCA. |
| `freqtrade/commands/cli_options.py` | +21 lignes | **Nouvelle option `--sampler`** pour `freqtrade hyperopt`. Choix : `NSGAIIISampler` (défaut, génétique multi-objectif — bonne diversité Pareto), `NSGAIISampler` (variante plus ancienne), `TPESampler` (bayésien, convergence rapide sur losses mono-objectif), `CmaEsSampler` (sans gradient, pour espaces continus), `GPSampler` (bayésien à processus gaussien), `QMCSampler` (Quasi-Monte Carlo — exploration pure). Écrase ce que retourne `HyperOpt.generate_estimator()`, donc tu peux A/B tester les samplers sans éditer la stratégie. |
| `freqtrade/commands/arguments.py` | +1 ligne | Branche `--sampler` dans `ARGS_HYPEROPT`. |
| `freqtrade/configuration/configuration.py` | +1 ligne | Log du sampler choisi quand `--sampler` est utilisé. |
| `freqtrade/optimize/hyperopt/hyperopt_optimizer.py` | 1 ligne modifiée | `get_optimizer()` utilise le sampler CLI si présent, fallback sur le défaut de la stratégie sinon. |

#### Intégration FreqUI

| Fichier | Ajouté | Rôle |
|---------|--------|------|
| `freqtrade/commands/deploy_ui.py` | 1 ligne modifiée | `freqtrade install-ui` récupère maintenant FreqUI depuis [titouannwtt/frequi-fork](https://github.com/titouannwtt/frequi-fork) au lieu du repo upstream. Ce fork complémentaire est une refonte quasi-complète de l'UI — monitoring de flotte, popovers riches, contexte de marché, alertes par bot, i18n. Voir son README pour l'inventaire complet. |
| `docs/freq-ui.md` | 2 lignes modifiées | Liens de doc mis à jour en conséquence. |

#### Config & scripts

| Fichier | Ajouté | Rôle |
|---------|--------|------|
| `freqtrade/config_schema/config_schema.py` | +12 lignes | Ajouts schema pour les nouvelles features. |
| `config_examples/config_full.example.json` | +1 ligne | Exemple des nouvelles clés de config. |
| `build_helpers/schema.json` | +3 lignes | Idem. |
| `launch_bot.sh` | nouveau | Lance un bot avec boucle d'auto-restart + grâce de 60 s (Ctrl-C avant le compte à rebours pour stopper). |
| `launch_dashboard.sh` | nouveau | Pareil, mais pour `freqtrade webserver` (mode UI seule — pas de trading). |
| `download.sh` | nouveau | Télécharge les 10 derniers jours de bougies pour toutes les configs de `backtest_configs/`. |
| `.gitignore` | +32 lignes | Garde `live_configs/`, `backtest_configs/`, `database/`, `.claude/` et tout `*access*.json` / `*credentials*` / `*secret*` / `*.key` / `*.pem` strictement local. |

### Comment utiliser ce fork

```bash
git clone https://github.com/titouannwtt/freqtrade-fork.git
cd freqtrade-fork
./setup.sh -i                     # même flow d'install que l'upstream

# Installe le fork FreqUI (récupéré automatiquement depuis titouannwtt/frequi-fork)
freqtrade install-ui

# Place tes configs de bot dans live_configs/ (gitignored — tes clés API restent locales)
cp /chemin/vers/mon_bot.json live_configs/

# Lance un bot avec auto-restart — son FreqUI est servi sur le port de son API par défaut
./launch_bot.sh mon_bot.json

# Optionnel : une instance "maître" dédiée en mode webserver-only, sans trading
# Utile quand tu as plusieurs bots et que tu veux une UI centralisée pour tous les piloter
./launch_dashboard.sh mon_bot.json
```

Qui héberge FreqUI ? Par défaut, **chaque instance `freqtrade trade` sert déjà FreqUI sur son propre port d'API** (défini par `api_server.listen_ip_address` / `listen_port` dans sa config). Donc si tu tournes un seul bot, rien à faire de spécial — il suffit d'ouvrir l'URL de son API dans un navigateur. Si tu tournes plusieurs bots, deux options équivalentes :

- **Approche bot-maître** : utilise un de tes bots de trading habituels comme hôte. Depuis l'écran de login de FreqUI, pointe vers les APIs des autres bots. Rien de plus à déployer.
- **Approche dashboard dédié** : lance un process supplémentaire en [mode webserver](https://www.freqtrade.io/en/stable/utils/#webserver-mode) (pas de trading, juste l'UI) — c'est ce que fait `launch_dashboard.sh`. Utile si tu préfères ne pas confier la responsabilité de servir ton UI à un bot de trading.

Dans les deux cas, l'UI est le même fork FreqUI que `install-ui` a récupéré.

Tout le reste (pairlists, stratégies, hyperopt, backtesting) fonctionne exactement comme l'upstream — voir la [doc officielle Freqtrade](https://www.freqtrade.io/en/stable/). Le fork n'ajoute que des fonctionnalités, il ne change pas le comportement existant.

#### Utiliser l'option `--sampler`

```bash
# Défaut (NSGA-III, comme avant)
freqtrade hyperopt --strategy MaStrategie --spaces buy sell --epochs 500

# Changer de sampler sans toucher à la stratégie
freqtrade hyperopt --strategy MaStrategie --spaces buy sell --epochs 500 --sampler TPESampler
freqtrade hyperopt --strategy MaStrategie --spaces buy sell --epochs 500 --sampler CmaEsSampler
```

Règle générale : TPE converge plus vite sur des losses mono-objectif, NSGA-III garde plus de diversité sur le front de Pareto.

#### Utiliser `TrendRegularityFilter`

Dans la section `pairlists` de ta config :

```json
{
  "method": "TrendRegularityFilter",
  "lookback_days": 30,
  "max_r_squared": 0.85,
  "min_slope": 0
}
```

Les paires dont la régression linéaire sur 30 jours a un R² au-dessus de `0.85` et une pente positive sont filtrées — hygiène utile pour les stratégies short only.

### Autres repos associés

- **[titouannwtt/frequi-fork](https://github.com/titouannwtt/frequi-fork)** — mon fork de FreqUI. Monitoring de flotte, popovers riches, contexte de marché (benchmarks BTC/ETH, Fear & Greed), alertes par bot, dashboard drag-and-drop, i18n complète. `freqtrade install-ui` dans ce fork pointe déjà dessus.
- **[titouannwtt/freqtrade-france-strategies_simple_vwap](https://github.com/titouannwtt/freqtrade-france-strategies_simple_vwap)** — stratégie simple basée sur le VWAP avec tout le scaffolding backtesting / hyperopt.
- **[titouannwtt/freqtrade-france-strategies-kac-index](https://github.com/titouannwtt/freqtrade-france-strategies-kac-index)** — stratégies KAC-Index et recherche associée.
- **[titouannwtt/freqtrade_basics](https://github.com/titouannwtt/freqtrade_basics)** — templates de stratégies de base, utile pour démarrer.

### Freqtrade France — tutoriels & communauté

Je publie mes tutoriels francophones sur le trading algorithmique avec Freqtrade ici :

**<https://buymeacoffee.com/freqtrade_france/posts>**

Guides gratuits sur l'installation, les fichiers de config, les fichiers de stratégies, les types d'ordres, les backtests, l'hyperopt, le compounding, et la connexion Freqtrade → Hyperliquid. Un membership payant (9 EUR / mois) débloque l'accès à mes stratégies, un serveur Discord et tout le contenu premium.

### Exchanges et réglementation française

Si tu trades depuis la France :

- **Exchanges enregistrés PSAN (recommandés)** : Binance, Kraken, Bitget, Bybit, OKX (via MyOKX EEA), Gate.io, Bitvavo.
- **Hyperliquid** est un DEX sans KYC — non soumis à l'enregistrement PSAN/DASP. C'est l'exchange principal contre lequel ce fork est testé. Lien de parrainage : <https://app.hyperliquid.xyz/join/MOUTON>.
- **Non recommandés pour les résidents français** : HTX (ex-Huobi), Bitmart — pas enregistrés PSAN.

La réglementation évolue — vérifie toujours le [registre AMF des PSAN](https://www.amf-france.org/fr/espace-professionnels/fintech/mes-relations-avec-lamf/obtenir-un-enregistrement-un-agrement-psan) avant de mettre de l'argent réel.

### Disclaimer

Ce logiciel est à usage éducatif uniquement. Ne risquez pas d'argent que vous ne pouvez pas vous permettre de perdre. **LES AUTEURS N'ASSUMENT AUCUNE RESPONSABILITÉ POUR VOS RÉSULTATS DE TRADING.**

### Licence

Même licence que Freqtrade upstream (GPL-3.0).
