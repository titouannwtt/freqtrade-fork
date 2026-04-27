# Strategy Evaluation — Tips et garde-fous

## Règles strictes (ne jamais enfreindre)

- 🚫 **Le winrate n'est PAS la métrique importante**. Stratégie à 97% winrate peut perdre -99% du capital. Privilégier: profit factor, Calmar ratio, max drawdown, SQN. Toujours vérifier profit total ET drawdown, jamais l'un sans l'autre. (tips.txt #4, communauté)
- 🚫 **Le SR Sharpe masque les blow-ups type LTCM**. LTCM avait SR > 3 avant l'explosion. Sharpe suppose distribution normale et traite downside/upside symétriquement. Pour stratégies "option-selling" (petits gains fréquents + rare désastre), préférer geometric return ou bootstrap distribution. DCA short sans cap du pire trade = option-selling classique. (tips.txt #117, Carver)
- 🚫 **Sharpe > 5 = fraud/bug/curve-fit**. "Si tu me montres un Sharpe double-digit, ça ne vaut pas la peine de continuer la conversation." Les BT à Sharpe extrême sont TOUJOURS red flag. (tips.txt #132, Clenow)
- 🚫 **Probabilités asymétriques > probabilités hautes (métrique d'évaluation)**. "Payé 10x quand raison 20% > 1.2x quand raison 80%." Vérifier systématiquement le profit moyen / perte moyenne (payoff ratio), pas juste le win rate. Un bot DCA haute fréquence (#6) reste valide SI son payoff ratio tient — danger = high-winrate avec payoff ratio catastrophique (cf. #4, #133). (tips.txt #188, Quant 1B)

## Bonnes pratiques (toujours suivre sauf justification explicite)

- ✅ **Comparer systématiquement la stratégie au TOTAL2 sur la même période**. Si sous-performe TOTAL2 en bull mais meilleur DD, c'est acceptable — les bots brillent dans la gestion du risque, pas dans la capture de rallyes. (tips.txt #32, Beetcoin)
- ✅ **Se méfier de la focalisation "downside only volatility" (Sortino)**. Clenow: "those guys usually blow up." Sortino masque le risque réel en ignorant la vol à la hausse. Préférer Sharpe ou Calmar qui prennent en compte la vol totale. (tips.txt #98, Clenow)
- ✅ **~15% annualisé, drawdown ~25%, Sharpe ~0.85 = réaliste voire très bon**. Calibrer les attentes sur ces ordres de grandeur, pas sur les promesses internet de 300% annualisés sans DD. (tips.txt #140, Clenow)
- ✅ **Benchmarker contre le bon comparable**. En crypto: buy-and-hold BTC INCLUANT funding payé/reçu sur Hyperliquid si applicable, pas BTC spot nu. Pour DCA short: benchmarker aussi contre short-and-hold BTC sur la même période. (tips.txt #142, Clenow)
