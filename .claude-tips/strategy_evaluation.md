# Strategy Evaluation — Tips et garde-fous

## Règles strictes (ne jamais enfreindre)

- 🚫 **Le winrate n'est PAS la métrique importante**. Stratégie à 97% winrate peut perdre -99% du capital. Privilégier: profit factor, Calmar ratio, max drawdown, SQN. Toujours vérifier profit total ET drawdown, jamais l'un sans l'autre. (tips.txt #4)
- 🚫 **Le SR Sharpe masque les blow-ups type LTCM**. LTCM avait SR > 3 avant l'explosion. Sharpe suppose distribution normale et traite downside/upside symétriquement. Pour stratégies "option-selling" (petits gains fréquents + rare désastre), préférer geometric return ou bootstrap distribution. DCA short sans cap du pire trade = option-selling classique. (tips.txt #117, Carver)
- 🚫 **Sharpe > 5 = fraud/bug/curve-fit**. Les BT à Sharpe extrême sont TOUJOURS red flag. (tips.txt #132, Clenow)
- 🚫 **Probabilités asymétriques > probabilités hautes**. "Payé 10x quand raison 20% > 1.2x quand raison 80%." Vérifier le payoff ratio (profit moyen / perte moyenne), pas juste le win rate. (tips.txt #188)

## Checklist d'analyse de stratégie

Lors du review d'une stratégie, vérifier l'utilisation de ces fonctions freqtrade. Signaler si une fonction pertinente n'est pas implémentée :

| Fonction | Quand elle devrait être présente |
|---|---|
| `custom_stake_amount` | Toute stratégie DCA ou avec sizing dynamique |
| `custom_stoploss` | SL adaptatif (trailing custom, SL par DCA level) |
| `custom_exit` | Sortie complexe (conditions multiples, temporelle, indicateurs) |
| `adjust_trade_position` | DCA / safety orders / pyramidage |
| `confirm_trade_entry` | Garde-fou pré-entrée (conditions supplémentaires, position guard) |
| `confirm_trade_exit` | Garde-fou pré-sortie (empêcher sorties prématurées) |
| `custom_entry_price` / `custom_exit_price` | Pricing spécifique (mid-spread, offset) |
| `leverage` | Levier dynamique par paire ou condition de marché |
| `informative_pairs` | Multi-timeframe, cross-pair (BTC comme filtre macro) |
| `bot_loop_start` | Logique exécutée à chaque cycle (état global) |

Ne pas ajouter ces fonctions par défaut — signaler uniquement quand leur absence est un manque.

## Bonnes pratiques (toujours suivre sauf justification explicite)

- ✅ **Comparer la stratégie au TOTAL2 sur la même période**. Si sous-performe en bull mais meilleur DD, c'est acceptable — les bots brillent dans la gestion du risque. (tips.txt #32)
- ✅ **Se méfier du Sortino**. Clenow: "those guys usually blow up." Sortino masque le risque réel en ignorant la vol à la hausse. Préférer Sharpe ou Calmar. (tips.txt #98, Clenow)
- ✅ **~15% annualisé, drawdown ~25%, Sharpe ~0.85 = réaliste voire très bon**. (tips.txt #140, Clenow)
- ✅ **Benchmarker contre le bon comparable**. En crypto: buy-and-hold BTC INCLUANT funding. Pour DCA short: benchmarker aussi contre short-and-hold BTC. (tips.txt #142, Clenow)
