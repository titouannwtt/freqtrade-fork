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

## Bonnes pratiques (toujours suivre sauf justification explicite)

- ✅ **Hyperliquid: préférer les ordres makers** (0.02% vs 0.05% taker). Rate limit = 1200 req/min par wallet. Solution si problème: Producer-Consumer mode, JAMAIS de sub-accounts (centraliser volume sur un seul wallet). Si rate-limit persiste: passer à VPN IP-level, jamais wallet-level. (tips.txt #27, CLAUDE.md)
- ✅ **La vraie complexité du trading systématique est dans l'opérationnel, pas dans les règles**. En production il faut redondance, fail-safes, gestion d'erreurs. La différence livre/prod n'est pas "5 jours au lieu de 7", c'est l'infrastructure. (tips.txt #103, Clenow)
- ✅ **Diagnostiquer une dégradation = comprendre le changement de structure du marché**. Exemple: explosion options 0DTE par retail. Lire Bloomberg/FT pour identifier les structural shifts qui expliquent un drawdown, pas pour trader. (tips.txt #159, Chan)
- ✅ **Monitor le VaR en live, pas seulement au BT**. Risque théorique BT ≠ risque live. Surveiller VaR quotidien et comparer à l'estimation BT. Si drift > X sigma, stopper et réinvestiguer. (tips.txt #190, Quant 1B)
