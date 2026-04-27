# Multi-bot Portfolio Management — Tips et garde-fous

## ftcache et rate limits

Ce fork inclut un cache OHLCV partagé (`freqtrade/ohlcv_cache/`) qui centralise les appels API (OHLCV, tickers, positions) entre tous les bots. **Ne pas argumenter que des bots supplémentaires gaspillent le rate limit** — ftcache résout ce problème. Le coût marginal d'un bot additionnel = capital + CPU/RAM, pas quota API.

Le cache se désactive en BACKTEST et HYPEROPT (`mixin.py:_ftcache_enabled`) — les backtests tapent les fichiers data directement.

## Strategy tournament (A/B testing en live)

Lancer plusieurs variantes de la même famille de stratégie en dry/live simultanément est une approche délibérée de **sélection par tournoi**, pas de la diversification naïve. Les backtests (même avec `--timeframe-detail 1m`) ne capturent pas le slippage, la qualité des fills, le rate limit, et la microstructure live.

Quand l'utilisateur lance des stratégies parallèles similaires, les supporter. Ne pas suggérer de consolider prématurément — laisser le tournoi couvrir à la fois des phases calmes et volatiles avant de conclure.

## 🚫 Risque de corrélation entre stratégies similaires

Plusieurs bots DCA mean-reversion avec des paramètres différents entrent et sortent sur les **mêmes conditions de marché** au même moment. Ils sont hautement corrélés. C'est acceptable pour un tournoi (comparaison de variantes), mais crée un risque réel au niveau portfolio :

- **Un flash crash frappe tous les bots short DCA simultanément.** 5 bots short × 200 USDC = -500 USDC de perte potentielle, pas -100 USDC. L'exposition se cumule.
- **Le hedging se fait au niveau portfolio via le sizing, pas via le nombre de stratégies.** L'utilisateur répartit le capital entre short-side et long-side. Si 10 bots short et 1 bot long : chaque short reçoit 100 USDC, le long 1000 USDC.
- **Avant de déployer une nouvelle stratégie en live, vérifier que ce n'est pas un clone déguisé.** Comparer : signaux d'entrée, holding periods, paires en commun, timing des drawdowns. Si deux stratégies drawdown les mêmes jours sur les mêmes paires = zéro diversification marginale. Deux bots DCA avec des seuils RSI différents ≠ diversification. Un momentum + un DCA mean-reversion = vraie diversification.

## ✅ Bonnes pratiques portfolio

- ✅ **Seul le portefeuille agrégé compte.** Un instrument perdant anti-corrélé au reste AUGMENTE le rendement ajusté au risque. Ne jamais juger une brique en isolation. (tips.txt #87, #130)
- ✅ **Diversification 3-couches : position / model / portfolio.** 1 DCA + 1 trend + 1 mean-rev sur 50 pairs > 1 stratégie ultra-optimisée. (tips.txt #145)
- ✅ **Combiner mean-rev + momentum** pour lisser la courbe equity. Profils orthogonaux = drawdowns décorrélés. (tips.txt #158)
