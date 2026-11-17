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
- Étape 1 : validée. Loudness (pas de 10 ms pour M/S, grille 100 ms pour I), true-peak x4, spectres tiers d'octave et Bark, cas EBU reconstruits, comparatif oracles (`tools/compare_oracles.py`, oracle Master = `tools/master_oracle.cpp`). Le 3e morceau réel n'est pas bloquant.
- Étape 2 : validée par l'utilisateur (« ça me paraît bien ») (`mixlab analyze`, `mixlab roles`). Bandes larges dans `mixlab/bands.py` ; mud et comparaison aux références dans `measures/balance.py` (normalisation du loudness obligatoire avant toute comparaison spectrale) ; sections par contraste spectral (`sections.py`, défaut 8 s minimum). Reste : avis de l'utilisateur sur un de ses mix.
- Étape 3 : seuils figés (commit da717e5) puis implémentation (`features.py`, `masking.py`, `stems.py`, commande `mixlab stems`), tests T1-T10 verts sans modification. Extrait réel : `data/test-1/stems/` (44,1 kHz / 32 bits flottant, 28,35 s, 14 stems + Master « …Beatz_2_Master »), `roles.yaml` dedans ; exclure `test-1_Master.wav` et `…Insert_1.wav` (demande de l'utilisateur). Test à l'aveugle : ÉCHEC (1 correspondance sur 2 notes, annexe A3). Condition (b) levée (le test d'écoute a eu lieu), mais toute suite au-delà de l'étape 3 attend la validation de l'utilisateur.
- Données audio : la release privée est abandonnée. L'utilisateur envoie un extrait de 20-30 s (stems + Master) dans le chat avant l'étape 3. Références dans `data/refs/` (16 bits / 48 kHz) ; exports réels en 32 bits flottant / 44,1 kHz.
- Rapports : toujours afficher fréquence et profondeur de chaque fichier (`AudioInfo.label`).
