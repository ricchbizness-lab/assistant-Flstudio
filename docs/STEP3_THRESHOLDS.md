# Étape 3 : paramètres du modèle et seuils des tests (FIGÉS)

Condition (a) de l'utilisateur : ce document est commité **avant toute implémentation
de l'étape 3**. Les seuils des tests ne seront jamais modifiés pour faire passer un test.
Si un seuil s'avère faux (erreur de raisonnement, comme le mud de l'étape 2), la
correction est proposée à l'utilisateur, justifiée, et consignée en annexe datée,
sans effacer la valeur d'origine.

Condition (b) : l'attribution de l'écrêtage du bus Master n'est **pas** dans ce
périmètre. Seuls l'alignement stems/Master et la mesure de l'écart global sont faits.

## 1. Modèle de masquage (paramètres figés)

| Paramètre | Valeur |
|---|---|
| Bandes | 24 bandes critiques de Zwicker (`BARK_EDGES`, 20 Hz - 15,5 kHz) |
| Position d'une bande | Bark de son centre géométrique (formule de Zwicker et Terhardt) |
| Trames | pas = puissance de 2 la plus proche de 23,2 ms (1024 à 44,1 et 48 kHz) |
| Fenêtres | Hann ; 4 x le pas (≈ 93 ms) pour les bandes dont la borne haute ≤ 510 Hz, 1 x le pas (≈ 23 ms) au-dessus |
| Énergie | par stem, par canal (L, R), par trame, par bande |
| Masqueur | somme des énergies des autres stems (addition de puissances) ; pour une paire : un seul stem |
| Étalement | fonction de Schroeder : SF(dz) = 15,81 + 7,5(dz + 0,474) - 17,5·sqrt(1 + (dz + 0,474)²) dB, dz = z(cible) - z(masqueur) |
| Décalage du seuil | 6 dB sous l'excitation étalée |
| SMR | énergie de la cible - seuil (dB), par canal |
| Bande pertinente | énergie de la cible dans la bande ≥ (bande la plus forte de la cible dans la trame) - 30 dB |
| Trame active | énergie totale de la cible ≥ (95e percentile de ses trames) - 30 dB |
| Masqué | dans tous les canaux où la bande est pertinente, SMR < 0 |
| masked_ratio (bande) | part des trames actives, où la bande est pertinente, qui sont masquées |
| energy_masked_pct (stem) | part de l'énergie pertinente de la cible située dans des cases (trame, bande, canal) masquées |
| Score d'un conflit (paire i, j) | max(energy_masked_pct de i par j seul, de j par i seul) |
| Kick / 808 | enveloppes RMS sur 10 ms dans 30-120 Hz : corrélation des enveloppes |
| Bus | stem dont le résidu après soustraction des stems corrélés (r > 0,2) est ≤ -30 dB : exclu de la somme |
| Alignement stems / Master | décalage par intercorrélation (mono, 10 premières secondes), recherche ±50 ms |

## 2. Tests synthétiques et seuils

Tous les sinus sont en stéréo (L = R), avec fondus de 10 ms, sauf mention contraire.
Niveaux en crête (dBFS). Les SMR prévus sont calculés avec les paramètres du §1
(énergie d'un sinus = crête - 3,01 dB), avant toute implémentation.

| # | Signal | Seuil figé | Prévu |
|---|---|---|---|
| T1 | Masqueur 1 kHz -20 ; cible 1,1 kHz -40 ; 2 s | cible : masked_ratio ≥ 0,9 et SMR médian ≤ -6 dB | -9,3 dB |
| T2 | Masqueur 1 kHz -20 ; cible 4 kHz -40 | cible : masked_ratio ≤ 0,05 | +64 dB |
| T3a | Masqueur 500 Hz -20 ; cible 700 Hz -45 | cible masquée : masked_ratio ≥ 0,9 | -6,2 dB |
| T3b | Masqueur 700 Hz -20 ; cible 500 Hz -45 | cible non masquée : masked_ratio ≤ 0,1 | +9,6 dB |
| T3c | Asymétrie | SMR médian (T3b) - SMR médian (T3a) ≥ 8 dB | 15,8 dB |
| T4a | Kick (balayage 120 → 50 Hz, décroissance 30 ms, coupé à 0,18 s, crête -14) toutes les 0,5 s ; 808 (45 Hz, décroissance 60 ms, coupée à 0,22 s, crête -2) décalée de 0,25 s, 8 s | kick masqué par la 808 : masked_ratio bande 0 ≤ 0,1 ; corrélation des enveloppes ≤ 0,2 | sans recouvrement |
| T4b | Même kick et même 808, frappés ensemble | kick : masked_ratio bande 0 ≥ 0,6 ; corrélation des enveloppes ≥ 0,7 | 808 12 dB au-dessus |
| T5a | T1 avec masqueur 100 % à gauche, cible 100 % à droite | cible : masked_ratio ≤ 0,1 | pas de masqueur dans R |
| T5b | T1 centré (contrôle) | identique à T1 | |
| T6 | Bruit rose -20 RMS ; cible sinus 1 kHz -20 | cible : masked_ratio ≤ 0,1 | tonalité au-dessus du bruit de bande |
| T7 | Stem « bus » = somme exacte de deux stems de bruit indépendants | bus détecté et exclu ; aucun des deux stems sources n'est détecté comme bus | résidu -inf |
| T8 | Somme de stems retardée de 86 échantillons, sans autre traitement | décalage estimé = 86 ± 1 ; écart après alignement ≤ -60 dB | |
| T9 | 16 stems de 30 s à 44,1 kHz | analyse complète ≤ 60 s sur la machine de développement | |
| T10 | Paire (i, j) symétrique : score identique quel que soit l'ordre des fichiers | écart = 0 | |

## 3. Test d'écoute à l'aveugle (critère d'acceptation)

- L'utilisateur a noté 3 conflits perçus avant de voir les résultats.
- L'outil donne ses 3 premiers conflits : paires non ordonnées, classées par score (§1).
- Correspondance : même paire d'éléments, ou même rôle si l'utilisateur désigne un
  groupe (« les basses ») et que la paire de l'outil en contient un.
- **Réussi si au moins 2 conflits sur 3 correspondent.** Sinon : recalibrage des
  paramètres du §1 (consigné en annexe datée), les seuils du §2 restant inchangés et
  devant toujours passer, puis nouveau test sur un autre extrait.

## Annexes (corrections ultérieures)

### A1 (17/11/2026) : prédictions de la colonne « Prévu » vs mesures — aucun seuil modifié

Les 10 tests passent avec les seuils et paramètres d'origine. Valeurs mesurées :

| # | Prévu (papier) | Mesuré |
|---|---|---|
| T1 | SMR -9,3 dB | ratio 1,00, SMR médian -14,5 dB |
| T2 | +64 dB | ratio 0,00, +64,0 dB |
| T3a | -6,2 dB | ratio 1,00, -15,8 dB |
| T3b | +9,6 dB | ratio 0,00 dans la bande du sinus |
| T3c | 15,8 dB | 12,4 dB (seuil 8) |
| T4a / T4b | | ratio bande 0 : 0,04 / 1,00 ; corrélation des enveloppes : -0,24 / +0,93 |
| T5a | | ratio 0,00 |
| T6 | | ratio 0,00, SMR +17,6 dB |

Écart T1/T3a : les prédictions supposaient des bandes étanches. Avec la fenêtre courte
(23 ms) au-dessus de 510 Hz, le lobe principal de Hann couvre environ ±86 Hz : un sinus
à 1100 Hz, à 20 Hz de la frontière 1080 Hz, dépose 47 % de son énergie dans la bande du
masqueur. **Limite du modèle** : près des frontières de bande, le masquage entre éléments
voisins est surestimé. Le SMR médian de T3b (-3,4 dB) inclut ces cases de débordement
(hors de la bande du sinus) ; le ratio dans la bande du sinus reste 0,00.

### A2 (17/11/2026) : indicateurs d'affichage ajoutés (le score figé n'est pas modifié)

Avec un masqueur intermittent (snare, snap), le SMR médian sur toutes les trames de la
cible devient très grand (+125 dB et plus) car le masqueur est absent la plupart du
temps. Ajout de deux indicateurs d'affichage : part du temps de la cible où le masqueur
joue, et SMR médian sur ces trames seulement. Le score de classement reste celui du §1.
