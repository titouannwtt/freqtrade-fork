# Data Quality — Tips et garde-fous

## Règles strictes (ne jamais enfreindre)

- 🚫 **Causal denial > p-hacking**. Les modèles factoriels misspecifiés (confondent corrélation et causalité) sont PLUS dangereux que les modèles p-hackés, car seuls les premiers sont cause suffisante de pertes systématiques. Si un facteur n'a pas de justification causale, il ne devrait pas être dans ton modèle. (tips.txt #99, Lopez de Prado)
- 🚫 **More data = bien. More features = MAL**. "Feature-rich dataset is a curse in trading. The more features you have, the more likely you will find spurious correlations." Feature SELECTION est critique — ajouter 50 indicateurs au dataset est l'inverse de ce qu'il faut faire. (tips.txt #163, Chan)

## Conseils avancés (à appliquer selon le contexte)

- 💡 **L'orderbook comme source de données** — Applicable quand: tu veux un signal d'intention avant exécution. Les indicateurs arrivent "en retard", l'orderbook montre l'intention. Nécessite outils spécifiques (NautilusTrader), hors scope Freqtrade standard. (tips.txt #37, communauté)
- 💡 **Level 1 data suffit pour REJETER, pas pour valider** — Applicable quand: tu fais du HF et tu veux prouver qu'une stratégie MARCHE. Level 2 (depth of book) nécessaire car Level 1 quotes valables que pour 100 shares. (tips.txt #151, Chan)
