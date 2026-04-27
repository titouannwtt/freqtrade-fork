# Hyperopt — Tips et garde-fous

## Règles strictes (ne jamais enfreindre)

- 🚫 **Cap 200-300 epochs maximum**. Au-delà, sur-optimisation quasi garantie. Alternative robuste: 10-20 hyperopts de 200 epochs avec seeds différents et moyenner les JSON résultants. (tips.txt #14)
- 🚫 **Supprimer le `.json` co-localisé AVANT chaque hyperopt**. Il override silencieusement `buy_params` et `DecimalParameter` defaults. Si oublié, l'hyperopt peut varier des params qui n'ont aucun effet réel. (tips.txt #21, CLAUDE.md)
- 🚫 **Jamais `tee` pour piper un hyperopt**. Bufferise les retours chariot et cache la progress bar. Le `.fthypt` persiste déjà toutes les epochs. (tips.txt #25, CLAUDE.md)
- 🚫 **Toujours entraîner sur l'exchange cible**. Params Binance USDT ne transfèrent PAS à Hyperliquid USDC. Liquidité, spreads, funding, price action différents. Une stratégie profitable Binance peut produire -99% DD sur Hyperliquid. (tips.txt #26, CLAUDE.md)
- 🚫 **Hyperopt = piège d'overfitting**. La vraie edge vient de l'intuition et l'observation. 90% des stratégies rentables se construisent avec 2 indicateurs d'entrée + 1 indicateur de sortie. Si on doit hyperopter: utiliser CategoricalParameter larges/fixes plutôt que DecimalParameter, MOT 2-3 max, 200-300 epochs max. (tips.txt #38, communauté)
- 🚫 **"A very easy way to avoid over-fitting is to do no fitting at all."** Utiliser des valeurs par défaut raisonnables est plus fiable. (tips.txt #54, Carver)
- 🚫 **Zéro optimisation dans les backtests** (Clenow réplique des fonds trend-following avec règles non-optimisées). La volatilité (risk management) est la variable principale, pas les params d'indicateurs. (tips.txt #72, Clenow)
- 🚫 **Le nombre d'essais tentés est l'info la plus importante et la plus absente**. 1000 epochs = 1000 combinaisons → probabilité qu'au moins une soit "bonne" par hasard très élevée. (tips.txt #76, Lopez de Prado)
- 🚫 **Stabilité des params optimaux**. Si changer légèrement un param fait chuter la perf, c'est de l'overfitting. La recherche de params optimaux n'est pas une maximisation, c'est une preuve de robustesse. (tips.txt #81, Lopez de Prado)
- 🚫 **Meta-overfitting: holdout final jamais touché**. Même avec validation rigoureuse (CPCV), tester des dizaines d'idées sur le même dataset trouvera un faux positif. Défense: dataset holdout final intouché. (tips.txt #85, Lopez de Prado)
- 🚫 **Tenir le modèle LOIN des données le plus longtemps possible**. "Dès que tu regardes l'equity curve, tu fais de l'implicit fitting." Valider d'abord le comportement théorique AVANT de regarder la P&L. (tips.txt #113, Carver)
- 🚫 **"Best system in backtest = often the luckiest"**. Quand tu screens 1000 stratégies et tu gardes la meilleure, tu maximises le data snooping. Sélectionner sur ROBUSTESSE, pas sur PEAK performance. (tips.txt #161, Chan)
- 🚫 **Log systématique de TOUS les backtests avec pénalité**. Tenir un journal de tous tes hyperopts. Si tu cherches depuis 6 mois, ajuster le seuil de significance vers le haut. (tips.txt #180, Lopez de Prado)
- 🚫 **Aucun `logger.info` / `logger.debug` / `logger.warning` dans le code stratégie pendant l'hyperopt**. Chaque message × 28 workers × 40 paires × milliers de candles sature la log queue multiprocessing → main thread bloqué sur rich rendering → hyperopt **3× plus lent** ou stalls apparents (epoch counter figé, fthypt non mis à jour). Pour backtest et live : tous niveaux OK, garder les logs. Pour hyperopt : seul `logger.error` reste. Pattern quand un debug est utile : `if logger.isEnabledFor(logging.DEBUG): logger.debug(...)`. Hot paths à auditer SYSTÉMATIQUEMENT : `custom_stake_amount`, `confirm_trade_entry`, `adjust_trade_position`, `custom_exit`, `confirm_trade_exit`. (tips.txt #201, expérience HippoDCA short_reco r1 et short_casino r1)

## Bonnes pratiques (toujours suivre sauf justification explicite)

- ✅ **Feature importance > backtesting**. La méthode dominante (rechercher par BT) revient à du data mining brut. (tips.txt #79, Lopez de Prado)
- ✅ **Re-fit uniquement si HF**. Pour un système slow (DCA mean-rev sur 15m), réagir à 2 mois de données récentes sur 5 ans d'historique est une erreur. Carver n'a pas changé ses params en 8 ans. (tips.txt #108, Carver)

## Choix de la loss function (rappel CLAUDE.md)

| Comportement stratégie | Use | Do NOT use |
|---|---|---|
| Patient (attend jours/semaines) | `CalmarHyperOptLoss` | `SharpeHyperOptLossDaily` (pénalise inactivité) |
| Fréquente (trades chaque jour) | `SharpeHyperOptLossDaily` | `CalmarHyperOptLoss` (ignore consistance) |
| Safety-first (DD = mort) | `MaxDrawDownHyperOptLoss` | Raw profit losses |
| Diversifié multi-pair | `Mouton2HyperOptLoss` | Anything sans pair diversity penalty |

**Calmar = profit / max drawdown.** Best pour DCA qui doit sit out les bear markets.
