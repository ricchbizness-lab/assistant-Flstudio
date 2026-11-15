# Étape 1 : comparaison avec les oracles

Généré par `tools/compare_oracles.py`. Oracles : ffmpeg `ebur128=peak=true` (une décimale), pyloudnorm 0.2.0 (pas de true-peak), RicchBeatz Master (`Source/Dsp.h` compilé sans JUCE).

Tolérances : intégré ±0.1 LU, LRA ±0.2 LU, true-peak ±0.1 dB (+0.05 pour l'arrondi d'affichage de ffmpeg). Comparaisons avec Master : informatives seulement (voir notes).

| Fichier | Format | I mixlab | I ffmpeg | I pyloudnorm | I Master | LRA mixlab | LRA ffmpeg | LRA pyloudnorm | LRA Master | TP mixlab | TP ffmpeg | TP Master |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EBU 3341-1-integrated | 48 kHz / 32 bits flottant | -22.99 | -23.0 | -23.03 | -22.99 | 0.00 | 0.0 | 0.00 | 0.00 | -23.00 | -23.0 | -23.00 |
| EBU 3341-2-integrated | 48 kHz / 32 bits flottant | -32.99 | -33.0 | -33.03 | -32.99 | 0.00 | 0.0 | 0.00 | 0.00 | -33.00 | -33.0 | -33.00 |
| EBU 3341-3 | 48 kHz / 32 bits flottant | -23.01 | -23.0 | -23.06 | -23.01 | 13.00 | 13.0 | 13.00 | 13.00 | -23.00 | -23.0 | -23.00 |
| EBU 3341-4 | 48 kHz / 32 bits flottant | -23.01 | -23.0 | -23.06 | -23.01 | 13.00 | 13.0 | 13.00 | 13.00 | -23.00 | -23.0 | -23.00 |
| EBU 3341-5 | 48 kHz / 32 bits flottant | -22.98 | -23.0 | -23.02 | -22.98 | 6.00 | 6.0 | 6.00 | 6.00 | -20.00 | -20.0 | -20.00 |
| EBU 3341-9 | 48 kHz / 32 bits flottant | -22.99 | -23.0 | -23.04 | -22.99 | 0.00 | 0.0 | 0.46 | 0.00 | -20.00 | -20.0 | -20.00 |
| EBU 3341-12 | 48 kHz / 32 bits flottant | -22.96 | -23.0 | -23.00 | -22.96 | 0.46 | 0.5 | 1.30 | 0.46 | -20.00 | -20.0 | -20.00 |
| EBU 3341-15 | 48 kHz / 32 bits flottant | -2.69 | -2.7 | -2.73 | -2.69 | 0.00 | 0.0 | – | 0.00 | -6.02 | -6.0 | -6.02 |
| EBU 3341-16 | 48 kHz / 32 bits flottant | -2.69 | -2.7 | -2.73 | -2.69 | 0.00 | 0.0 | – | 0.00 | -6.02 | -6.0 | -6.02 |
| EBU 3341-17 | 48 kHz / 32 bits flottant | -2.69 | -2.7 | -2.73 | -2.69 | 0.00 | 0.0 | – | 0.00 | -6.02 | -6.0 | -6.02 |
| EBU 3341-18 | 48 kHz / 32 bits flottant | -2.70 | -2.7 | -2.74 | -2.70 | 0.00 | 0.0 | – | 0.00 | -6.02 | -6.0 | -6.02 |
| EBU 3341-19 | 48 kHz / 32 bits flottant | 6.32 | 6.3 | 6.27 | 6.32 | 0.00 | 0.0 | – | 0.00 | 2.98 | 3.0 | 2.98 |
| EBU 3341-20 | 48 kHz / 32 bits flottant | -2.68 | -2.7 | -2.73 | -2.68 | 0.00 | 0.0 | – | 0.00 | -0.13 | -0.1 | -0.13 |
| EBU 3341-21 | 48 kHz / 32 bits flottant | -2.68 | -2.7 | -2.73 | -2.68 | 0.00 | 0.0 | – | 0.00 | -0.13 | -0.1 | -0.13 |
| EBU 3341-22 | 48 kHz / 32 bits flottant | -2.68 | -2.7 | -2.73 | -2.68 | 0.00 | 0.0 | – | 0.00 | -0.14 | -0.1 | -0.14 |
| EBU 3341-23 | 48 kHz / 32 bits flottant | -2.68 | -2.7 | -2.73 | -2.68 | 0.00 | 0.0 | – | 0.00 | -0.13 | -0.1 | -0.13 |
| EBU 3342-1 | 48 kHz / 32 bits flottant | -22.59 | -22.6 | -22.63 | -22.59 | 10.00 | 10.0 | 10.00 | 10.00 | -20.00 | -20.0 | -20.00 |
| EBU 3342-2 | 48 kHz / 32 bits flottant | -16.81 | -16.8 | -16.85 | -16.81 | 5.00 | 5.0 | 5.00 | 5.00 | -15.00 | -15.0 | -15.00 |
| EBU 3342-3 | 48 kHz / 32 bits flottant | -20.03 | -20.0 | -20.07 | -20.03 | 20.00 | 20.0 | 20.00 | 20.00 | -20.00 | -20.0 | -20.00 |
| EBU 3342-4 | 48 kHz / 32 bits flottant | -24.49 | -24.5 | -24.53 | -24.49 | 15.00 | 15.0 | 15.00 | 15.00 | -20.00 | -20.0 | -20.00 |
| Nayfun - MARACANA (Baile Funk) | 48 kHz / 16 bits | -10.37 | -10.4 | -10.41 | -10.37 | 7.56 | 7.6 | 7.55 | 7.42 | 0.58 | 0.6 | 0.58 |
| Nayfun - MONEY (Jerk Drill) | 48 kHz / 16 bits | -9.45 | -9.5 | -9.48 | -9.45 | 8.77 | 8.9 | 9.53 | 9.28 | 0.79 | 0.8 | 0.79 |

**Résultat : aucun écart hors tolérance**

## Notes de lecture

- **pyloudnorm** lit l'intégré environ 0,04 LU plus bas que les trois autres sur tous les signaux : écart systématique de sa pondération K, sans conséquence (tolérance 0,1).
- **LRA sur musique réelle** : les implémentations divergent davantage que sur les signaux d'essai, car Tech 3342 laisse libres le pas du court terme (≥ 10 Hz) et l'estimateur de percentile. mixlab suit le pseudo-code de la norme (pas de 100 ms, percentiles par rang) et reste à ±0,15 LU de ffmpeg. Master utilise un pas de 1 s, pyloudnorm un autre estimateur : ils sont listés à titre indicatif et ne servent pas de critère.
- **True-peak, cas EBU 20 à 23** : la crête réelle du signal filtré est de -0,07 à -0,13 dBTP (référence : suréchantillonnage x32). Le x4 de mixlab et de Master sous-lit au plus 0,06 dB, ce que la tolérance de la norme (+0,2/-0,4 dB) prévoit.
- **ffmpeg** n'affiche qu'une décimale : ses valeurs sont arrondies à ±0,05.
