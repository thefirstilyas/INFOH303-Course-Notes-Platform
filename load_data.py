"""
Script de chargement des données fournies par le professeur.
Lit : cours.csv, utilisateurs (XML), recompenses.xml, commentaires.json
et insère tout dans la base PostgreSQL infoh303.

Usage :
    python load_data.py
"""

import csv
import json
import os
import sys
import xml.etree.ElementTree as ET
import psycopg2
from psycopg2.extras import RealDictCursor
from pathlib import Path

# Import les constantes points depuis app/db.py pour rester en phase avec l'app
sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.db import POINTS_PUBLICATION, POINTS_EVALUATION

DATA_DIR = Path("data")

import getpass

DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "/var/run/postgresql"),
    "dbname":   os.getenv("DB_NAME",     "infoh303"),
    "user":     os.getenv("DB_USER",     getpass.getuser()),
    "password": os.getenv("DB_PASSWORD", ""),
    "port":     os.getenv("DB_PORT",     "5432"),
}

# Mapping des types non reconnus par notre schéma
TYPE_COSMETIQUE_MAP = {
    "badge":      "badge",
    "titre":      "titre",
    "theme":      "theme",
    "cosmetique": "theme",  # type inconnu → on le traite comme thème
}

# Quel titre récompense quel palier de niveau (par nom, pas par id)
TITRE_NIVEAUX = {
    "Titre étudiant modèle": 2,
    "Titre mentor":          3,
    "Top Contributeur":      4,
    "Maître du savoir":      5,
    "Titre professeur":      6,
    "Titre VIP":             7,
    "Titre élite":           8,
    "Légende du campus":     9,
}


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def _safe_int(value, default=0):
    """Convertit en int, retourne default si valeur absente ou mal formée."""
    try:
        return int(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _safe_float(value, default=None):
    """Convertit en float, retourne default si valeur absente ou mal formée."""
    try:
        return float(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


# ──────────────────────────────────────────────
# 1. COURS  (CSV)
# ──────────────────────────────────────────────
def load_cours(cur):
    print("→ Chargement des cours...")
    inserted = 0
    with open(DATA_DIR / "cours.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cur.execute(
                """
                INSERT INTO COURS (code_cours, nom_cours, faculte, annee_academique)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (code_cours) DO NOTHING
                """,
                (row["code_cours"], row["nom"], row["faculte"], "2025-2026"),
            )
            inserted += cur.rowcount
    print(f"   {inserted} cours insérés.")


# ──────────────────────────────────────────────
# 2. OBJETS COSMÉTIQUES  (XML recompenses)
# ──────────────────────────────────────────────
def load_objets(cur):
    print("→ Chargement des objets cosmétiques...")
    tree = ET.parse(DATA_DIR / "recompenses.xml")
    root = tree.getroot()
    inserted = 0
    for objet in root.findall("objet"):
        type_brut = objet.findtext("type", "theme")
        type_ok   = TYPE_COSMETIQUE_MAP.get(type_brut, "theme")
        cur.execute(
            """
            INSERT INTO OBJET_COSMETIQUE (nom, description, prix_points, type_cosmetique)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (nom) DO NOTHING
            """,
            (
                objet.findtext("nom"),
                objet.findtext("description"),
                _safe_int(objet.findtext("prix"), 0),
                type_ok,
            ),
        )
        inserted += cur.rowcount

    # Renseigne niveau_requis pour les titres (par nom, indépendant des id SERIAL)
    titres_taggues = 0
    for nom_titre, niveau in TITRE_NIVEAUX.items():
        cur.execute(
            "UPDATE OBJET_COSMETIQUE SET niveau_requis = %s WHERE nom = %s AND type_cosmetique = 'titre'",
            (niveau, nom_titre),
        )
        titres_taggues += cur.rowcount

    print(f"   {inserted} objets insérés, {titres_taggues} titres taggués par niveau_requis.")


# ──────────────────────────────────────────────
# 3. UTILISATEURS + RÉSUMÉS + POSSEDE  (XML utilisateurs)
# ──────────────────────────────────────────────
def load_utilisateurs(cur):
    print("→ Chargement des utilisateurs, résumés et achats...")
    tree = ET.parse(DATA_DIR / "utilisateurs")
    root = tree.getroot()

    u_inserted = 0
    r_inserted = 0
    p_inserted = 0

    for u in root.findall("utilisateur"):
        nom   = u.findtext("nomUtilisateur")
        email = u.findtext("email")
        date  = u.findtext("dateInscription")
        pts   = _safe_int(u.findtext("points"), 0)
        # On ignore <niveau> du XML : c'est un attribut dérivé, le trigger
        # le recalcule à partir des résumés insérés juste après.
        cur.execute(
            """
            INSERT INTO UTILISATEUR (nom_utilisateur, email, date_inscription, nbr_pt, niveau)
            VALUES (%s, %s, %s, %s, 1)
            ON CONFLICT (nom_utilisateur) DO NOTHING
            RETURNING id_utilisateur
            """,
            (nom, email, date, pts),
        )
        row = cur.fetchone()
        if row is None:
            cur.execute("SELECT id_utilisateur FROM UTILISATEUR WHERE nom_utilisateur = %s", (nom,))
            row = cur.fetchone()
        id_user = row["id_utilisateur"]
        u_inserted += 1

        # Résumés
        for resume in u.findall("resumes/resume"):
            code_cours = (resume.findtext("cours") or "").strip()
            titre      = resume.findtext("titre")
            date_pub   = resume.findtext("datePublication")
            note_moy   = resume.findtext("noteMoyenne")

            # Rejet conceptuel : un résumé sans code de cours n'a pas de sens
            # (la PK COURS.code_cours ne peut pas être vide)
            if not code_cours:
                continue

            # S'assurer que le cours existe
            cur.execute(
                """
                INSERT INTO COURS (code_cours, nom_cours, faculte, annee_academique)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (code_cours) DO NOTHING
                """,
                (code_cours, code_cours, "Inconnu", "2025-2026"),
            )

            cur.execute(
                """
                INSERT INTO RESUME
                    (titre, description, date_publication, version, visibilite,
                     note_moyenne, id_utilisateur, code_cours)
                VALUES (%s, %s, %s, 1, 'public', %s, %s, %s)
                ON CONFLICT DO NOTHING
                RETURNING id_resume
                """,
                (
                    titre,
                    titre,
                    date_pub,
                    _safe_float(note_moy, None),
                    id_user,
                    code_cours,
                ),
            )
            res = cur.fetchone()
            if res:
                r_inserted += 1
                id_resume = res["id_resume"]
                # Transaction de points pour la publication
                cur.execute(
                    """
                    INSERT INTO TRANSACTION_POINTS
                        (montant, type_transaction, date_transaction, id_utilisateur, id_resume)
                    VALUES (%s, 'gain', %s, %s, %s)
                    """,
                    (POINTS_PUBLICATION, date_pub, id_user, id_resume),
                )

        # Achats d'objets
        titre_actif = u.findtext("titreActif")
        for achat in u.findall("achats/objet"):
            nom_objet = achat.text
            cur.execute(
                "SELECT id_objet, prix_points, type_cosmetique FROM OBJET_COSMETIQUE WHERE nom = %s",
                (nom_objet,),
            )
            obj = cur.fetchone()
            if obj is None:
                continue
            est_actif = (nom_objet == titre_actif)
            cur.execute(
                """
                INSERT INTO POSSEDE (id_utilisateur, id_objet, date_achat, est_actif)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (id_user, obj["id_objet"], date, est_actif),
            )
            if cur.rowcount:
                p_inserted += 1
                prix = obj["prix_points"]
                if prix > 0:
                    cur.execute(
                        """
                        INSERT INTO TRANSACTION_POINTS
                            (montant, type_transaction, date_transaction, id_utilisateur, id_objet)
                        VALUES (%s, 'dépense', %s, %s, %s)
                        """,
                        (prix, date, id_user, obj["id_objet"]),
                    )

    print(f"   {u_inserted} utilisateurs, {r_inserted} résumés, {p_inserted} achats insérés.")


# ──────────────────────────────────────────────
# 4. ÉVALUATIONS  (JSON commentaires)
# ──────────────────────────────────────────────
def load_evaluations(cur):
    print("→ Chargement des évaluations...")
    with open(DATA_DIR / "commentaires.json", encoding="utf-8") as f:
        data = json.load(f)

    inserted = 0
    skipped  = 0

    for ev in data.get("evaluations", []):
        # Lecture défensive : on skip toute évaluation à laquelle il manque
        # un champ critique plutôt que de planter sur KeyError
        try:
            auteur       = ev["auteur"]
            destinataire = ev["destinataire"]
            cours        = ev["resume"]["cours"]
            titre        = ev["resume"]["titre"]
            note         = _safe_int(ev["note"], 0)
        except (KeyError, TypeError):
            skipped += 1
            continue
        commentaire  = ev.get("commentaire")

        # Récupérer les IDs
        cur.execute("SELECT id_utilisateur FROM UTILISATEUR WHERE nom_utilisateur = %s", (auteur,))
        row_a = cur.fetchone()
        cur.execute("SELECT id_utilisateur FROM UTILISATEUR WHERE nom_utilisateur = %s", (destinataire,))
        row_d = cur.fetchone()

        if not row_a or not row_d:
            skipped += 1
            continue

        id_auteur      = row_a["id_utilisateur"]
        id_destinataire = row_d["id_utilisateur"]

        cur.execute(
            """
            SELECT id_resume FROM RESUME
            WHERE id_utilisateur = %s AND code_cours = %s AND titre = %s
            LIMIT 1
            """,
            (id_destinataire, cours, titre),
        )
        row_r = cur.fetchone()
        if not row_r:
            skipped += 1
            continue

        id_resume = row_r["id_resume"]

        cur.execute(
            """
            INSERT INTO EVALUATION (note, commentaire, date_eval, id_utilisateur, id_resume)
            VALUES (%s, %s, CURRENT_DATE, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING id_eval
            """,
            (note, commentaire, id_auteur, id_resume),
        )
        row_e = cur.fetchone()
        if not row_e:
            skipped += 1
            continue

        id_eval = row_e["id_eval"]
        inserted += 1

        # Points pour l'évaluateur
        cur.execute(
            """
            INSERT INTO TRANSACTION_POINTS
                (montant, type_transaction, date_transaction, id_utilisateur, id_eval)
            VALUES (%s, 'gain', CURRENT_DATE, %s, %s)
            """,
            (POINTS_EVALUATION, id_auteur, id_eval),
        )
        # Points pour l'auteur du résumé
        cur.execute(
            """
            INSERT INTO TRANSACTION_POINTS
                (montant, type_transaction, date_transaction, id_utilisateur, id_eval)
            VALUES (%s, 'gain', CURRENT_DATE, %s, %s)
            """,
            (POINTS_EVALUATION, id_destinataire, id_eval),
        )

        # Mettre à jour note_moyenne
        cur.execute(
            """
            UPDATE RESUME SET note_moyenne = (
                SELECT AVG(note) FROM EVALUATION WHERE id_resume = %s
            ) WHERE id_resume = %s
            """,
            (id_resume, id_resume),
        )

    print(f"   {inserted} évaluations insérées, {skipped} ignorées (données manquantes).")


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
def main():
    print("\n=== Chargement des données INFOH303 ===\n")
    conn = get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                load_cours(cur)
                load_objets(cur)
                load_utilisateurs(cur)
                load_evaluations(cur)
        print("\n✓ Toutes les données ont été chargées avec succès.\n")
    except Exception as e:
        print(f"\n✗ Erreur : {e}\n")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
