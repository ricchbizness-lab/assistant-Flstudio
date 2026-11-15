# assistant-Flstudio (notes pour Claude Code)

- Paquet Python `mixlab` (Python 3.11, NumPy/SciPy/soundfile). Conception : `docs/PHASE0.md`. Avancement : section « Avancement » de ce fichier.
- Moteur indépendant de toute GUI et de la couche IA : `features`, `measures`, `masking`, `gaps`, `rules` n'importent jamais `ai`, `report` ni une GUI.
- Jamais d'audio dans git : tout fichier audio va dans `data/` (ignoré). Les originaux ne sont jamais ouverts en écriture : passer par `mixlab.workcopy.make_working_copy`.
- Toute mesure est validée sur signaux synthétiques (`mixlab.testsignals`) avant d'être déclarée terminée. Convention : `dbfs` = crête d'un sinus ; bruit rose limité à 20 Hz-20 kHz.
- Mesures de loudness et true-peak : comparer à `ffmpeg -af ebur128=peak=true` et à pyloudnorm (oracles), pas seulement aux tests internes.
- Affirmations sur FL Studio : distinguer [V] vérifié (source), [S] supposé, [NT] non testé.
- Conditions de l'utilisateur : (a) les seuils numériques des tests de l'étape 3 sont figés dans `docs/STEP3_THRESHOLDS.md` et commités AVANT toute implémentation de l'étape 3, puis jamais modifiés pour faire passer un test ; (b) l'attribution de l'écrêtage du bus Master n'est développée qu'après le test d'écoute à l'aveugle de l'étape 3.
- Rôles des stems : préfixe dans le nom de piste (`KICK`, `808`, `SNARE`, `HAT`, `PERC`, `LEAD`, `KEYS`, `PAD`, `FX`, `VOX`, `BUS`, `SEND`), `roles.yaml` en secours.

## Avancement
- Phase 0 validée pour les étapes 0 à 3 uniquement.
- Étape 0 : validée par l'utilisateur.
- Étape 1 : faite, en attente de validation. Loudness (pas de 10 ms pour M/S, grille 100 ms pour I), true-peak x4, spectres tiers d'octave et Bark, cas EBU reconstruits, comparatif oracles (`tools/compare_oracles.py`, oracle Master = `tools/master_oracle.cpp`). Reste : comparatif sur un 3e morceau réel.
- Données audio : la release privée est abandonnée. L'utilisateur envoie un extrait de 20-30 s (stems + Master) dans le chat avant l'étape 3. Références dans `data/refs/` (16 bits / 48 kHz) ; exports à venir en 24 bits.
- Rapports : toujours afficher fréquence et profondeur de chaque fichier (`AudioInfo.label`).
