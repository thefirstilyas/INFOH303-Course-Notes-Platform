# INFOH303 – Plateforme de Partage de Résumés de Cours

Application web Flask – Partie 2
Groupe AB – ULB 2025-2026

**Membres :** Gharbi Marwa · El Haichami Ilyas · Benjelloun Mohamed · Chaabane Youssef

## Prérequis

- **PostgreSQL** ≥ 14 (incluant les commandes `psql` et `createdb`)
- **Python** ≥ 3.8

Installation sous Ubuntu / Debian :
```bash
sudo apt install postgresql postgresql-client python3 python3-pip python3-venv
```

Le projet se connecte par défaut via socket Unix (auth peer) avec votre nom d'utilisateur système. Pour que ça marche directement, votre user Unix doit avoir un rôle PostgreSQL correspondant :
```bash
sudo -u postgres createuser -s $USER
```

Si vous préférez configurer manuellement (host TCP + mot de passe), une page `/setup` est disponible au premier lancement de l'app si la connexion échoue.

## Lancer le projet

```bash
# 1. Environnement Python isolé (recommandé, obligatoire sur Ubuntu 23.04+)
python3 -m venv venv
source venv/bin/activate                      # à refaire à chaque nouveau terminal

# 2. Dépendances
pip install -r requirements.txt

# 3. Base de données
createdb infoh303
psql -d infoh303 -f sql/create.sql
python3 load_data.py

# 4. Lancement de l'app
python3 run.py
```

Ouvrir **http://localhost:5000**

> **À propos du venv** : depuis Ubuntu 23.04 / Debian 12 (PEP 668), `pip install` au niveau système est bloqué pour protéger les paquets Debian. Le venv contourne ça proprement. Alternative non recommandée : `pip install -r requirements.txt --break-system-packages`.

Pour utiliser un autre nom de base ou d'autres paramètres de connexion :
```bash
DB_NAME=ma_base DB_USER=postgres DB_PASSWORD=secret python3 load_data.py
DB_NAME=ma_base DB_USER=postgres DB_PASSWORD=secret python3 run.py
```

## Structure du projet

```
infoh303/
├── run.py              # point d'entrée Flask
├── load_data.py        # import des données (CSV, XML, JSON)
├── requirements.txt    # dépendances Python
├── app/db.py           # couche connexion PostgreSQL
├── web/app.py          # routes Flask + 8 requêtes analytiques
├── web/templates/      # templates Jinja2 (10 pages)
├── web/static/         # CSS (thème violet sombre)
├── sql/create.sql      # DDL : 8 tables, 8 triggers, 2 vues, 8 indexes
├── data/               # données fournies (CSV, XML, JSON)
├── rapport_bdd.pdf     # rapport Partie 1 mis à jour
├── presentation.pdf    # slides de défense (28 pages)
└── E-R Diagram.png     # diagramme Entité-Association
```

## Fonctionnalités principales

- Inscription / connexion, tableau de bord personnel avec rang
- Catalogue de cours avec recherche et ajout
- Publication, modification, suppression et évaluation (1–5★) de résumés
- Système de points (+10 publication, +5 évaluation donnée ou reçue)
- Boutique cosmétique : 45 badges, titres et thèmes
- Système de niveaux automatique (trigger) avec attribution des titres
- Classement mensuel avec snapshot historique
- Dashboard analytique : 8 requêtes SQL avec visualisations Chart.js

## Triggers PostgreSQL (8)

| Trigger | Événement | Rôle |
|---|---|---|
| `trg_note_moyenne` | AFTER INS/UPD/DEL sur EVALUATION | recalcule `RESUME.note_moyenne` |
| `trg_auto_evaluation` | BEFORE INS/UPD sur EVALUATION | interdit d'évaluer son propre résumé |
| `trg_actif_unique` | BEFORE INS/UPD sur POSSEDE | max 1 badge actif par utilisateur |
| `trg_niveau_resume` | AFTER INS/DEL sur RESUME | recalcule le niveau + attribue les titres |
| `trg_niveau_note` | AFTER UPDATE sur note_moyenne | recalcule le niveau après changement de note |
| `trg_eval_date` | BEFORE INSERT sur EVALUATION | date_eval ≥ date_publication |
| `trg_transaction_date` | BEFORE INSERT sur TRANSACTION_POINTS | date_tx ≥ date_inscription |
| `trg_achat_date` | BEFORE INSERT sur POSSEDE | date_achat ≥ date_inscription |

## Documents fournis

- `rapport_bdd.pdf` — rapport Partie 1 (modèle ER, modèle relationnel, contraintes, 11 hypothèses)
- `presentation.pdf` — slides de défense (architecture, choix techniques, 8 requêtes SQL/AR/CT)
- `E-R Diagram.png` — diagramme Entité-Association
