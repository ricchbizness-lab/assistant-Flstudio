# Étape 3B : équilibre des niveaux, gain staging, chaîne Master (FIGÉ avant implémentation)

Validée par l'utilisateur le 17/11/2026 (option B, après l'échec du test d'écoute, annexe A3
de STEP3_THRESHOLDS.md). Condition (b) levée : le test d'écoute a eu lieu.
Même règle qu'à l'étape 3 : les seuils ci-dessous ne sont jamais modifiés pour faire passer
un test ; toute correction est proposée à l'utilisateur et ajoutée en annexe datée.

## 1. Mesures (définitions figées)

| Mesure | Définition |
|---|---|
| Niveau d'un stem | LUFS intégré et momentané max (fenêtre 400 ms : juste pour les sons brefs, snare, hats) |
| Contribution par bande | énergie du stem dans une bande / somme des énergies des stems dans cette bande (6 bandes larges et tiers d'octave) |
| Bandes à corriger | tiers d'octave où le Master s'écarte d'au moins 3 dB de la moyenne des références (spectres normalisés en loudness) ; pour chacune, les stems qui y contribuent le plus |
| Gain staging | crête de chaque stem et de la somme (flottant, peut dépasser 0 dBFS) ; correction globale = -6 dBFS - crête de la somme |
| Effet de la chaîne Master | facteur de crête perdu (somme -> Master) et loudness gagné (LU) |
| Gain de rattrapage G | médiane de crête(Master)/crête(somme) sur les trames de 5 ms dont la crête de la somme est entre ses percentiles 10 et 50 (zones où rien ne limite) |
| Réduction par trame | 20·log10(G·crête(somme)/crête(Master)), trames de 5 ms, Master aligné |
| Attribution | trames où la réduction dépasse 1 dB : à l'échantillon de crête de la somme, part positive de chaque stem (valeur signée dans le sens de la crête) ; cumul pondéré par la réduction, en % |

## 2. Recalibration du masquage (annexe A4 de STEP3_THRESHOLDS.md)

- Poids d'importance de la cible : w = 10^((M_max(cible) - M_max(stem le plus fort)) / 20), borné à [0, 1],
  M_max = loudness momentané max. Une couche à 35 dB sous l'élément le plus fort pèse 0,018.
- Score de classement = % d'énergie utile masquée × w. L'ancien score reste affiché.
- Les paramètres et seuils du §1-§2 de STEP3_THRESHOLDS.md sont inchangés.
- Validation : nouveau test d'écoute à l'aveugle sur un **autre extrait** (critère §3 inchangé).

## 3. Tests synthétiques et seuils (figés)

| # | Signal | Seuil |
|---|---|---|
| L1 | Somme de stems de crête +6,0 dBFS | correction globale = -12,0 dB ± 0,01 |
| L2 | Master = 0,5 × somme (gain seul) | facteur de crête perdu ≤ 0,1 dB ; loudness gagné = -6,02 ± 0,05 LU |
| L3 | Master = écrêtage dur à -1 dBFS de 1,5 × somme (kick, pad, basse) | G estimé = +3,52 dB ± 0,5 |
| L4 | Même signal que L3, seul le kick dépasse | part du kick dans la réduction ≥ 80 % |
| L5 | Master = gain seul (0,8 × somme) | trames avec réduction > 1 dB ≤ 1 % |
| L6 | Limiteur simulé (attaque instantanée, relâchement 50 ms, seuil 0,5), 10 s | erreur absolue médiane de la réduction estimée ≤ 1 dB sur les trames où la vraie réduction ≥ 2 dB |
| L7 | Stem A = bruit rose < 300 Hz, stem B = bruit rose > 1 kHz, même niveau | contribution de A dans le tiers d'octave 250 Hz ≥ 95 % ; de B à 2 kHz ≥ 95 % |
| L8 | Poids | w(-40 ; -5) = 0,0178 ± 0,0005 ; w(-5 ; -5) = 1 |
| L9 | Masqueur 1 kHz -20 et cible 1,1 kHz -50 ; masqueur 3 kHz -20 et cible 3,3 kHz -30 | classement pondéré : la cible 3,3 kHz passe devant la cible 1,1 kHz |
| L10 | 16 stems de 30 s, analyse complète (niveaux + masquage) | ≤ 60 s |

## Annexes

### B1 (17/11/2026) : L4 ÉCHOUE (78,6 % pour un seuil de 80 %) — correction PROPOSÉE, non appliquée

Résultats : L1, L2, L3, L5 à L10 passent. L4 donne 78,6 % (kick), 14,1 % (basse), 7,3 % (pad).

Cause : la définition figée (§1) attribue la crête à chaque piste qui sonne au même instant,
au prorata de son amplitude. Dans le signal de L4, la basse (crête 0,126) s'ajoute au kick
(0,708) : même en phase parfaite, la part du kick plafonne à 85 % ; en moyenne 78,6 %. Le
seuil de 80 % était une estimation trop serrée, faite sans ce calcul. Ce n'est pas un défaut
d'implémentation : la basse contribue réellement à la crête écrêtée.

Méthode alternative testée (contribution marginale : la réduction disparaît-elle si l'on
retire la piste ?) : 57,7 % pour le kick, moins bonne. Écartée.

Correction proposée à l'utilisateur : seuil L4 abaissé à 75 %, avec la justification
ci-dessus. **En attente de sa décision** ; d'ici là, le test reste en échec.
