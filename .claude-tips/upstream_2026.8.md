# Suivi upstream — freqtrade 2026.8 (2026-09-03)

**Upstream release** : [freqtrade/freqtrade 2026.8](https://github.com/freqtrade/freqtrade/releases/tag/2026.8)
**Base fork** : `__version__ = "2026.6"` avec les features 2026.7 déjà portées (`505bf3812 feat(upstream): port the 2026.7 features the fork was missing`)
**Compare** : https://github.com/freqtrade/freqtrade/compare/2026.7...2026.8 — 299 commits, 205 fichiers

Document d'analyse. **Aucun code applicatif n'est modifié dans cette PR**. Elle prépare une PR de portage manuelle à venir.

---

## TL;DR — impact fork

Le sync 2026.8 est globalement **modéré** : la majorité des changements sont refactors, tests, docs, ou dépendances. Trois points méritent une attention réelle :

1. **`balance_includes_unrealized_pnl: True` sur Hyperliquid** (2 lignes) — **changement de comportement** : ccxt mappe `total` à `marginSummary.accountValue`, qui **inclut le PnL non-réalisé**. Le solde du wallet lu par le bot changera de valeur au premier redémarrage post-upgrade. Impact sur le sizing (`available_capital`, `wallets.py`), à vérifier avant de laisser tourner en live.
2. **Normalisation des colonnes par type de candle** (nouveau `freqtrade/candle_columns.py`, 5 commits) — restructure la source de vérité pour les colonnes OHLCV. `DEFAULT_DATAFRAME_COLUMNS` est ré-exporté depuis `constants.py` pour compat descendante, mais le replay harness (`freqtrade/replay/`) et le cache OHLCV (`freqtrade/ohlcv_cache/`) doivent être audités : ils touchent aux dataframes historiques.
3. **Garde d'adoption d'ordre dans `freqtradebot.py:handle_onexchange_order`** (nouveau bloc, ~10 lignes) — refuse d'adopter un ordre déjà rattaché à un autre trade. Recoupe le travail fork `241f0329d feat(position-audit): prove order ownership and keep an auditable position trail`. À réconcilier — la garde fork est probablement déjà un sur-ensemble, mais il faut vérifier qu'aucune règle upstream ne manque.

Tout le reste (support timerange à la minute, fix hyperopt log queue, refactor shutdown async ccxt, fix websocket disconnects) peut être porté au fil de l'eau.

---

## Fichiers fork-critiques touchés par 2026.8

Recoupement avec les zones de fork listées dans `CLAUDE.md` :

| Fichier fork | Lignes upstream | Nature | Risque |
|--------------|-----------------|--------|--------|
| `freqtrade/freqtradebot.py` | 17 (+14 / -3) | Deux `.get()` safety sur `cancel_open_orders_on_exit`, `range(0,24)`→`range(24)`, **nouvelle garde d'adoption d'ordre** | 🟡 moyen — le bloc de garde recoupe `_handle_external_close` et le travail position-audit |
| `freqtrade/exchange/exchange.py` | 153 (+87 / -66) | Refactor du shutdown async ccxt (extraction `_close_async_ccxt`), nouveau `balance_includes_unrealized_pnl: False` par défaut, renommage `uid`/`accountId` | 🟢 faible — ne touche pas `_guard_shared_wallet_exit`, refactor propre |
| `freqtrade/exchange/hyperliquid.py` | 2 (+2) | Ajout `balance_includes_unrealized_pnl: True` | 🔴 **impact live** — change la lecture du solde wallet |
| `freqtrade/constants.py` | 8 (+5 / -3) | `DEFAULT_DATAFRAME_COLUMNS` déplacé vers `candle_columns.py` (ré-exporté), `MINIMAL_CONFIG` : `key`/`secret` → `api_key`/`secret` avec `None` | 🟢 faible — n'affecte pas la registration `TrendRegularityFilter` |
| `freqtrade/plugins/pairlist/*` | 7 fichiers | Refactors mineurs (IPairList, VolumePairList, VolatilityFilter, etc.) | 🟢 faible — ne touche pas `TrendRegularityFilter.py` |
| `tests/freqtradebot/test_freqtradebot.py` | — | Tests upstream mis à jour | 🟡 à porter avec la garde d'adoption d'ordre |

Aucune modif upstream sur : `freqtrade/replay/*`, `freqtrade/rpc/api_server/api_replay.py`, `freqtrade/plugins/pairlist/TrendRegularityFilter.py`, `freqtrade/fleet_coordination.py`, `freqtrade/ohlcv_cache/*`.

---

## Découpage des changements upstream

### 🔴 Rupture / changement de comportement (à décider avant portage)

| Commit | Sujet | Impact fork |
|--------|-------|-------------|
| — | `balance_includes_unrealized_pnl` sur Hyperliquid | ccxt lit maintenant `accountValue` (avec PnL non-réalisé). À valider sur un dry avant de laisser en live — modifie `available_capital`, donc le sizing DCA. Peut nécessiter un ajustement de `dry_run_wallet` ou d'`overbuy_factor`. |
| `059504e8c → 2776f7274` (5 commits) | Colonnes par type de candle (`empty_dataframe` helper, `informative` decorator candle-aware, normalisation au chargement) | Le replay harness manipule des dataframes historiques (feathers Hyperliquid, virtual clock, cache OHLCV). Auditer que la nouvelle normalisation n'introduit pas de divergences dans le seed du replay. |

### 🟡 Fonctionnel (à porter, avec conflit possible)

| Commit | Sujet | Impact fork |
|--------|-------|-------------|
| `dfa9d0442` + `60e7c957b` (PR #13478) | Support timerange à la minute (API v2.50) | Vérifier que le replay harness (virtual clock candle-par-candle) reste cohérent avec des timeranges minute. |
| `9112e674e` | `fix: don't reassign log queue in hyperopt unconditionally` | À porter tel quel — le fork utilise hyperopt régulièrement. |
| `160c23cc1` | `fix: avoid fragmented dataframe, fix mean calculation problem` | Correctness fix — porter. |
| `26810e950` + `41dbe059a` | Websocket disconnects proprement gérés + pas de nouvelles souscriptions pendant le shutdown | Auditer le shutdown fork (`fix(exchange): release the loop's workers on close so shutdown cannot hang`) — potentiel recoupement. |
| `047e5cca4` + `90db9286c` + `1b91e04a3` + `7d403867f` | FreqAI : réparation historic predictions, gestion downtime | Le fork n'utilise pas FreqAI actuellement mais garde le code. Porter par prudence. |
| `9f829f204` | `fix: unknown file layouts should be treated as empty when loading files` | Correctness fix — porter. |
| Nouvelle garde d'adoption d'ordre dans `handle_onexchange_order` | | À réconcilier avec `241f0329d feat(position-audit)`. Vérifier si la règle upstream est déjà couverte par la garde fork ; sinon compléter. |

### 🟢 Sûr / trivial (dep bumps, CI, docs)

À accepter au fil de l'eau ou à ignorer :

- **Deps** : ccxt 4.5.74→4.5.76, uvicorn 0.52.1→0.52.4, sqlalchemy 2.0.51→2.0.52, filelock 3.32.2→3.32.3, mypy 2.3.0→2.3.1, ruff 0.16.2→0.16.3
- **CI/Docker** : setup-uv 9.0.0→10.0.1, setup-buildx-action bump, devcontainer build fix
- **Docs** : timerange minute, funding rate, backtest caching, typos
- **Data** : nouveau snapshot Binance leverage tiers
- **Tests** : `AsyncMock` remplace `get_mock_coro`, tests hyperopt_logger, tests timerange format

---

## Plan d'action

1. **Cette PR** : ajoute ce suivi. Ne modifie **aucun code** applicatif. Zéro risque.
2. **PR suivi 1 — bloc "changement de comportement"** :
   - Décider de la stratégie Hyperliquid `balance_includes_unrealized_pnl`. Option A : accepter le nouveau comportement et mesurer l'impact sizing sur un dry. Option B : forcer `False` dans le fork Hyperliquid pour préserver la sémantique historique (à évaluer contre les besoins de shared-wallet).
   - Auditer replay harness contre la normalisation candle_columns. Ajouter test de régression si besoin.
3. **PR suivi 2 — features fonctionnelles** :
   - Cherry-pick les fix hyperopt, dataframe fragmenté, websocket, freqAI historic predictions, file layout empty.
   - Porter la garde d'adoption d'ordre après réconciliation avec `position-audit`.
   - Bump `__version__` à `2026.8` (ou garder `2026.6` selon la convention actuelle du fork qui décorrèle version et features portées).
4. **Deps** : accepter groupés dans une PR séparée (ou attendre Dependabot si réactivé).

---

## Ce qui n'est PAS traité par cette PR

- Le portage effectif du code — chaque item ci-dessus mérite sa propre PR, testée séparément.
- Le bump de version dans `freqtrade/__init__.py`.
- Le run des tests fork (`pytest --random-order -n auto`) sur le sync — à faire dans la PR de portage.
- La validation live/dry post-port (dry_run_replay sur les stratégies actives).
