# Live Trading — Tips et garde-fous

## Règles strictes (ne jamais enfreindre)

- 🚫 **Dry-run obligatoire avant tout passage en live**. Durée minimale selon fréquence: 2-4 semaines pour HF (10+ trades/semaine, type DCA 15m), 3 mois minimum pour LF (c'est le NOMBRE DE TRADES qui donne la significance statistique, pas la durée calendrier). Idéalement même capital que prévu en live. Comparer systématiquement BT vs dry-run sur la même période. (tips.txt #28, communauté)
- 🚫 **Override OK pour ajuster la VITESSE, JAMAIS pour inverser le SIGNE**. Seule bonne décision discrétionnaire de Carver (COVID mars 2020): accélérer ce que le modèle faisait déjà. Tu peux changer la taille, jamais le sens. (tips.txt #114, Carver)
- 🚫 **Paper trading multi-jours = 3 MOIS minimum**. Un dry-run de 2 semaines sur une stratégie DCA qui fait 10 trades/semaine n'est pas probant. (tips.txt #154, Chan)
- 🚫 **Ne pas descendre sous 5m pour Freqtrade**. Sous cette TF, les frais Hyperliquid (0.02% maker / 0.05% taker) deviennent prohibitifs sur signaux faibles. 15m est un bon compromis signal/coûts. (tips.txt #155, Chan)
- 🚫 **Le programme de BACKTEST et d'EXÉCUTION DOIT être le MÊME**. Sinon bugs introduits en exécution. Le programme ne doit pas pouvoir distinguer data live vs historique. Freqtrade respecte déjà ce principe — ne jamais implémenter d'optimisations qui divergent live vs BT. (tips.txt #167, Chan)

## process_throttle_secs — guide de choix

`process_throttle_secs` fixe le **temps minimum entre deux itérations** de la boucle de trading (`process()`). Si un cycle prend 1.5s et le throttle est 15s, le bot dort 13.5s. Si le cycle dépasse le throttle, il enchaîne immédiatement (pas de sleep négatif). Le throttle est automatiquement raccourci pour s'aligner sur l'arrivée de la prochaine bougie (candle alignment).

### Ce que fait un cycle `process()` (appels API)

| Étape | Appel API | Caché par ftcache ? |
|---|---|---|
| `reload_markets()` | 1 appel (caché 60 min) | Non, mais rare |
| `refresh_pairlist()` | `get_tickers()` | ✅ Oui (partagé entre bots) |
| `refresh_latest_ohlcv()` | N appels OHLCV | ✅ Oui (partagé + coalescing) |
| `fetch_positions()` | 1 appel | ✅ Oui (partagé entre bots) |
| `manage_open_orders()` | `fetch_order()` × N ordres ouverts | ❌ Non, 1 appel/ordre/cycle |
| `exit_positions()` | `get_rates()` via tickers | ✅ Oui |
| `process_open_trade_positions()` | `get_rates()` via tickers | ✅ Oui |
| `enter_positions()` | `create_order()` × N signaux | ❌ Non, 1 appel/entrée |

**Avec ftcache actif, la charge non-cachée par cycle ≈ nombre d'ordres ouverts + ordres créés/annulés.** C'est très faible — typiquement 0 à 5 appels/cycle pour un bot DCA avec MOT ≤ 5.

### Impact du throttle

| Aspect | Throttle bas (5s) | Throttle moyen (15s) | Throttle haut (30-60s) |
|---|---|---|---|
| **Latence détection fill** | ~2.5s moyen | ~7.5s moyen | ~15-30s moyen |
| **Latence DCA** | Quasi-immédiat | ~7.5s retard max | ~30s retard max |
| **Charge API (sans ftcache)** | Élevée (12 cycles/min) | Modérée (4 cycles/min) | Faible (1-2 cycles/min) |
| **Charge API (avec ftcache)** | ~Nulle | ~Nulle | ~Nulle |
| **CPU/RAM** | Plus haut | Modéré | Minimal |

### ✅ Recommandations par contexte

**Avec ftcache (notre fork) :**

La charge API est quasi-nulle quel que soit le throttle. Le seul facteur est la **latence acceptable** pour votre stratégie :

| Contexte | Valeur | Justification |
|---|---|---|
| DCA mean-reversion 15m (notre cas) | **15s** | Un DCA n'est pas à 15s près. Détection fill en 7.5s moyen = acceptable |
| DCA mean-reversion 1h+ | **30s** | Bougie horaire → 30s de latence est négligeable |
| Stratégie à signaux rapides (5m, scalping) | **5-10s** | Besoin de réagir vite aux signaux intra-bougie |
| Dry-run / test | **15s** | Même valeur que live, pas besoin de speed |
| 50-100 bots sur même serveur | **15-20s** | Le CPU/RAM devient le facteur limitant, pas l'API |

**Sans ftcache (freqtrade vanilla) :**

Chaque bot fait TOUS les appels API lui-même. Le throttle doit protéger contre les 429 :

| Contexte | Valeur | Justification |
|---|---|---|
| 1 bot, Hyperliquid | **5-10s** | 10 req/s budget → un bot passe facilement |
| 2-5 bots, Hyperliquid | **15-20s** | Partage du budget rate-limit |
| 10+ bots, Hyperliquid | **30-60s** | Risque de cascade de 429 si trop agressif |
| 1 bot, Kraken | **30-60s** | Kraken = 1 req/s, le plus restrictif |

### 🚫 Ne jamais descendre sous 5s en live

Même avec ftcache, un throttle < 5s crée un risque de boucle trop rapide qui sature CPU/logs sans bénéfice sur du 15m. La valeur par défaut freqtrade (5s) existe pour une raison.

### 💡 Le throttle s'auto-aligne sur les bougies

Le code (`worker.py:168-177`) raccourcit automatiquement le sleep si la prochaine bougie arrive avant le prochain cycle. Avec un throttle de 15s sur du 15m, le bot fera ~60 cycles/bougie. Avec 60s, ~15 cycles/bougie. Les deux sont largement suffisants pour ne rien rater.

## Capital & sizing — available_capital, dry_run_wallet, MOT

Le sizing en mode `stake_amount: "unlimited"` repose sur une formule dynamique qui évolue avec le PnL. Mal configurée, elle crée des surprises silencieuses en live.

### La formule centrale (wallets.py)

**Avec `available_capital` configuré (notre cas) :**
```
available_amount = available_capital - capital_withdrawal + total_closed_profit
proposed_stake  = available_amount / max_open_trades
```

**Sans `available_capital` :**
```
available_amount = (capital_en_trades + solde_libre) × tradable_balance_ratio
proposed_stake  = available_amount / max_open_trades
```

`total_closed_profit` = somme des profits/pertes de TOUS les trades fermés en DB. C'est **cumulatif et permanent** — il ne se remet pas à zéro.

### Effet de compounding silencieux

Avec `available_capital: 1000`, `max_open_trades: 2`, `stake_amount: "unlimited"` :

| Événement | total_closed_profit | available_amount | proposed_stake |
|---|---|---|---|
| Démarrage | 0 | 1000 | 500 |
| +200 USDC de gains cumulés | +200 | 1200 | 600 |
| +500 USDC de gains cumulés | +500 | 1500 | 750 |
| Puis -300 USDC de perte | +200 | 1200 | 600 |
| Puis liquidation -1200 USDC | -1000 | 0 | 0 (bot bloqué) |

**Le stake monte avec les gains.** Un bot qui a bien performé pendant 3 mois prend des positions 50% plus grosses qu'au démarrage. Si un flash crash arrive à ce moment, la perte est amplifiée par rapport au capital initial.

**Les pertes réduisent le stake.** Après des pertes, le bot prend des positions plus petites → moins de capacité de recovery. C'est un anti-martingale naturel (bon pour la gestion du risque, mais surprenant si on ne s'y attend pas).

### 🚫 Règles strictes

- 🚫 **`dry_run_wallet` DOIT correspondre à `available_capital`** pour que le dry-run simule correctement le live. Si `available_capital: 1000` et `dry_run_wallet: 5000`, le dry-run montrera des résultats 5x plus optimistes (stakes 5x plus gros). Toujours les garder synchronisés.

- 🚫 **Ne jamais mettre `available_capital` > le solde réel du wallet exchange.** La formule wallets.py utilise `available_capital` comme référence et ne vérifie pas le solde exchange. Si `available_capital: 5000` mais le wallet a 1000 USDC, les ordres seront rejetés par l'exchange en live.

- 🚫 **Après un reset de DB, `total_closed_profit` repart à 0.** Si le bot a accumulé 500 USDC de gains, un reset de DB fait passer `available_amount` de 1500 → 1000. Le sizing change brutalement. Documenter tout reset de DB.

### ✅ Bonnes pratiques

- ✅ **Utiliser `available_capital` plutôt que `dry_run_wallet` seul** pour le sizing. Le mode sans `available_capital` utilise le solde réel exchange, qui fluctue avec les positions ouvertes et peut causer des variations erratiques du stake.

- ✅ **Surveiller le ratio `proposed_stake / available_capital` au fil du temps.** Si ce ratio dépasse 1.5x le ratio initial, le compounding expose au risque de drawdown amplifié. Considérer un `capital_withdrawal` pour "prendre des profits" et stabiliser le sizing.

- ✅ **`capital_withdrawal` sert à simuler un retrait sans toucher à la DB.** Exemple : bot a gagné 500 USDC, on veut les "retirer" → mettre `capital_withdrawal: 500` ramène `available_amount` au niveau du capital initial. Le champ ne peut pas être négatif ; s'il dépasse `available_capital + total_closed_profit`, le capital disponible passe à 0.

- ✅ **MOT change radicalement le sizing DCA.** `proposed_stake = available / MOT`. Passer MOT de 5 → 3 augmente le stake de 67%. Passer de 3 → 2 l'augmente de 50%. Le sizing DCA (`custom_stake_amount`) dépend directement de `proposed_stake`. Toujours re-vérifier le sizing effectif après un changement de MOT.

### 💡 Vérification rapide de cohérence config

Pour une config avec `stake_amount: "unlimited"`, vérifier :

```
1. available_capital == dry_run_wallet (si dry_run: true)
2. available_capital <= solde réel du wallet exchange (si dry_run: false)
3. available_capital / max_open_trades = stake par trade attendu
4. stake_par_trade × leverage <= limite exchange pour les paires ciblées
5. Si capital_withdrawal > 0 : (available_capital - capital_withdrawal) / MOT = stake effectif
```

### 💡 Interaction avec le DCA

Le capital disponible pour les ordres DCA (safety orders) utilise la **même formule** que l'entrée initiale. Si le bot a 3 trades ouverts sur MOT=3, il n'y a plus de capital pour les DCA des trades existants. C'est pourquoi un MOT élevé avec DCA agressif peut bloquer les safety orders — le capital est déjà réparti sur les trades initiaux.

## Bonnes pratiques (toujours suivre sauf justification explicite)

- ✅ **Hyperliquid: préférer les ordres makers** (0.02% vs 0.05% taker). Rate limit = 1200 req/min par wallet. Solution si problème: Producer-Consumer mode, JAMAIS de sub-accounts (centraliser volume sur un seul wallet). Si rate-limit persiste: passer à VPN IP-level, jamais wallet-level. (tips.txt #27, CLAUDE.md)
- ✅ **La vraie complexité du trading systématique est dans l'opérationnel, pas dans les règles**. En production il faut redondance, fail-safes, gestion d'erreurs. La différence livre/prod n'est pas "5 jours au lieu de 7", c'est l'infrastructure. (tips.txt #103, Clenow)
- ✅ **Diagnostiquer une dégradation = comprendre le changement de structure du marché**. Exemple: explosion options 0DTE par retail. Lire Bloomberg/FT pour identifier les structural shifts qui expliquent un drawdown, pas pour trader. (tips.txt #159, Chan)
- ✅ **Monitor le VaR en live, pas seulement au BT**. Risque théorique BT ≠ risque live. Surveiller VaR quotidien et comparer à l'estimation BT. Si drift > X sigma, stopper et réinvestiguer. (tips.txt #190, Quant 1B)
