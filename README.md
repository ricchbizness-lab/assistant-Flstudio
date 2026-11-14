# assistant-Flstudio

Assistant de mixage pour exports FL Studio : il mesure un mix et ses stems, trouve où les fréquences se masquent et prépare des corrections chiffrées pour Fruity Parametric EQ 2. Il ne modifie jamais un projet ni un fichier original.

Conception et plan : [`docs/PHASE0.md`](docs/PHASE0.md).

## Installation (Windows 11, Python 3.11)

```bash
py -3.11 -m venv .venv
```

```bash
.venv\Scripts\python -m pip install -e ".[dev]"
```

```bash
.venv\Scripts\python -m pytest
```

## Commandes disponibles

Copie de travail vérifiée d'un fichier (l'original n'est ouvert qu'en lecture) :

```bash
.venv\Scripts\python -m mixlab copy "C:\chemin\vers\mix.wav"
```

Données de test depuis la release privée `test-data-v1` (nécessite un jeton GitHub en lecture dans `GITHUB_TOKEN`) :

```bash
.venv\Scripts\python -m mixlab fetch-test-data
```

Tout ce qui est audio va dans `data/`, ignoré par git.

## Nommage des pistes mixer (avant export « Split mixer tracks »)

Préfixe de rôle en majuscules, puis le nom libre : `KICK`, `808`, `SNARE`, `HAT`, `PERC`, `LEAD`, `KEYS`, `PAD`, `FX`, `VOX`, `BUS`, `SEND`.
Exemple : `808 slide`, `BUS drums`. Les pistes sans préfixe sont décrites dans `roles.yaml` (à partir de l'étape 2).
