# Music Engineering Lab : Phase 0 (audit et conception)

Statut : **validée le 14/11/2026 pour les étapes 0 à 3 uniquement**, sous deux conditions : (a) seuils numériques des tests de l’étape 3 figés avant implémentation ; (b) attribution de l’écrêtage du bus reportée après le test d’écoute à l’aveugle de l’étape 3. Les étapes 4 à 6 restent à valider.
Légende des affirmations : **[V]** vérifié dans une doc (source citée) · **[S]** supposé · **[NT]** non testé, à tester sur ta machine.

---

## 1. Étude de faisabilité : le masquage

### Le problème de fond
Deux stems qui ont de l'énergie dans la même bande ne se masquent pas forcément. Ce qui compte :
- **l'écart de niveau** dans la bande (le plus fort masque le plus faible, pas l'inverse) ;
- **l'étalement fréquentiel asymétrique** : un son grave masque plus facilement un son plus aigu que l'inverse (*upward spread of masking*) ;
- **le temps** : un kick et une 808 dans la même bande ne se gênent pas s'ils ne jouent pas en même temps (sidechain, programmation) ;
- **l'espace stéréo** : deux sources panoramiquées à l'opposé se masquent moins (démasquage binaural, plusieurs dB) ;
- **le niveau d'écoute absolu** : inconnu pour un fichier, ce qui interdit un seuil absolu exact.

Conclusion : un simple « chevauchement spectral » sur-déclare le masquage. Il faut au minimum le niveau relatif, l'étalement et la dimension temporelle.

### Options comparées

| | A. Chevauchement d'énergie par bande | B. Seuil de masquage simplifié (recommandé) | C. Sonie partielle (Moore-Glasberg / Zwicker) |
|---|---|---|---|
| Principe | Énergie de A et de B par bande Bark et par trame ; on signale quand les deux dépassent un seuil relatif | Pour la cible A, on calcule le seuil de masquage produit par le masqueur M (étalement Bark asymétrique type Schroeder), puis le rapport signal/masque (SMR) de A par bande et par trame. A est masqué là où SMR < 0 | Sonie de A seul vs sonie de A en présence de M ; la perte de sonie quantifie directement « A s'entend moins » |
| Avantage | Trivial, rapide, très lisible | Capture l'asymétrie niveau/fréquence, reste explicable (« la 808 couvre le kick de 6 dB à 60-80 Hz pendant 70 % des temps forts ») | Le plus proche de la perception |
| Inconvénient | Faux positifs massifs, aucune notion de « qui gagne » | Modèle monaural de base, seuil relatif (pas absolu), paramètres à calibrer | Lent, implémentations Python peu nombreuses, résultats plus durs à traduire en réglage EQ |
| Quand le choisir | Visualisation d'appoint | Moteur principal | Validation ponctuelle plus tard, si B donne des résultats douteux |

**Recommandation : B**, avec A conservé pour l'affichage (carte d'occupation spectrale), et trois correctifs explicites aux limites :
1. **Temps** : trames courtes (≈ 23 ms) et résultat exprimé en *% du temps où la cible joue* (trames où A est actif, pas sur toute la durée).
2. **Stéréo** : calcul sur L et R séparément, masquage retenu = minimum des deux (approximation conservatrice du démasquage spatial). Sous 120 Hz, le mono est la norme, donc pas de correction.
3. **Pondération** : un masquage n'est signalé que dans les bandes qui comptent *pour la cible* (bandes où la cible porte une part significative de son énergie propre). Une 808 qui masque les 6 kHz d'un kick n'intéresse personne.

### Deux métriques de masquage
- **Masquage global d'un stem** : masqueur = mix − stem (en pratique, somme des autres stems). Répond à « cette piste s'entend-elle ? ».
- **Masquage par paire** : masqueur = un seul autre stem. Répond à « qui est responsable ? ». C'est cette matrice qui génère les corrections ciblées (couper X sur la piste Y).

### Résolution temps-fréquence dans le grave (point dur)
Distinguer 50 et 60 Hz exige une fenêtre longue (≥ 100 ms) ; voir un transitoire de kick exige une fenêtre courte. **Choix : STFT multi-résolution** (fenêtre longue sous ~250 Hz, courte au-dessus) regroupée en bandes Bark. Pour kick/808 spécifiquement, ajout d'une mesure d'**enveloppe temporelle** dans 30-120 Hz : corrélation des enveloppes kick/808, qui détecte l'absence de sidechain ou de décalage.

### Limites assumées (à afficher dans le rapport)
- Seuil relatif, indépendant du volume d'écoute réel.
- Pas de masquage temporel pré/post (sauf si besoin révélé à l'étape 3).
- Le modèle ne sait pas ce qui doit dominer artistiquement : une voix lead doit masquer un pad, ce n'est pas un défaut. D'où les **rôles** des stems (kick, 808, lead vocal, pad, etc.) et la priorité que tu indiques.

### Autres mesures (mix stéréo)
| Mesure | Méthode | Remarque |
|---|---|---|
| Loudness | BS.1770-4 intégré, court terme, momentané, LRA (EBU Tech 3342) | pyloudnorm couvre intégré + LRA **[V]**, pas le true-peak **[V]**, momentané/court terme non documentés **[V]** |
| True-peak | Sur-échantillonnage x4, sinc fenêtré Kaiser 32 points (port du `TruePeakTable` de RicchBeatz Master) | Déjà validé contre `ffmpeg ebur128=peak=true` dans le repo Master |
| Mud | Énergie 200-500 Hz relative au total et à la pente spectrale ; écart vs tes références | Pas de seuil par genre en dur : comparaison avec tes références, seuil par défaut seulement en l'absence de référence |
| Largeur | Corrélation L/R et ratio S/M par bande ; compatibilité mono (corrélation sous 120 Hz) | |
| Dynamique | PLR (true-peak − LUFS intégré), crest factor par bande, variation du court terme par section | |
| Équilibre | Courbe 1/3 d'octave lissée vs moyenne de tes références (écart en dB par bande) | |

---

## 2. Architecture

### Principe central : une représentation intermédiaire commune
Le moteur ne travaille jamais directement sur l'audio pour le masquage. Il travaille sur des **trames de caractéristiques** (`FeatureFrame`) : par stem, par trame de ~23 ms, l'énergie par bande Bark sur L, R, M et S, plus le pic, le RMS et l'activité. Deux entrées produisent ces mêmes trames :
- **entrée fichier** (Phase A) : décode le WAV/MP3, calcule les trames ;
- **entrée flux** (Phase B) : reçoit les trames déjà calculées par les sondes VST3 (aucun audio ne transite).

Ainsi, masquage, trous spectraux et recommandations sont identiques dans les deux phases.

```
            ┌───────────── entrée fichier (WAV/MP3 → copie → décodage) ──┐
            │                                                            ▼
 sondes VST3 (Phase B) ── trames UDP ──► entrée flux ──► FeatureFrames (par stem)
                                                                         │
                       ┌──────────────────────────┬──────────────────────┤
                       ▼                          ▼                      ▼
                 measures/ (mix)           masking/ (paires)      gaps/ (trous, samples)
                       └──────────────┬───────────┴──────────────────────┘
                                      ▼
                         rules/ (diagnostics + corrections chiffrées, déterministes)
                                      │
                         ai/ (facultatif : priorisation + rédaction, sous garde-fou)
                                      │
                    report/ (HTML + JSON)        store/ (SQLite + .npz)
                                      │
                                   cli/
```

### Modules (paquet Python `mixlab`)
| Module | Rôle | Dépend de |
|---|---|---|
| `io` | Copie de travail horodatée (jamais l'original), hash SHA-256, décodage (soundfile ; ffmpeg pour MP3), rééchantillonnage, alignement des stems (même longueur, même fs) | — |
| `features` | STFT multi-résolution → `FeatureFrame` ; segmentation en sections | `io` |
| `measures` | Loudness, true-peak, mud, largeur, dynamique, équilibre | `features` |
| `masking` | Étalement Bark, SMR, matrice des paires, masquage global, kick/808 | `features` |
| `gaps` | Trous spectraux par section, score d'un sample candidat | `features`, `masking` |
| `rules` | Transforme les mesures en `Finding` + `CorrectionProposal` (valeurs chiffrées) | `measures`, `masking`, `gaps` |
| `ai` | Envoie le JSON des findings à l'API Claude, reçoit une sortie structurée, la valide | `rules` |
| `report` | Rendu HTML autonome (graphiques SVG inline) + export JSON | tout |
| `store` | SQLite (métadonnées, mesures scalaires) + fichiers `.npz` (trames, spectres) | — |
| `testsignals` | Générateur de signaux synthétiques de validation | — |
| `cli` | `mixlab analyze mix.wav --stems dossier/ --ref ref1.wav --role 808=Insert3 ...` | tout |

Règle d'isolation : `features`, `measures`, `masking`, `gaps` et `rules` n'importent ni `ai`, ni `report`, ni aucune GUI.

### Modèle de données (SQLite)
```
project(id, name, created_at)
mix_version(id, project_id, label, mix_path_copy, mix_sha256, created_at, notes, target_json)
    -- target_json : objectif sonore + références choisies (règle 9)
stem(id, mix_version_id, file_copy, sha256, mixer_label, role, priority)
reference(id, project_id, file_copy, sha256, label, features_npz)
analysis_run(id, mix_version_id, engine_version, params_json, started_at, duration_s)
section(id, run_id, start_s, end_s, label)              -- intro / couplet / refrain ou auto
measurement(id, run_id, stem_id NULL=mix, section_id NULL=global,
            metric, band_lo_hz, band_hi_hz, value, unit)
masking(id, run_id, target_stem_id, masker_stem_id NULL=tous,
        section_id, bark_band, masked_ratio, median_smr_db)
finding(id, run_id, element, problem, evidence_json,   -- liste d'ids measurement/masking
        confidence, source)                             -- source = 'rules' | 'ai'
correction(id, finding_id, target_track, device, parameter,
           initial_value, proposed_value, unit, expected_result, risk)
```
Les trames brutes et les spectres vont dans des `.npz` à côté de la base : volumineux, inutiles en SQL.

### Format d'une recommandation (règle 5)
```json
{
  "element": "808 (Insert 3)",
  "problem": "Masque le kick dans 55-80 Hz",
  "evidence": [
    {"ref": "masking#412", "fact": "kick masqué 68 % du temps où il joue, bandes Bark 1-2, SMR médian -4,1 dB"},
    {"ref": "measurement#88", "fact": "corrélation d'enveloppe kick/808 0,82 sur 30-120 Hz"}
  ],
  "confidence": "élevée",
  "correction": {
    "track": "Insert 3 (808)", "device": "Fruity Parametric EQ 2",
    "parameter": "bande 2 : gain à 65 Hz", "initial": "0 dB", "proposed": "-3 dB",
    "alternative": "sidechain du kick sur la 808, réduction 4-6 dB, relâchement 80 ms"
  },
  "expected": "SMR du kick remonté d'environ 3 dB dans 55-80 Hz",
  "risk": "808 moins pleine en écoute seule ; à vérifier sur petites enceintes",
  "hypotheses": ["valeur initiale du gain supposée à 0 dB : le projet n'est pas lu"]
}
```
Point important : l'outil **ne lit pas le projet**, il ne connaît donc pas tes réglages actuels. La « valeur initiale » est soit fournie par toi, soit marquée comme hypothèse.

### Couche IA : options
| | Avantage | Inconvénient | Quand |
|---|---|---|---|
| 1. Règles seules (sans IA) | Déterministe, testable, gratuit | Rédaction rigide, pas de priorisation contextuelle | Toujours présent (règle 8) |
| 2. IA libre sur les mesures | Texte riche | Risque d'inventer des valeurs, non testable | Jamais |
| 3. **Hybride (recommandé)** : les règles produisent les findings et corrections chiffrés ; l'IA priorise, regroupe, rédige et tient compte de ton objectif sonore | Meilleure lisibilité, chiffres garantis | Coût API, latence | Couche facultative |

Garde-fou de l'option 3 : sortie structurée (schéma JSON imposé), chaque nombre de la réponse doit exister dans le JSON d'entrée (vérification automatique) ou être étiqueté `hypothesis`. En cas d'échec, on affiche les règles seules. Le modèle exact et ses paramètres seront vérifiés dans la doc de l'API au moment de l'étape 4.

---

## 3. Stack et réutilisation de RicchBeatz Master

J'ai regardé le repo : `Source/Dsp.h` contient en C++ le K-weighting, le LUFS/LRA, le true-peak (sinc Kaiser 32 points x4), une FFT et le spectre 1/3 d'octave, avec un banc de validation (`Tools/MasterTest.cpp`, comparaison ffmpeg).

| Option | Avantage | Inconvénient | Quand la choisir |
|---|---|---|---|
| A. **Projet Python séparé, Dsp.h comme référence** (recommandé) | Itération rapide en sessions courtes ; NumPy/SciPy, HTML, SQLite et API Claude triviaux ; `MasterTest` sert d'oracle croisé | Deux implémentations du true-peak à maintenir (≈ 40 lignes à porter) | Phase A |
| B. Tout en C++/JUCE dans le repo Master | Réutilisation directe, un seul langage, rapide à l'exécution | Rapport HTML, SQLite, appels API et itération beaucoup plus lents ; mélange deux produits | Si tu veux un exécutable unique sans Python |
| C. Python + Dsp.h exposé via pybind11 | Une seule source de vérité DSP | Chaîne de build Windows (MSVC + CMake + wheel) lourde pour un gain faible | Jamais en Phase A ; éventuellement plus tard |

**Recommandation : A.** Repo : `ricchbizness-lab/assistant-Flstudio`, paquet Python `mixlab`. Réutilisation concrète :
- port NumPy du `TruePeakTable` et du K-weighting (mêmes coefficients) ;
- `MasterTest` et `ffmpeg ebur128=peak=true` comme oracles dans les tests ;
- en **Phase B**, `Dsp.h` est réutilisable *tel quel* dans les sondes VST3 (JUCE, même toolchain CMake), ce qui garantit des bandes et mesures identiques côté sonde et côté moteur.

Stack retenue, avec ajustements par rapport à ta proposition :
- **NumPy/SciPy** : oui, cœur du DSP.
- **librosa** : seulement pour la segmentation en sections et le tempo ; le DSP de masquage est écrit à la main (contrôle et testabilité). Dépendance lourde (numba), on la garde optionnelle si possible.
- **pyloudnorm** : utilisable pour l'intégré et le LRA **[V]**, mais pas de true-peak **[V]** ; je propose d'implémenter BS.1770 nous-mêmes (≈ 60 lignes, déjà fait une fois en C++) et de garder pyloudnorm + ffmpeg comme oracles. Un seul code pour momentané, court terme, intégré, par stem et par section.
- **soundfile** (libsndfile) pour WAV/FLAC ; **ffmpeg** pour MP3 (décodage vers une copie WAV).
- **SQLite** (module standard), **Jinja2** pour le HTML, **SDK anthropic** en option.
- **pytest** pour toute la validation.
- Interface : CLI + HTML. PySide6 seulement si le besoin apparaît (Phase B).

---

## 4. Vérifications FL Studio

### 4.1 Rendu en ligne de commande
- **[V]** FL Studio a un rendu en ligne de commande : `FL.exe /R /Emp3 /F"c:\src\"` (tous les .flp d'un dossier) ou `FL.exe /Emp3 /R "c:\src\project.flp"` (un projet). Syntaxe : `/R[filename] /E<extensions> /F<foldername> [project.flp]`, avec `/O` pour le dossier de sortie. Les exemples du manuel citent FL Studio 2024. Source : manuel officiel, page *Save/Export file formats*.
- **[V]** Aucun drapeau de la ligne de commande ne couvre **Split mixer tracks** : la section n'en mentionne aucun. Le rendu en ligne de commande produit le master seul.
- **[V]** En export GUI *Split mixer tracks* : un .wav par piste mixer, pas de FLAC/MP3/OGG, et les pistes mutées (Master compris) ne sont pas exportées.
- **[V]** Les stems *Split mixer tracks* **contournent le Master** : « Master FX are only included on the Master Track export ». Le stem Master (option *Include*) contient lui les effets du Master. Les effets des pistes d'insert sont inclus si l'option est cochée. Le manuel demande de renommer les pistes (sinon « Insert N »).
- **[NT]** Les pistes de bus/groupe (inserts qui reçoivent d'autres inserts) sont aussi exportées : leur contenu fait doublon avec celui des pistes sources dans la somme des stems. Le routage doit donc être déclaré, ou détecté (un bus ≈ somme de ses sources).
- **[V]** (forum Image-Line, 2024) `/F` rend aussi les projets des sous-dossiers `Backup`, ce qui crée des doublons.
- **Conséquence** : l'export des stems reste manuel en Phase A. L'automatisation possible se limite au mix master (pratique pour réanalyser plusieurs versions), avec un dossier source dédié sans sous-dossier `Backup`.
- **[NT]** Les réglages de rendu appliqués en ligne de commande (fréquence d'échantillonnage, profondeur, queue de reverb) et le nommage exact des fichiers de stems (`<Projet>_<Insert N> - <nom>.wav` ?) sont à constater sur ta machine. Le parseur de noms de stems sera écrit à partir d'un export réel.

### 4.2 Identifier la piste mixer d'une instance de plugin (Phase B)
Trois pistes, par ordre de fiabilité :
1. **Script FL en lecture seule + identifiant exposé par la sonde** (recommandé, **[NT]**). L'API de script documente `mixer.getTrackName(index)` (API v1) et, dans le module `plugins`, `getPluginName(index, slotIndex)`, `getParamCount`, `getParamName` et `getParamValue(paramIndex, index, slotIndex)` (API v8), où `index` désigne la piste mixer et `slotIndex` l'emplacement d'effet **[V]** (stubs IL-Group, © Image-Line). Méthode : chaque sonde expose un paramètre « ID » unique ; le script parcourt pistes × emplacements, trouve les instances nommées « MixLab Probe », lit leur ID et produit la table ID → (piste, nom de piste). Tout reste en lecture.
2. **VST3 `IInfoListener::setChannelContextInfos`** (le standard pour transmettre le nom de piste à un plugin) : **sources contradictoires**. Un mainteneur de framework Rust indique que FL Studio est le seul DAW testé qui ne l'appelle pas ; des utilisateurs de FabFilter Pro-Q 4 disent voir les noms de pistes FL dans la liste d'instances. **[NT]** À tester en 10 minutes avec une sonde JUCE minimale (`updateTrackProperties`).
3. **Saisie manuelle** du nom dans l'UI de la sonde : solution de secours, toujours fiable.

**[S] Risque à vérifier tôt en Phase B** : l'interpréteur Python embarqué de FL pour les scripts de contrôleur est restreint (bibliothèque standard partielle). Le script devra peut-être transmettre la table par un canal détourné (SysEx MIDI vers un port virtuel, ou écriture de fichier si `open()` est disponible). À tester avant de construire quoi que ce soit dessus.

---

## 5. Plan de développement

Chaque étape fait 1 à 3 sessions courtes et se termine par un critère binaire. Rien n'est « terminé » sans tests verts.

**Étape 0 (1 session) : socle.** Repo, `pyproject`, pytest, `testsignals` (sinus, bruit rose, bruit blanc, sinus inter-échantillons, paires de sinus), copie de travail + hash.
*Critère* : les tests de l'outil de copie prouvent que l'original n'est jamais ouvert en écriture (permissions en lecture seule dans le test) et que le hash est stable.

**Étape 1 (2-3 sessions) : mesures de base validées.**
- Sinus 1 kHz -20 dBFS sur L et R → -20,0 LUFS (±0,1) ; sur un seul canal → -23,0 LUFS (±0,1).
- Bruit rose : écart ≤ 0,1 LU avec pyloudnorm et ffmpeg ; LRA ≤ 0,2 LU d'écart avec ffmpeg.
- Fichiers de conformité EBU Tech 3341/3342 si disponibles au téléchargement **[NT]** : tolérances de la norme.
- True-peak : sinus à fs/4 déphasé de 45°, crête des échantillons -3,01 dBFS → true-peak ≈ 0,0 dBTP (±0,2) ; écart ≤ 0,1 dB avec `ffmpeg ebur128=peak=true` et `MasterTest` sur 3 morceaux réels.
- Spectre : un sinus tombe dans la bonne bande 1/3 d'octave et la bonne bande Bark ; le bruit rose donne une courbe plate (±0,5 dB) en 1/3 d'octave.
*Critère* : `pytest tests/measures` vert, et un tableau comparatif ffmpeg/MasterTest/mixlab sur 3 vrais exports.

*Résultat (15/11/2026)* :
- Les fichiers EBU n'ont pas pu être téléchargés (HTTP 403). Les cas d'essai ont été reconstruits depuis le texte des normes (`mixlab/ebu_cases.py`) : Tech 3341 cas 1-5, 9, 10, 12, 13, 15-23 et Tech 3342 cas 1-4, tous dans la tolérance de la norme (`tests/test_ebu_compliance.py`).
- Changement par rapport à la conception : momentané et court terme calculés au pas de 10 ms (un pas de 100 ms donnait -23,45 LUFS au cas 13, hors tolérance). L'intégré garde la grille de 100 ms de BS.1770.
- Oracles (`tools/compare_oracles.py`, tableau dans `docs/validation/step1-oracles.md`) : aucun écart hors tolérance avec ffmpeg et pyloudnorm sur 22 fichiers. Le code de Master (`Dsp.h`) est compilé sans JUCE au lieu de `MasterTest`, qui ne sait pas mesurer un fichier seul.
- **Partiel** : 2 morceaux réels au lieu de 3 (deux références reçues ; tes exports arrivent avant l'étape 3). À compléter avec le premier export.

**Étape 2 (2-3 sessions) : analyse du mix stéréo.**
- Largeur : L = R → corrélation 1, S/M = -∞ ; bruits indépendants → corrélation ≈ 0 ; L = -R → -1 et alerte mono.
- Mud : bruit rose + bosse +6 dB à 300 Hz (Q 1) → indicateur de mud +4 à +6 dB par rapport au bruit rose seul ; aucun déclenchement sur bruit rose seul.
- Dynamique : signal compressé vs non compressé → PLR et crest dans le bon ordre et aux bonnes valeurs calculées.
- Sections : segmentation sur un signal synthétique à 3 parties nettement différentes → frontières à ±0,5 s.
- Sortie : `mixlab analyze mix.wav` produit un JSON de mesures.
*Critère* : tests verts et JSON relu par toi sur un de tes mix, avec ton avis « cohérent / pas cohérent ».

*Résultat (15/11/2026)* :
- Tests verts : largeur (mono, indépendant, opposition de phase, un seul canal, panoramique, profil par bande), dynamique (crête d'un sinus, crête par bande, compression), pente spectrale (rose 0, blanc +3 dB/octave), mud, normalisation du loudness, sections (3 parties, saut de niveau seul, signal stationnaire, petit changement ignoré), rôles et `roles.yaml`.
- **Critère corrigé (mud)** : la fourchette « +4 à +6 dB » était une estimation fausse de la Phase 0. Les flancs de la cloche relèvent aussi les bandes de la pente (+0,8 dB à 125 Hz, +1,3 dB à 800 Hz). La valeur exacte, calculée depuis la réponse du filtre, est 3,73 dB ; la mesure donne 3,66 à 3,82 dB selon le tirage du bruit. Le test compare désormais à cette prédiction (±0,3 dB), sans modification de la mesure.
- Comparaison aux références : chaque spectre est ramené à 0 LUFS intégré avant comparaison (demande de l'utilisateur). Test : le même signal 10 dB plus fort donne un écart nul (< 0,01 dB).
- Sections sur musique réelle : sans vérité terrain. La durée minimale par défaut est passée de 4 à 8 s après essai sur MONEY et MARACANA (16 sections trop courtes avec 4 s). À valider contre la structure réelle d'un morceau.
- **En attente** : l'avis de l'utilisateur sur l'analyse d'un de ses mix (extrait attendu avant l'étape 3).

**Étape 3 (3 sessions) : masquage par paire de stems.**
- Sinus 1 kHz -20 dB + sinus 1,1 kHz -40 dB → le second est masqué.
- Sinus 1 kHz -20 dB + sinus 4 kHz -40 dB → pas de masquage.
- Asymétrie : 500 Hz fort masque 700 Hz faible ; 700 Hz fort masque nettement moins 500 Hz faible (SMR différent d'au moins X dB, valeur fixée par le modèle).
- Temps : kick et 808 synthétiques alternés (jamais simultanés) → masquage ≈ 0 ; simultanés → masquage détecté.
- Stéréo : même paire panoramiquée à 100 % L / 100 % R → masquage réduit par rapport au centre.
- Analyse du bus : stems synthétiques (kick + 808 + pad) sommés puis écrêtés à -1 dBFS pour simuler le Master → l'écrêtage est attribué au bon stem (kick ≥ 80 % si seul le kick dépasse) ; somme non écrêtée → écart nul (< -60 dB).
- Routage : un stem « bus » égal à la somme de deux autres est détecté et exclu de la somme.
*Critère* : tests verts, puis test d'écoute sur un de tes morceaux : les 3 premiers conflits signalés doivent correspondre à ce que tu entends. Si ce n'est pas le cas, on recalibre avant d'aller plus loin.

**Étape 4 (2 sessions) : règles, format des recommandations et couche IA.**
- `rules` génère des findings complets (les 7 champs de la règle 5).
- `ai` : schéma de sortie imposé, vérificateur « chaque nombre provient de l'entrée ».
*Critère* : un test injecte une réponse IA contenant une valeur inventée, qui doit être rejetée ; sans clé API, le rapport sort quand même ; le JSON envoyé ne contient aucun échantillon audio (vérifié par test).

**Étape 5 (2 sessions) : trous spectraux et sound selection.**
- Trou = bande où le mix est sous sa tendance lissée (ou sous tes références) d'au moins N dB, sur une section donnée.
- Score d'un sample : part de son énergie qui tombe dans les trous, et masquage qu'il causerait ou subirait (réutilise l'étape 3).
*Critère* : mix synthétique avec un trou creusé à 2-4 kHz → trou détecté ; un sample de bruit filtré 2-4 kHz est mieux classé qu'un sample 200-400 Hz.

**Étape 6 (2 sessions) : rapport et historique.**
- HTML autonome (un seul fichier, SVG inline), JSON des mesures, SQLite par version de mix, comparaison v1 → v2 (ce qui a bougé, en dB).
*Critère* : deux versions d'un même mix analysées → le rapport de comparaison montre l'effet attendu d'une correction appliquée (par exemple le SMR du kick qui remonte après la coupe sur la 808).

**Phase B** (sondes VST3) : seulement après validation de l'étape 6. Première tâche : les deux tests [NT] de la section 4.2.

---

## 6. Risques et questions ouvertes

### Risques
| Risque | Impact | Parade |
|---|---|---|
| Le modèle de masquage signale des conflits inaudibles ou rate les vrais | Perte de confiance dans l'outil | Critère d'écoute à l'étape 3 ; niveau de confiance affiché ; recalibrage avant l'étape 4 |
| Somme des stems ≠ Master : stems avant bus **[V]**, pistes mutées non exportées **[V]**, bus/groupes en doublon **[NT]** | Masquage calculé sur un état différent de ce que tu entends ; somme faussée par les bus | Écart mesuré et exploité (analyse du bus, voir Décisions) ; routage déclaré ou détecté pour exclure les bus de la somme |
| Corrections en paramètres inexacts pour le plugin réel (unités de largeur de bande de Fruity Parametric EQ 2, etc.) **[NT]** | Instructions inapplicables | Format de correction par plugin, vérifié sur ta version de FL ; Q exprimé aussi en octaves |
| Valeurs initiales inconnues (le projet n'est pas lu) | Corrections en absolu fausses | Corrections exprimées en *delta* (« -3 dB à partir du réglage actuel »), valeurs initiales en hypothèse |
| Résolution grave insuffisante (kick/808) | Diagnostics flous sous 100 Hz | STFT multi-résolution et analyse d'enveloppe dédiée |
| Dépendances Windows (ffmpeg dans le PATH, numba via librosa) | Installation pénible | ffmpeg détecté au démarrage avec message clair ; librosa optionnel |
| Coût et latence de l'API | Faible | Option, entrée = JSON compact, cache par hash de run |
| Interpréteur Python de FL restreint **[S]** | Phase B compromise côté script | Tester en premier en Phase B ; saisie manuelle en secours |

### Décisions (réponses du 13/11/2026)
1. **Repo** : `ricchbizness-lab/assistant-Flstudio` (ce document y est désormais). Paquet Python : `mixlab`.
2. **EQ cible** : Fruity Parametric EQ 2 uniquement. Les unités exactes de ses paramètres (largeur de bande, plage de gain) seront relevées sur ta version de FL avant l'étape 4.
3. **Stems** : 5 à 10, jusqu'à ~20. Conséquences : jusqu'à 380 paires ordonnées à calculer (sans problème en temps de calcul), donc le rapport doit **filtrer** : top 5 des conflits par défaut, matrice complète en annexe. Les rôles (kick, 808, lead…) seront devinés depuis le nom des pistes, avec correction manuelle.
4. **Références** : fournies par toi (en attente).
5. **Bus master** : FL Limiter + soft clipper. Voir ci-dessous.
6. **Python 3.11** sur Windows : OK.
7. Fréquence d'échantillonnage des exports : non précisée ; l'outil accepte 44,1 et 48 kHz et rééchantillonne si les stems diffèrent.

### Bus master (limiteur + soft clipper) : traitement retenu
Oui, c'est utile, et c'est même une des mesures les plus intéressantes. Comme les stems contournent le Master **[V]**, un seul export *Split mixer tracks* avec le stem Master inclus donne :
- **les stems** = le mix *avant* bus ; c'est sur eux qu'on calcule le masquage ;
- **le stem Master** = ce que tu entends ; c'est sur lui qu'on calcule loudness, true-peak, largeur et dynamique du rendu final ;
- **l'écart entre les deux** (somme des stems vs Master, après alignement) = ce que fait ton bus : réduction de gain et écrêtage, **instant par instant**. En croisant ces instants avec l'activité de chaque stem, l'outil peut dire *quel élément déclenche le limiteur et le clipper* (typiquement : « 70 % de l'écrêtage tombe sur les coups de kick, 20 % sur les attaques de 808 »). C'est une information directement actionnable (niveau, transitoire ou sidechain de l'élément fautif).

**Challenge** : ce bus fait doublon avec RicchBeatz Master, qui a déjà son limiteur true-peak et sa boucle de loudness. Deux limiteurs en série (plus un clipper) écrasent les transitoires deux fois et faussent l'analyse de RicchBeatz. Trois façons de faire :

| Option | Avantage | Inconvénient | Quand |
|---|---|---|---|
| A. Bus désactivé à l'export vers RicchBeatz, crêtes vers -6 dBFS | RicchBeatz travaille sur un signal propre, une seule étape de limitation | Le mix sonne moins fort pendant la production | **Recommandé** pour le fichier final |
| B. Soft clipper gardé (choix de couleur), limiteur retiré | Garde le caractère du clip sur les drums | Le clip est figé avant le mastering | Si le clip fait partie de ton son |
| C. Tout gardé | Rien à changer | Double limitation, marge de RicchBeatz réduite | Écoute de travail seulement |

Pour l'assistant de mixage, ça ne change rien : il analyse les stems (avant bus) et le stem Master (après bus), quelle que soit l'option.

---

## Sources
- Manuel FL Studio, Save/Export file formats (ligne de commande, Split mixer tracks) : https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/fformats_save_export.htm
- Forum Image-Line, doublons `/F` avec les dossiers Backup : https://forum.image-line.com/viewtopic.php?p=1969608
- API de script FL, `mixer` (pistes) : https://il-group.github.io/FL-Studio-API-Stubs/midi_controller_scripting/mixer/tracks
- API de script FL, `plugins` : https://il-group.github.io/FL-Studio-API-Stubs/midi_controller_scripting/plugins/
- Manuel FL Studio, emplacements d'effets du mixer : https://flstudio.image-line.com/help/html/mixer_plugin.htm
- VST3 `setChannelContextInfos` non appelé par FL (nice-plug) : https://codeberg.org/RustAudio/nice-plug/pulls/57
- Noms de pistes FL visibles dans Pro-Q (forum FabFilter) : https://prod.fabfilter.com/forum/add-comment/3360
- pyloudnorm : https://github.com/csteinmetz1/pyloudnorm
