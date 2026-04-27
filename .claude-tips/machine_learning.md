# Machine Learning — Tips et garde-fous

> **Décision actuelle de l'utilisateur** : PAS de ML sur 15m candles avec Freqtrade (cf. tips.txt #36 et #162). Ce fichier sert de référence si la décision change ou pour la veille théorique.

## Règles strictes (ne jamais enfreindre)

- 🚫 **ML marche sur tick data + order book + stocks individuels en cross-section. PAS sur daily/15m bars, futures ou indices**. "Applying to futures and indices — the data are simply insufficient and machine learning will suffer severe data snooping bias." Confirme: ne PAS utiliser FreqAI ou tout ML sur signaux d'entrée avec candles 15m. ML sérieux nécessiterait tick data sur 100+ pairs et infrastructure dédiée — hors scope Freqtrade. (tips.txt #162, Chan)

## Bonnes pratiques (toujours suivre sauf justification explicite)

- ✅ **ML pour les signaux d'entrée/sortie n'a pas produit de résultats convaincants** (FreqAI, QuickAdapter, copy trading). En revanche, ML pour l'allocation de capital et le risk management (orchestrateur de bots, sizing dynamique) est une piste prometteuse. (tips.txt #36, communauté)
- ✅ **Prédire le RISQUE est plus facile que prédire la DIRECTION**. ML peut bien filtrer les trades du bot (couche risk management) mais pas générer d'alpha. Faux positifs = no profit (pas de perte), alors que mauvaise direction = perte sèche. (tips.txt #148, Chan)
- ✅ **Retraining ML: une fois par trimestre suffit**. "Adding a few months of data is not going to make a big difference. If it does, something's wrong with the model." Retrainer trop souvent = red flag d'instabilité. (tips.txt #153, Chan)
- ✅ **Neural networks ne font PAS de feature selection**. "NN basically takes everything you got and squeezes them into a sausage." C'est pourquoi NN marche en computer vision (stationnaire) mais échoue en finance (non-stationnaire). Préférer stepwise regression, CART, random forest qui sélectionnent explicitement. (tips.txt #164, Chan)
- ✅ **Ensemble methods > algorithme unique**. "One of the few free lunches in ML." Combiner plusieurs modèles diversifiés réduit la variance et contre le test-set overfitting. (tips.txt #171, Lopez de Prado)
- ✅ **Le modèle le plus EXPLICATIF n'est PAS forcément le meilleur PRÉDICTEUR**. Tension entre econometrics et ML. Bias-variance tradeoff: ML accepte un biais dans le prédicteur pour améliorer la prédiction. Ne pas choisir un modèle parce qu'il "explique bien" ce qui s'est passé. (tips.txt #176, Lopez de Prado)
- ✅ **Finance = problème BEAUCOUP plus dur que face recognition**. Télécharger une lib Silicon Valley (PyTorch, sklearn defaults) et l'appliquer aux prix = erreur garantie. Datasets finance: non-stationnaires, multi-colinéaires, non-IID, avec regime switches. (tips.txt #177, Lopez de Prado)

## Conseils avancés (à appliquer selon le contexte)

- 💡 **Triple Barrier Method: labeler les trades par {profit-taking, stop-loss, time-out}** — Applicable quand: tu entraînes un modèle ML. Au lieu de prédire "le prix monte", prédire "ce trade va toucher TP avant SL avant timeout". Méthode de LABELING uniquement, pas règle d'exit live (compatible avec exits dynamiques mean-rev). (tips.txt #77, Lopez de Prado)
- 💡 **Meta-labeling: un second modèle décide s'il faut agir sur le signal du premier** — Applicable quand: tu veux séparer direction (modèle 1, peut être un indicateur classique) et timing (modèle 2 filtre les faux signaux). Extension #78 → #168. (tips.txt #78, Lopez de Prado)
- 💡 **Différentiation fractionnaire** — Applicable quand: tu construis des features ML sur des prix. Différentiation entière (returns) supprime toute la mémoire. Fractionnaire trouve le minimum nécessaire pour stationnarité, préservant le pouvoir prédictif. (tips.txt #82, Lopez de Prado)
- 💡 **Random Forest = oversample rows + UNDERsample features** — Applicable quand: tu veux le combo anti-overfit. "You want a lot of data but very few predictors. Random Forest achieves that." (tips.txt #165, Chan)
- 💡 **ML comme couche probabiliste au-dessus de règles simples** — Applicable quand: tu veux prolonger la durée de vie d'une stratégie simple. "Simple models have a quick half-life. ML applies a filter to the trades that the simple model suggests — it assigns a probability to the success of the trade." Extension de #78. (tips.txt #168, Chan)
- 💡 **Sampling basé sur l'arrivée d'INFORMATION, pas sur le temps** — Applicable quand: tu construis une infra ML custom (hors Freqtrade standard). Time bars échantillonnent quand il n'y a rien à apprendre. Préférer dollar bars, volume bars, dollar imbalance bars. Adaptation Freqtrade: pondérer indicateurs 15m par volume relatif (signal RSI ignoré si volume < 30% de la moyenne). (tips.txt #170, Lopez de Prado)
- 💡 **Denoising via Marchenko-Pastur** — Applicable quand: tu estimes une matrice de covariance pour optimisation portfolio. Eigenvalues sous distribution MP = bruit pur, remplacer par leur moyenne améliore massivement (-60% MSE min-variance, -94% MSE max-Sharpe). Supérieur à Ledoit-Wolf. (tips.txt #173, Lopez de Prado)
- 💡 **Nested Clustered Optimization (NCO)** — Applicable quand: instabilité Markowitz frappe. Cluster les assets, optimiser indépendamment dans chaque cluster, puis entre clusters. -47% MSE vs Markowitz direct. Crypto: cluster les pairs par similarité de comportement. (tips.txt #174, Lopez de Prado)
- 💡 **ML +31% vs Markowitz en moyenne, avant transaction costs** — Applicable quand: tu choisis un allocateur de portefeuille. Tree-based (HRP, etc.) > Markowitz out-of-sample. Après coûts Markowitz devient prohibitif (turnover extrême). HRP/NCO pour allouer entre stratégies/pairs. (tips.txt #178, Lopez de Prado)
- 💡 **Weighting observations par UNIQUENESS** — Applicable quand: tu entraînes sur des labels qui se chevauchent dans le temps. Sans pondération, l'algo sur-apprend les exemples redondants. Donner moins de poids aux observations moins uniques augmente l'accuracy out-of-sample. (tips.txt #179, Lopez de Prado)
