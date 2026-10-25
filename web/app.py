import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, jsonify)
from functools import wraps
import psycopg2
from app import db
from app.db import POINTS_PUBLICATION, POINTS_EVALUATION

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "infoh303_ulb_2026_secret")


def db_ok():
    try:
        conn = db.get_connection()
        conn.close()
        return True
    except Exception:
        return False


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Connectez-vous pour accéder à cette page.", "warning")
            return redirect(url_for("auth"))
        # Vérifier que l'utilisateur existe toujours en base
        user = db.execute(
            "SELECT id_utilisateur FROM UTILISATEUR WHERE id_utilisateur = %s",
            (session["user_id"],), fetch="one"
        )
        if not user:
            session.clear()
            flash("Session expirée. Reconnectez-vous.", "warning")
            return redirect(url_for("auth"))
        return f(*args, **kwargs)
    return decorated


BADGE_ICONS = {
    "Débutant":            "🌱",
    "Apprenti":            "📚",
    "Badge participation": "🎯",
    "Contributeur actif":  "✍️",
    "Badge fidélité":      "🔁",
    "Badge bronze":        "🥉",
    "Contributeur expert": "⭐",
    "Badge argent":        "🥈",
    "Badge physique":      "⚡",
    "Badge math":          "🔢",
    "Badge économie":      "💰",
    "Expert SQL":          "🗄️",
    "Badge IA":            "🤖",
    "Badge or":            "🥇",
    "Badge diamant":       "💎",
}

# Mapping nom d'objet → slug CSS pour les thèmes de couleur
THEME_SLUGS = {
    "Profil sombre":          "dark",
    "Profil clair":           "light",
    "Thème nuit":             "night",
    "Thème pastel":           "pastel",
    "Thème sombre premium":   "dark-premium",
    "Thème néon":             "neon",
}

# Mapping nom d'objet → emoji pour les icônes de profil
THEME_ICONS = {
    "Icône étoile":   "⭐",
    "Icône flamme":   "🔥",
    "Icône trophée":  "🏆",
    "Icône livre":    "📖",
    "Icône cerveau":  "🧠",
    "Icône fusée":    "🚀",
    "Icône éclair":   "⚡",
    "Icône cible":    "🎯",
}

# Mapping nom d'objet → classe CSS de cadre
FRAME_CLASSES = {
    "Cadre simple":         "frame-simple",
    "Cadre premium":        "frame-premium",
    "Cadre doré":           "frame-gold",
    "Cadre arc-en-ciel":    "frame-rainbow",
}

# Mapping nom d'objet → classe CSS d'effet
EFFECT_CLASSES = {
    "Effet brillant":       "effect-glow",
    "Effet feu":            "effect-fire",
    "Effet glace":          "effect-ice",
    "Effet holographique":  "effect-holo",
}

@app.context_processor
def inject_user_titre():
    if "user_id" in session:
        row = db.execute(
            "SELECT titre_certif FROM v_user_titre WHERE id_utilisateur = %s",
            (session["user_id"],), fetch="one"
        )
        current_titre = row["titre_certif"] if row else None

        # tous les objets cosmétiques actifs de l'utilisateur
        actifs = db.execute(
            """
            SELECT oc.nom, oc.type_cosmetique
            FROM POSSEDE p
            JOIN OBJET_COSMETIQUE oc ON oc.id_objet = p.id_objet
            WHERE p.id_utilisateur = %s AND p.est_actif = TRUE
            """,
            (session["user_id"],), fetch="all"
        ) or []

        theme_slug   = None
        theme_icon   = None
        frame_class  = None
        effect_class = None

        for item in actifs:
            nom  = item["nom"]
            typ  = item["type_cosmetique"]
            if typ == "theme":
                if nom in THEME_SLUGS:
                    theme_slug = THEME_SLUGS[nom]
                elif nom in THEME_ICONS:
                    theme_icon = THEME_ICONS[nom]
                elif nom in FRAME_CLASSES:
                    frame_class = FRAME_CLASSES[nom]
                elif nom in EFFECT_CLASSES:
                    effect_class = EFFECT_CLASSES[nom]

        return {
            "current_titre":  current_titre,
            "badge_icons":    BADGE_ICONS,
            "current_theme_slug":  theme_slug,
            "current_theme_icon":  theme_icon,
            "current_frame_class": frame_class,
            "current_effect_class": effect_class,
        }
    return {
        "current_titre":  None,
        "badge_icons":    BADGE_ICONS,
        "current_theme_slug":  None,
        "current_theme_icon":  None,
        "current_frame_class": None,
        "current_effect_class": None,
    }


@app.before_request
def ensure_db():
    excluded = {"setup", "static"}
    if request.endpoint and request.endpoint not in excluded:
        if not db_ok():
            flash("Impossible de se connecter à la base de données. Configurez la connexion.", "danger")
            return redirect(url_for("setup"))


# -- setup --

@app.route("/setup", methods=["GET", "POST"])
def setup():
    error = None
    if request.method == "POST":
        db.set_config(
            host=request.form.get("host", "localhost"),
            port=request.form.get("port", "5432"),
            dbname=request.form.get("dbname", "infoh303"),
            user=request.form.get("user", "postgres"),
            password=request.form.get("password", ""),
        )
        if db_ok():
            flash("Connexion réussie !", "success")
            return redirect(url_for("auth"))
        else:
            error = "Connexion échouée. Vérifiez les paramètres."
    current = db.DB_CONFIG
    return render_template("setup.html", current=current, error=error)


# -- authentification --

@app.route("/auth", methods=["GET", "POST"])
def auth():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    tab = request.args.get("tab", "login")

    if request.method == "POST":
        action = request.form.get("action")

        if action == "login":
            username = request.form.get("username", "").strip()
            if not username:
                flash("Nom d'utilisateur requis.", "danger")
                return redirect(url_for("auth", tab="login"))
            row = db.execute(
                "SELECT id_utilisateur, nom_utilisateur, nbr_pt, niveau FROM UTILISATEUR WHERE nom_utilisateur = %s",
                (username,), fetch="one"
            )
            if not row:
                flash("Utilisateur introuvable.", "danger")
                return redirect(url_for("auth", tab="login"))
            session["user_id"] = row["id_utilisateur"]
            session["username"] = row["nom_utilisateur"]
            flash(f"Bienvenue, {row['nom_utilisateur']} !", "success")
            return redirect(url_for("dashboard"))

        elif action == "register":
            username = request.form.get("reg_username", "").strip()
            email    = request.form.get("reg_email", "").strip()
            if not username or not email:
                flash("Tous les champs sont requis.", "danger")
                return redirect(url_for("auth", tab="register"))
            if "@" not in email or "." not in email.split("@")[-1]:
                flash("Adresse email invalide.", "danger")
                return redirect(url_for("auth", tab="register"))
            try:
                row = db.execute(
                    "INSERT INTO UTILISATEUR (nom_utilisateur, email) VALUES (%s, %s) RETURNING id_utilisateur",
                    (username, email), fetch="one"
                )
                session["user_id"] = row["id_utilisateur"]
                session["username"] = username
                flash(f"Compte créé ! Bienvenue, {username} !", "success")
                return redirect(url_for("dashboard"))
            except psycopg2.errors.UniqueViolation:
                flash("Ce nom d'utilisateur ou email existe déjà.", "danger")
                return redirect(url_for("auth", tab="register"))
            except Exception as e:
                flash(f"Erreur : {e}", "danger")
                return redirect(url_for("auth", tab="register"))

    return render_template("auth.html", tab=tab)


@app.route("/logout")
def logout():
    session.clear()
    flash("Déconnecté avec succès.", "info")
    return redirect(url_for("auth"))


# -- dashboard --

@app.route("/")
@login_required
def dashboard():
    uid = session["user_id"]

    user = db.execute(
        """SELECT u.nom_utilisateur, u.email, u.date_inscription, u.nbr_pt, u.niveau,
                  vt.titre_certif
           FROM UTILISATEUR u
           LEFT JOIN v_user_titre vt ON vt.id_utilisateur = u.id_utilisateur
           WHERE u.id_utilisateur = %s""",
        (uid,), fetch="one"
    )
    if not user:
        session.clear()
        flash("Session expirée. Reconnectez-vous.", "warning")
        return redirect(url_for("auth"))
    # tiebreak par date_inscription : plus ancienne = mieux classé
    rank = db.execute(
        """SELECT COUNT(*)+1 AS rang FROM UTILISATEUR
           WHERE nbr_pt > %s
              OR (nbr_pt = %s AND date_inscription < %s)""",
        (user["nbr_pt"], user["nbr_pt"], user["date_inscription"]),
        fetch="one"
    )
    nb_resumes = db.execute(
        "SELECT COUNT(*) AS cnt FROM RESUME WHERE id_utilisateur = %s",
        (uid,), fetch="one"
    )
    nb_evals = db.execute(
        "SELECT COUNT(*) AS cnt FROM EVALUATION WHERE id_utilisateur = %s",
        (uid,), fetch="one"
    )
    recent_tx = db.execute(
        """SELECT montant, type_transaction, date_transaction
           FROM TRANSACTION_POINTS WHERE id_utilisateur = %s
           ORDER BY date_transaction DESC LIMIT 8""",
        (uid,), fetch="all"
    )
    total_users = db.execute("SELECT COUNT(*) AS cnt FROM UTILISATEUR", fetch="one")
    active_items = db.execute(
        """SELECT oc.nom, oc.type_cosmetique
           FROM POSSEDE p
           JOIN OBJET_COSMETIQUE oc ON oc.id_objet = p.id_objet
           WHERE p.id_utilisateur = %s AND p.est_actif = TRUE""",
        (uid,), fetch="all"
    )
    titres = db.execute(
        """SELECT oc.nom
           FROM POSSEDE p
           JOIN OBJET_COSMETIQUE oc ON oc.id_objet = p.id_objet
           WHERE p.id_utilisateur = %s AND oc.type_cosmetique = 'titre'
           ORDER BY oc.id_objet""",
        (uid,), fetch="all"
    )
    active_badge = next((i for i in (active_items or []) if i["type_cosmetique"] == "badge"), None)

    return render_template("dashboard.html",
        user=user,
        rang=rank["rang"],
        nb_resumes=nb_resumes["cnt"],
        nb_evals=nb_evals["cnt"],
        recent_tx=recent_tx or [],
        total_users=total_users["cnt"],
        titres=titres or [],
        active_badge=active_badge,
    )


# -- cours --

@app.route("/courses")
@login_required
def courses():
    search = request.args.get("q", "").strip()
    if search:
        rows = db.execute(
            """SELECT c.code_cours, c.nom_cours, c.faculte, c.annee_academique,
                      COUNT(r.id_resume) AS nb_resumes
               FROM COURS c LEFT JOIN RESUME r ON r.code_cours = c.code_cours
               WHERE c.code_cours ILIKE %s OR c.nom_cours ILIKE %s OR c.faculte ILIKE %s
               GROUP BY c.code_cours ORDER BY c.code_cours""",
            (f"%{search}%", f"%{search}%", f"%{search}%"), fetch="all"
        )
    else:
        rows = db.execute(
            """SELECT c.code_cours, c.nom_cours, c.faculte, c.annee_academique,
                      COUNT(r.id_resume) AS nb_resumes
               FROM COURS c LEFT JOIN RESUME r ON r.code_cours = c.code_cours
               GROUP BY c.code_cours ORDER BY c.code_cours""",
            fetch="all"
        )
    return render_template("courses.html", courses=rows or [], search=search)


@app.route("/courses/add", methods=["POST"])
@login_required
def courses_add():
    code    = request.form.get("code_cours", "").strip().upper()
    nom     = request.form.get("nom_cours", "").strip()
    faculte = request.form.get("faculte", "").strip()
    annee   = request.form.get("annee_academique", "2025-2026").strip()
    if not code or not nom or not faculte:
        flash("Tous les champs sont requis.", "danger")
        return redirect(url_for("courses"))
    try:
        db.execute(
            "INSERT INTO COURS (code_cours, nom_cours, faculte, annee_academique) VALUES (%s, %s, %s, %s)",
            (code, nom, faculte, annee)
        )
        flash(f"Cours {code} ajouté.", "success")
    except psycopg2.errors.UniqueViolation:
        flash(f"Le cours {code} existe déjà.", "warning")
    except Exception as e:
        flash(f"Erreur : {e}", "danger")
    return redirect(url_for("courses"))


@app.route("/courses/<code>/delete", methods=["POST"])
@login_required
def courses_delete(code):
    nb = db.execute(
        "SELECT COUNT(*) AS cnt FROM RESUME WHERE code_cours = %s", (code,), fetch="one"
    )
    if nb and nb["cnt"] > 0:
        flash(f"Impossible : {nb['cnt']} résumé(s) sont liés à ce cours.", "warning")
        return redirect(url_for("courses"))
    try:
        db.execute("DELETE FROM COURS WHERE code_cours = %s", (code,))
        flash(f"Cours {code} supprimé.", "success")
    except Exception as e:
        flash(f"Erreur : {e}", "danger")
    return redirect(url_for("courses"))


# -- résumés --

@app.route("/summaries")
@login_required
def summaries():
    uid = session["user_id"]
    filter_mode = request.args.get("filter", "all")
    filter_cours = request.args.get("cours", "").strip()

    base = """SELECT r.id_resume, r.titre, r.description, r.code_cours, c.nom_cours,
                     r.date_publication, r.visibilite, r.note_moyenne,
                     u.nom_utilisateur, r.id_utilisateur,
                     COUNT(e.id_eval) AS nb_evals,
                     vt.titre_certif, vb.badge_actif
              FROM RESUME r
              JOIN COURS c ON c.code_cours = r.code_cours
              JOIN UTILISATEUR u ON u.id_utilisateur = r.id_utilisateur
              LEFT JOIN EVALUATION e ON e.id_resume = r.id_resume
              LEFT JOIN v_user_titre vt ON vt.id_utilisateur = r.id_utilisateur
              LEFT JOIN v_user_badge vb ON vb.id_utilisateur = r.id_utilisateur"""

    if filter_mode == "mine":
        where, params = "WHERE r.id_utilisateur = %s", [uid]
    else:
        where, params = "WHERE (r.visibilite = 'public' OR r.id_utilisateur = %s)", [uid]

    if filter_cours:
        where += " AND r.code_cours = %s"
        params.append(filter_cours)

    rows = db.execute(
        base + " " + where + " GROUP BY r.id_resume, c.nom_cours, u.nom_utilisateur, vt.titre_certif, vb.badge_actif ORDER BY r.date_publication DESC",
        tuple(params), fetch="all"
    )

    cours_list = db.execute("SELECT code_cours, nom_cours FROM COURS ORDER BY code_cours", fetch="all")
    return render_template("summaries.html",
        summaries=rows or [],
        cours_list=cours_list or [],
        filter_mode=filter_mode,
        filter_cours=filter_cours,
        uid=uid,
    )


@app.route("/summaries/add", methods=["POST"])
@login_required
def summaries_add():
    uid         = session["user_id"]
    titre       = request.form.get("titre", "").strip()
    description = request.form.get("description", "").strip()
    code_cours  = request.form.get("code_cours", "").strip()
    visibilite  = request.form.get("visibilite", "public")
    if not titre or not code_cours:
        flash("Titre et cours sont requis.", "danger")
        return redirect(url_for("summaries"))
    if len(titre) > 255:
        flash("Le titre ne peut pas dépasser 255 caractères.", "danger")
        return redirect(url_for("summaries"))
    if visibilite not in ("public", "privé"):
        visibilite = "public"
    try:
        with db.transaction() as conn:
            row = db.execute_in(
                conn,
                """INSERT INTO RESUME (titre, description, date_publication, version, visibilite, id_utilisateur, code_cours)
                   VALUES (%s, %s, CURRENT_DATE, 1, %s, %s, %s) RETURNING id_resume""",
                (titre, description or None, visibilite, uid, code_cours), fetch="one"
            )
            db.execute_in(
                conn,
                """INSERT INTO TRANSACTION_POINTS (montant, type_transaction, date_transaction, id_utilisateur, id_resume)
                   VALUES (%s, 'gain', CURRENT_DATE, %s, %s)""",
                (POINTS_PUBLICATION, uid, row["id_resume"])
            )
            db.execute_in(
                conn,
                "UPDATE UTILISATEUR SET nbr_pt = nbr_pt + %s WHERE id_utilisateur = %s",
                (POINTS_PUBLICATION, uid)
            )
        flash(f"Résumé publié ! +{POINTS_PUBLICATION} points.", "success")
    except Exception as e:
        flash(f"Erreur : {e}", "danger")
    return redirect(url_for("summaries"))


@app.route("/summaries/<int:rid>/edit", methods=["POST"])
@login_required
def summaries_edit(rid):
    uid = session["user_id"]
    row = db.execute("SELECT id_utilisateur FROM RESUME WHERE id_resume = %s", (rid,), fetch="one")
    if not row or row["id_utilisateur"] != uid:
        flash("Action non autorisée.", "danger")
        return redirect(url_for("summaries"))
    titre = request.form.get("titre", "").strip()
    description = request.form.get("description", "").strip()
    visibilite = request.form.get("visibilite", "public")
    if not titre:
        flash("Le titre est requis.", "danger")
        return redirect(url_for("summaries"))
    if len(titre) > 255:
        flash("Le titre ne peut pas dépasser 255 caractères.", "danger")
        return redirect(url_for("summaries"))
    if visibilite not in ("public", "privé"):
        visibilite = "public"
    db.execute(
        "UPDATE RESUME SET titre = %s, description = %s, visibilite = %s WHERE id_resume = %s",
        (titre, description or None, visibilite, rid)
    )
    flash("Résumé modifié.", "success")
    return redirect(url_for("summaries"))


@app.route("/summaries/<int:rid>/delete", methods=["POST"])
@login_required
def summaries_delete(rid):
    uid = session["user_id"]
    row = db.execute("SELECT id_utilisateur FROM RESUME WHERE id_resume = %s", (rid,), fetch="one")
    if not row or row["id_utilisateur"] != uid:
        flash("Action non autorisée.", "danger")
        return redirect(url_for("summaries"))
    # On rend les points avant le DELETE : le CASCADE va effacer les transactions,
    # donc plus moyen de les retrouver après. GREATEST(0,…) au cas où l'user
    # aurait déjà dépensé ces points en boutique.
    try:
        with db.transaction() as conn:
            affected = db.execute_in(
                conn,
                """SELECT id_utilisateur,
                          SUM(CASE WHEN type_transaction = 'gain' THEN montant ELSE -montant END) AS delta
                   FROM TRANSACTION_POINTS
                   WHERE id_resume = %s
                      OR id_eval IN (SELECT id_eval FROM EVALUATION WHERE id_resume = %s)
                   GROUP BY id_utilisateur""",
                (rid, rid), fetch="all"
            ) or []
            for r in affected:
                db.execute_in(
                    conn,
                    "UPDATE UTILISATEUR SET nbr_pt = GREATEST(0, nbr_pt - %s) WHERE id_utilisateur = %s",
                    (r["delta"], r["id_utilisateur"])
                )
            db.execute_in(conn, "DELETE FROM RESUME WHERE id_resume = %s", (rid,))
        flash("Résumé supprimé.", "success")
    except Exception as e:
        flash(f"Erreur : {e}", "danger")
    return redirect(url_for("summaries"))


@app.route("/summaries/<int:rid>")
@login_required
def summary_detail(rid):
    uid = session["user_id"]
    resume = db.execute(
        """SELECT r.id_resume, r.titre, r.description, r.date_publication, r.visibilite,
                  r.note_moyenne, r.code_cours, c.nom_cours, u.nom_utilisateur,
                  r.id_utilisateur, vt.titre_certif, vb.badge_actif
           FROM RESUME r
           JOIN COURS c ON c.code_cours = r.code_cours
           JOIN UTILISATEUR u ON u.id_utilisateur = r.id_utilisateur
           LEFT JOIN v_user_titre vt ON vt.id_utilisateur = r.id_utilisateur
           LEFT JOIN v_user_badge vb ON vb.id_utilisateur = r.id_utilisateur
           WHERE r.id_resume = %s
             AND (r.visibilite = 'public' OR r.id_utilisateur = %s)""",
        (rid, uid), fetch="one"
    )
    if not resume:
        flash("Résumé introuvable.", "danger")
        return redirect(url_for("summaries"))
    evals = db.execute(
        """SELECT e.note, e.commentaire, e.date_eval, u.nom_utilisateur,
                  vt.titre_certif, vb.badge_actif
           FROM EVALUATION e
           JOIN UTILISATEUR u ON u.id_utilisateur = e.id_utilisateur
           LEFT JOIN v_user_titre vt ON vt.id_utilisateur = e.id_utilisateur
           LEFT JOIN v_user_badge vb ON vb.id_utilisateur = e.id_utilisateur
           WHERE e.id_resume = %s
           ORDER BY e.date_eval DESC""",
        (rid,), fetch="all"
    )
    already_evaluated = db.execute(
        "SELECT 1 FROM EVALUATION WHERE id_utilisateur = %s AND id_resume = %s",
        (uid, rid), fetch="one"
    )
    return render_template("summary_detail.html",
        resume=resume, evals=evals or [],
        already_evaluated=bool(already_evaluated),
        is_owner=(resume["id_utilisateur"] == uid)
    )


@app.route("/summaries/<int:rid>/evaluate", methods=["POST"])
@login_required
def summaries_evaluate(rid):
    uid         = session["user_id"]
    note_raw    = request.form.get("note")
    commentaire = request.form.get("commentaire", "").strip()

    if not note_raw:
        flash("Note requise.", "danger")
        return redirect(url_for("summary_detail", rid=rid))
    try:
        note = int(note_raw)
        if not (1 <= note <= 5):
            raise ValueError
    except ValueError:
        flash("Note invalide (doit être entre 1 et 5).", "danger")
        return redirect(url_for("summary_detail", rid=rid))

    owner = db.execute("SELECT id_utilisateur FROM RESUME WHERE id_resume = %s", (rid,), fetch="one")
    if not owner:
        flash("Résumé introuvable.", "danger")
        return redirect(url_for("summaries"))
    if owner["id_utilisateur"] == uid:
        flash("Vous ne pouvez pas évaluer votre propre résumé.", "warning")
        return redirect(url_for("summary_detail", rid=rid))
    try:
        with db.transaction() as conn:
            row = db.execute_in(
                conn,
                """INSERT INTO EVALUATION (note, commentaire, date_eval, id_utilisateur, id_resume)
                   VALUES (%s, %s, CURRENT_DATE, %s, %s) RETURNING id_eval""",
                (note, commentaire or None, uid, rid), fetch="one"
            )
            db.execute_in(
                conn,
                """INSERT INTO TRANSACTION_POINTS (montant, type_transaction, date_transaction, id_utilisateur, id_eval)
                   VALUES (%s, 'gain', CURRENT_DATE, %s, %s)""",
                (POINTS_EVALUATION, uid, row["id_eval"])
            )
            db.execute_in(
                conn,
                "UPDATE UTILISATEUR SET nbr_pt = nbr_pt + %s WHERE id_utilisateur = %s",
                (POINTS_EVALUATION, uid)
            )
            db.execute_in(
                conn,
                """INSERT INTO TRANSACTION_POINTS (montant, type_transaction, date_transaction, id_utilisateur, id_eval)
                   VALUES (%s, 'gain', CURRENT_DATE, %s, %s)""",
                (POINTS_EVALUATION, owner["id_utilisateur"], row["id_eval"])
            )
            db.execute_in(
                conn,
                "UPDATE UTILISATEUR SET nbr_pt = nbr_pt + %s WHERE id_utilisateur = %s",
                (POINTS_EVALUATION, owner["id_utilisateur"])
            )
        flash(f"Évaluation soumise ! +{POINTS_EVALUATION} points.", "success")
    except psycopg2.errors.UniqueViolation:
        flash("Vous avez déjà évalué ce résumé.", "warning")
    except Exception as e:
        flash(f"Erreur : {e}", "danger")
    return redirect(url_for("summary_detail", rid=rid))


# -- points & historique --

@app.route("/points")
@login_required
def points():
    uid = session["user_id"]
    user = db.execute(
        "SELECT nbr_pt, niveau FROM UTILISATEUR WHERE id_utilisateur = %s",
        (uid,), fetch="one"
    )
    if not user:
        session.clear()
        return redirect(url_for("auth"))
    transactions = db.execute(
        """SELECT t.montant, t.type_transaction, t.date_transaction,
                  r.titre AS resume_titre, oc.nom AS objet_nom,
                  er.titre AS eval_resume_titre
           FROM TRANSACTION_POINTS t
           LEFT JOIN RESUME r ON r.id_resume = t.id_resume
           LEFT JOIN OBJET_COSMETIQUE oc ON oc.id_objet = t.id_objet
           LEFT JOIN EVALUATION e ON e.id_eval = t.id_eval
           LEFT JOIN RESUME er ON er.id_resume = e.id_resume
           WHERE t.id_utilisateur = %s
           ORDER BY t.date_transaction DESC""",
        (uid,), fetch="all"
    )
    total_gagnes = db.execute(
        "SELECT COALESCE(SUM(montant), 0) AS total FROM TRANSACTION_POINTS WHERE id_utilisateur = %s AND type_transaction = 'gain'",
        (uid,), fetch="one"
    )
    total_depenses = db.execute(
        "SELECT COALESCE(SUM(montant), 0) AS total FROM TRANSACTION_POINTS WHERE id_utilisateur = %s AND type_transaction = 'dépense'",
        (uid,), fetch="one"
    )
    return render_template("points.html",
        user=user,
        transactions=transactions or [],
        total_gagnes=total_gagnes["total"],
        total_depenses=total_depenses["total"],
    )


# -- boutique --

@app.route("/shop")
@login_required
def shop():
    uid = session["user_id"]
    user = db.execute(
        "SELECT nbr_pt FROM UTILISATEUR WHERE id_utilisateur = %s", (uid,), fetch="one"
    )
    if not user:
        session.clear()
        return redirect(url_for("auth"))
    items = db.execute(
        """SELECT oc.id_objet, oc.nom, oc.description, oc.prix_points, oc.type_cosmetique,
                  oc.niveau_requis,
                  p.id_utilisateur IS NOT NULL AS possede,
                  p.est_actif
           FROM OBJET_COSMETIQUE oc
           LEFT JOIN POSSEDE p ON p.id_objet = oc.id_objet AND p.id_utilisateur = %s
           ORDER BY oc.type_cosmetique, oc.prix_points""",
        (uid,), fetch="all"
    )
    titre_niveaux = {it["id_objet"]: it["niveau_requis"] for it in (items or []) if it["niveau_requis"] is not None}
    return render_template("shop.html", items=items or [], user=user, titre_niveaux=titre_niveaux)


@app.route("/shop/<int:iid>/buy", methods=["POST"])
@login_required
def shop_buy(iid):
    uid = session["user_id"]
    item = db.execute(
        "SELECT id_objet, nom, prix_points, type_cosmetique FROM OBJET_COSMETIQUE WHERE id_objet = %s", (iid,), fetch="one"
    )
    if not item:
        flash("Objet introuvable.", "danger")
        return redirect(url_for("shop"))
    if item["type_cosmetique"] == "titre":
        flash("Les titres sont des récompenses de niveau et ne peuvent pas être achetés.", "warning")
        return redirect(url_for("shop"))
    user = db.execute(
        "SELECT nbr_pt FROM UTILISATEUR WHERE id_utilisateur = %s", (uid,), fetch="one"
    )
    price = item["prix_points"]
    if user["nbr_pt"] < price:
        flash("Points insuffisants.", "warning")
        return redirect(url_for("shop"))
    try:
        with db.transaction() as conn:
            db.execute_in(
                conn,
                "INSERT INTO POSSEDE (id_utilisateur, id_objet, date_achat, est_actif) VALUES (%s, %s, CURRENT_DATE, FALSE)",
                (uid, iid)
            )
            if price > 0:
                db.execute_in(
                    conn,
                    """INSERT INTO TRANSACTION_POINTS (montant, type_transaction, date_transaction, id_utilisateur, id_objet)
                       VALUES (%s, 'dépense', CURRENT_DATE, %s, %s)""",
                    (price, uid, iid)
                )
                db.execute_in(
                    conn,
                    "UPDATE UTILISATEUR SET nbr_pt = nbr_pt - %s WHERE id_utilisateur = %s",
                    (price, uid)
                )
        flash(f"'{item['nom']}' acheté ! -{price} points.", "success")
    except psycopg2.errors.UniqueViolation:
        flash("Vous possédez déjà cet objet.", "warning")
    except Exception as e:
        flash(f"Erreur : {e}", "danger")
    return redirect(url_for("shop"))


@app.route("/shop/<int:iid>/activate", methods=["POST"])
@login_required
def shop_activate(iid):
    uid = session["user_id"]
    type_obj = db.execute(
        """SELECT oc.type_cosmetique FROM OBJET_COSMETIQUE oc
           JOIN POSSEDE p ON p.id_objet = oc.id_objet
           WHERE oc.id_objet = %s AND p.id_utilisateur = %s""",
        (iid, uid), fetch="one"
    )
    if not type_obj:
        flash("Objet introuvable ou non possédé.", "danger")
        return redirect(url_for("shop"))
    if type_obj["type_cosmetique"] == "titre":
        flash("Les titres sont toujours visibles, pas besoin de les activer.", "info")
        return redirect(url_for("shop"))
    db.execute(
        """UPDATE POSSEDE p SET est_actif = FALSE
           FROM OBJET_COSMETIQUE oc
           WHERE p.id_objet = oc.id_objet
             AND p.id_utilisateur = %s
             AND oc.type_cosmetique = %s""",
        (uid, type_obj["type_cosmetique"])
    )
    db.execute(
        "UPDATE POSSEDE SET est_actif = TRUE WHERE id_utilisateur = %s AND id_objet = %s",
        (uid, iid)
    )
    flash("Objet activé !", "success")
    return redirect(url_for("shop"))


@app.route("/shop/<int:iid>/deactivate", methods=["POST"])
@login_required
def shop_deactivate(iid):
    uid = session["user_id"]
    db.execute(
        "UPDATE POSSEDE SET est_actif = FALSE WHERE id_utilisateur = %s AND id_objet = %s",
        (uid, iid)
    )
    flash("Objet désactivé.", "info")
    return redirect(url_for("shop"))


# -- classement --

def _refresh_leaderboard_snapshot(periode: str):
    # snapshot uniquement si on n'en a pas encore pour ce mois/cette année
    trunc_unit = "month" if periode == "mensuel" else "year"
    already = db.execute(
        f"""SELECT 1 FROM LEADERBOARD
            WHERE type_periode = %s
              AND date_classement = date_trunc('{trunc_unit}', CURRENT_DATE)::date
            LIMIT 1""",
        (periode,), fetch="one"
    )
    if already:
        return
    # On fige nbr_pt dans le snapshot, sinon l'historique afficherait
    # le solde courant et non celui du moment du classement.
    db.execute(
        f"""INSERT INTO LEADERBOARD (rang, nbr_pt, type_periode, date_classement, id_utilisateur)
            SELECT ROW_NUMBER() OVER (ORDER BY nbr_pt DESC, date_inscription ASC),
                   nbr_pt,
                   %s,
                   date_trunc('{trunc_unit}', CURRENT_DATE)::date,
                   id_utilisateur
            FROM UTILISATEUR
            ON CONFLICT (id_utilisateur, type_periode, date_classement) DO NOTHING""",
        (periode,)
    )


@app.route("/leaderboard")
@login_required
def leaderboard():
    uid = session["user_id"]
    _refresh_leaderboard_snapshot("mensuel")
    rows = db.execute(
        """SELECT u.id_utilisateur, u.nom_utilisateur, u.nbr_pt, u.niveau,
                  COUNT(DISTINCT r.id_resume) AS nb_resumes,
                  COUNT(DISTINCT e.id_eval)   AS nb_evals,
                  vt.titre_certif, vb.badge_actif
           FROM UTILISATEUR u
           LEFT JOIN RESUME r ON r.id_utilisateur = u.id_utilisateur
           LEFT JOIN EVALUATION e ON e.id_utilisateur = u.id_utilisateur
           LEFT JOIN v_user_titre vt ON vt.id_utilisateur = u.id_utilisateur
           LEFT JOIN v_user_badge vb ON vb.id_utilisateur = u.id_utilisateur
           GROUP BY u.id_utilisateur, u.nom_utilisateur, u.nbr_pt, u.niveau, vt.titre_certif, vb.badge_actif
           ORDER BY u.nbr_pt DESC, u.date_inscription ASC""",
        fetch="all"
    )
    my_rank = db.execute(
        """WITH me AS (SELECT nbr_pt, date_inscription FROM UTILISATEUR WHERE id_utilisateur = %s)
           SELECT COUNT(*)+1 AS rang FROM UTILISATEUR, me
           WHERE UTILISATEUR.nbr_pt > me.nbr_pt
              OR (UTILISATEUR.nbr_pt = me.nbr_pt AND UTILISATEUR.date_inscription < me.date_inscription)""",
        (uid,), fetch="one"
    )
    # On lit le nbr_pt depuis LEADERBOARD (figé au snapshot), pas depuis UTILISATEUR
    history = db.execute(
        """SELECT l.rang, l.date_classement, u.nom_utilisateur, l.nbr_pt
           FROM LEADERBOARD l
           JOIN UTILISATEUR u ON u.id_utilisateur = l.id_utilisateur
           WHERE l.type_periode = 'mensuel'
             AND l.date_classement = date_trunc('month', CURRENT_DATE - INTERVAL '1 month')::date
           ORDER BY l.rang
           LIMIT 5""",
        fetch="all"
    )
    history_date = db.execute(
        """SELECT TO_CHAR(date_classement, 'Month YYYY') AS mois
           FROM LEADERBOARD WHERE type_periode = 'mensuel'
             AND date_classement = date_trunc('month', CURRENT_DATE - INTERVAL '1 month')::date
           LIMIT 1""",
        fetch="one"
    )
    return render_template("leaderboard.html",
        rows=rows or [],
        my_rank=my_rank["rang"] if my_rank else 1,
        uid=uid,
        history=history or [],
        history_date=history_date["mois"].strip() if history_date else None
    )


# -- requêtes analytiques --

@app.route("/queries")
@login_required
def queries():
    return render_template("queries.html")


@app.route("/api/query/<int:n>")
@login_required
def api_query(n):
    try:
        result = _run_query(n)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def _run_query(n):
    if n == 1:
        # tiebreak par date_inscription en cas d'égalité de points
        rows = db.execute(
            """SELECT nom_utilisateur, nbr_pt
               FROM UTILISATEUR
               ORDER BY nbr_pt DESC, date_inscription ASC
               LIMIT 10""",
            fetch="all"
        )
        return [dict(r) for r in rows] if rows else []

    elif n == 2:
        rows = db.execute(
            """SELECT u.nom_utilisateur,
                      COUNT(DISTINCT r.code_cours) AS nb_cours,
                      COUNT(r.id_resume)           AS nb_resumes
               FROM UTILISATEUR u, RESUME r
               WHERE r.id_utilisateur = u.id_utilisateur
               GROUP BY u.id_utilisateur, u.nom_utilisateur
               HAVING COUNT(DISTINCT r.code_cours) >= 3
               ORDER BY nb_cours DESC, u.nom_utilisateur""",
            fetch="all"
        )
        return [dict(r) for r in rows] if rows else []

    elif n == 3:
        rows = db.execute(
            """SELECT c.code_cours, c.nom_cours, COUNT(r.id_resume) AS total_resumes
               FROM COURS c, RESUME r
               WHERE c.code_cours = r.code_cours
               GROUP BY c.code_cours, c.nom_cours
               ORDER BY total_resumes DESC LIMIT 1""",
            fetch="all"
        )
        return [dict(r) for r in rows] if rows else []

    elif n == 4:
        # note_moyenne est mis à jour par trigger, on peut donc filtrer directement dessus
        rows = db.execute(
            """SELECT r.code_cours, r.titre, r.note_moyenne
               FROM RESUME r
               WHERE r.note_moyenne IS NOT NULL
                 AND r.note_moyenne = (
                     SELECT MAX(r2.note_moyenne)
                     FROM RESUME r2
                     WHERE r2.code_cours = r.code_cours
                 )
               ORDER BY r.code_cours""",
            fetch="all"
        )
        return [dict(r) for r in rows] if rows else []

    elif n == 5:
        rows = db.execute(
            """SELECT nom_utilisateur, email, date_inscription::text
               FROM UTILISATEUR
               WHERE id_utilisateur NOT IN (
                   SELECT id_utilisateur FROM RESUME
               )
               ORDER BY nom_utilisateur""",
            fetch="all"
        )
        return [dict(r) for r in rows] if rows else []

    elif n == 6:
        rows = db.execute(
            """SELECT oc.nom, oc.type_cosmetique, oc.prix_points,
                      COUNT(p.id_utilisateur) AS nb_achats
               FROM OBJET_COSMETIQUE oc, POSSEDE p
               WHERE p.id_objet = oc.id_objet
                 AND oc.type_cosmetique != 'titre'
               GROUP BY oc.id_objet, oc.nom, oc.type_cosmetique, oc.prix_points
               ORDER BY nb_achats DESC
               LIMIT 1""",
            fetch="all"
        )
        return [dict(r) for r in rows] if rows else []

    elif n == 7:
        rows = db.execute(
            """SELECT u.nom_utilisateur, u.nbr_pt AS solde_actuel,
                      SUM(CASE WHEN t.type_transaction = 'gain'    THEN t.montant ELSE 0 END) AS total_gain,
                      SUM(CASE WHEN t.type_transaction != 'gain'   THEN t.montant ELSE 0 END) AS total_depense
               FROM UTILISATEUR u, TRANSACTION_POINTS t
               WHERE t.id_utilisateur = u.id_utilisateur
               GROUP BY u.id_utilisateur, u.nom_utilisateur, u.nbr_pt
               HAVING SUM(CASE WHEN t.type_transaction != 'gain' THEN t.montant ELSE 0 END) >
                      (u.nbr_pt + SUM(CASE WHEN t.type_transaction = 'gain' THEN t.montant ELSE 0 END))
               ORDER BY u.nom_utilisateur""",
            fetch="all"
        )
        return [dict(r) for r in rows] if rows else []

    elif n == 8:
        # NULLIF évite div/0 si la table est vide, ::numeric force la division décimale
        row = db.execute(
            """SELECT ROUND((SELECT COUNT(*) FROM RESUME)::numeric
                          / NULLIF((SELECT COUNT(*) FROM UTILISATEUR), 0), 2) AS moyenne""",
            fetch="one"
        )
        return [{"moyenne": float(row["moyenne"]) if row and row["moyenne"] else 0}]

    return []
