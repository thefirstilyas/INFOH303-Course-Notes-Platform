-- ============================================================
-- Script DDL – INFOH303 Plateforme de Partage de Résumés
-- PostgreSQL
-- ============================================================

-- Suppression dans l'ordre inverse des dépendances
DROP TABLE IF EXISTS LEADERBOARD        CASCADE;
DROP TABLE IF EXISTS POSSEDE            CASCADE;
DROP TABLE IF EXISTS TRANSACTION_POINTS CASCADE;
DROP TABLE IF EXISTS EVALUATION         CASCADE;
DROP TABLE IF EXISTS RESUME             CASCADE;
DROP TABLE IF EXISTS COURS              CASCADE;
DROP TABLE IF EXISTS OBJET_COSMETIQUE   CASCADE;
DROP TABLE IF EXISTS UTILISATEUR        CASCADE;

DROP FUNCTION IF EXISTS update_note_moyenne()    CASCADE;
DROP FUNCTION IF EXISTS check_auto_evaluation()  CASCADE;
DROP FUNCTION IF EXISTS check_actif_unique()     CASCADE;
DROP FUNCTION IF EXISTS fn_update_niveau()       CASCADE;
DROP FUNCTION IF EXISTS fn_recalc_niveau()       CASCADE;
DROP FUNCTION IF EXISTS check_eval_date()        CASCADE;
DROP FUNCTION IF EXISTS check_transaction_date() CASCADE;
DROP FUNCTION IF EXISTS check_achat_date()       CASCADE;

-- ────────────────────────────────────────
-- UTILISATEUR
-- ────────────────────────────────────────
CREATE TABLE UTILISATEUR (
    id_utilisateur  SERIAL       PRIMARY KEY,
    nom_utilisateur VARCHAR(100) NOT NULL UNIQUE,
    email           VARCHAR(255) NOT NULL UNIQUE,
    date_inscription DATE        NOT NULL DEFAULT CURRENT_DATE,
    nbr_pt          INTEGER      NOT NULL DEFAULT 0  CHECK (nbr_pt >= 0),
    niveau          INTEGER      NOT NULL DEFAULT 1  CHECK (niveau >= 1)
);

-- ────────────────────────────────────────
-- COURS
-- ────────────────────────────────────────
CREATE TABLE COURS (
    code_cours       VARCHAR(20)  PRIMARY KEY,
    nom_cours        VARCHAR(255) NOT NULL,
    faculte          VARCHAR(100) NOT NULL,
    annee_academique VARCHAR(10)  NOT NULL
);

-- ────────────────────────────────────────
-- OBJET_COSMETIQUE
-- ────────────────────────────────────────
CREATE TABLE OBJET_COSMETIQUE (
    id_objet        SERIAL      PRIMARY KEY,
    nom             VARCHAR(100) NOT NULL UNIQUE,
    description     TEXT,
    prix_points     INTEGER      NOT NULL DEFAULT 0 CHECK (prix_points >= 0),
    type_cosmetique VARCHAR(20)  NOT NULL CHECK (type_cosmetique IN ('badge', 'titre', 'theme')),
    -- niveau_requis : NULL pour badges/thèmes, 2 à 9 pour les titres
    niveau_requis   INTEGER      CHECK (niveau_requis BETWEEN 2 AND 9)
);

-- ────────────────────────────────────────
-- RESUME
-- ────────────────────────────────────────
CREATE TABLE RESUME (
    id_resume        SERIAL       PRIMARY KEY,
    titre            VARCHAR(255) NOT NULL,
    description      TEXT,
    date_publication DATE         NOT NULL DEFAULT CURRENT_DATE,
    version          INTEGER      NOT NULL DEFAULT 1 CHECK (version >= 1),
    visibilite       VARCHAR(10)  NOT NULL CHECK (visibilite IN ('public', 'privé')),
    note_moyenne     NUMERIC(3,2),
    id_utilisateur   INTEGER      NOT NULL REFERENCES UTILISATEUR(id_utilisateur) ON DELETE CASCADE,
    code_cours       VARCHAR(20)  NOT NULL REFERENCES COURS(code_cours)           ON DELETE CASCADE
);

-- ────────────────────────────────────────
-- EVALUATION
-- ────────────────────────────────────────
CREATE TABLE EVALUATION (
    id_eval        SERIAL  PRIMARY KEY,
    note           INTEGER NOT NULL CHECK (note BETWEEN 1 AND 5),
    commentaire    TEXT,
    date_eval      DATE    NOT NULL DEFAULT CURRENT_DATE,
    id_utilisateur INTEGER NOT NULL REFERENCES UTILISATEUR(id_utilisateur) ON DELETE CASCADE,
    id_resume      INTEGER NOT NULL REFERENCES RESUME(id_resume)           ON DELETE CASCADE,
    UNIQUE (id_utilisateur, id_resume)
);

-- ────────────────────────────────────────
-- TRANSACTION_POINTS
-- Exactement 1 parmi id_eval, id_resume, id_objet doit être non NULL
-- ────────────────────────────────────────
CREATE TABLE TRANSACTION_POINTS (
    id_transaction   SERIAL      PRIMARY KEY,
    montant          INTEGER     NOT NULL CHECK (montant > 0),
    type_transaction VARCHAR(10) NOT NULL CHECK (type_transaction IN ('gain', 'dépense')),
    date_transaction TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    id_utilisateur   INTEGER     NOT NULL REFERENCES UTILISATEUR(id_utilisateur)    ON DELETE CASCADE,
    id_eval          INTEGER              REFERENCES EVALUATION(id_eval)            ON DELETE CASCADE,
    id_resume        INTEGER              REFERENCES RESUME(id_resume)              ON DELETE CASCADE,
    id_objet         INTEGER              REFERENCES OBJET_COSMETIQUE(id_objet)     ON DELETE CASCADE,
    CHECK (
        (CASE WHEN id_eval   IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN id_resume IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN id_objet  IS NOT NULL THEN 1 ELSE 0 END) = 1
    )
);

-- ────────────────────────────────────────
-- POSSEDE
-- ────────────────────────────────────────
CREATE TABLE POSSEDE (
    id_utilisateur INTEGER NOT NULL REFERENCES UTILISATEUR(id_utilisateur)  ON DELETE CASCADE,
    id_objet       INTEGER NOT NULL REFERENCES OBJET_COSMETIQUE(id_objet)   ON DELETE CASCADE,
    date_achat     DATE    NOT NULL DEFAULT CURRENT_DATE,
    est_actif      BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (id_utilisateur, id_objet)
);

-- ────────────────────────────────────────
-- LEADERBOARD
-- ────────────────────────────────────────
CREATE TABLE LEADERBOARD (
    id_classement   SERIAL      PRIMARY KEY,
    rang            INTEGER     NOT NULL,
    nbr_pt          INTEGER     NOT NULL CHECK (nbr_pt >= 0),
    type_periode    VARCHAR(10) NOT NULL CHECK (type_periode IN ('mensuel', 'annuel')),
    date_classement DATE        NOT NULL DEFAULT CURRENT_DATE,
    id_utilisateur  INTEGER     NOT NULL REFERENCES UTILISATEUR(id_utilisateur) ON DELETE CASCADE,
    UNIQUE (id_utilisateur, type_periode, date_classement)
);

-- ────────────────────────────────────────
-- INDEX
-- ────────────────────────────────────────
CREATE INDEX idx_resume_utilisateur  ON RESUME(id_utilisateur);
CREATE INDEX idx_resume_cours        ON RESUME(code_cours);
CREATE INDEX idx_evaluation_resume   ON EVALUATION(id_resume);
CREATE INDEX idx_evaluation_user     ON EVALUATION(id_utilisateur);
CREATE INDEX idx_transaction_user    ON TRANSACTION_POINTS(id_utilisateur);
CREATE INDEX idx_transaction_date    ON TRANSACTION_POINTS(date_transaction);
CREATE INDEX idx_possede_user        ON POSSEDE(id_utilisateur);
CREATE INDEX idx_leaderboard_user    ON LEADERBOARD(id_utilisateur);

-- ────────────────────────────────────────
-- VUES : titre et badge actif par utilisateur
-- ────────────────────────────────────────
CREATE OR REPLACE VIEW v_user_badge AS
SELECT p.id_utilisateur, oc.nom AS badge_actif
FROM POSSEDE p
JOIN OBJET_COSMETIQUE oc ON oc.id_objet = p.id_objet
WHERE oc.type_cosmetique = 'badge' AND p.est_actif = TRUE;

-- Pour chaque utilisateur, le titre le plus prestigieux qu'il possède
CREATE OR REPLACE VIEW v_user_titre AS
SELECT DISTINCT ON (p.id_utilisateur)
    p.id_utilisateur,
    oc.nom AS titre_certif
FROM POSSEDE p
JOIN OBJET_COSMETIQUE oc ON oc.id_objet = p.id_objet
WHERE oc.type_cosmetique = 'titre'
ORDER BY p.id_utilisateur, oc.niveau_requis DESC NULLS LAST;

-- ────────────────────────────────────────
-- TRIGGER 1 : mise à jour automatique de note_moyenne
-- ────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_note_moyenne()
RETURNS TRIGGER AS $$
DECLARE
    v_id_resume INTEGER;
BEGIN
    v_id_resume := CASE WHEN TG_OP = 'DELETE' THEN OLD.id_resume ELSE NEW.id_resume END;
    UPDATE RESUME
    SET note_moyenne = (
        SELECT AVG(note) FROM EVALUATION WHERE id_resume = v_id_resume
    )
    WHERE id_resume = v_id_resume;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_note_moyenne
AFTER INSERT OR UPDATE OR DELETE ON EVALUATION
FOR EACH ROW EXECUTE FUNCTION update_note_moyenne();

-- ────────────────────────────────────────
-- TRIGGER 2 : interdiction d'auto-évaluation
-- ────────────────────────────────────────
CREATE OR REPLACE FUNCTION check_auto_evaluation()
RETURNS TRIGGER AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM RESUME
        WHERE id_resume = NEW.id_resume
          AND id_utilisateur = NEW.id_utilisateur
    ) THEN
        RAISE EXCEPTION 'Interdit : un utilisateur ne peut pas évaluer son propre résumé.';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_auto_evaluation
BEFORE INSERT OR UPDATE ON EVALUATION
FOR EACH ROW EXECUTE FUNCTION check_auto_evaluation();

-- ────────────────────────────────────────
-- TRIGGER 3 : max 1 badge actif par utilisateur
-- (les titres sont permanents et ne passent jamais par est_actif)
-- ────────────────────────────────────────
CREATE OR REPLACE FUNCTION check_actif_unique()
RETURNS TRIGGER AS $$
DECLARE
    v_type VARCHAR(20);
BEGIN
    IF NEW.est_actif = TRUE THEN
        SELECT type_cosmetique INTO v_type
        FROM OBJET_COSMETIQUE
        WHERE id_objet = NEW.id_objet;

        IF v_type = 'badge' THEN
            UPDATE POSSEDE p
            SET est_actif = FALSE
            FROM OBJET_COSMETIQUE oc
            WHERE p.id_objet = oc.id_objet
              AND p.id_utilisateur = NEW.id_utilisateur
              AND oc.type_cosmetique = v_type
              AND NOT (p.id_utilisateur = NEW.id_utilisateur AND p.id_objet = NEW.id_objet);
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_actif_unique
BEFORE INSERT OR UPDATE ON POSSEDE
FOR EACH ROW EXECUTE FUNCTION check_actif_unique();

-- ────────────────────────────────────────
-- TRIGGER 4 : niveau basé sur nb_publications × note_moyenne
--             + attribution automatique des titres par palier
-- score = COUNT(résumés) × AVG(note_moyenne)
-- Seuils : ≥1→2, ≥3→3, ≥6→4, ≥10→5, ≥15→6, ≥22→7, ≥32→8, ≥45→9
-- ────────────────────────────────────────
CREATE OR REPLACE FUNCTION fn_recalc_niveau()
RETURNS TRIGGER AS $$
DECLARE
    v_uid      INTEGER;
    v_score    NUMERIC;
    new_niveau INTEGER;
    old_niveau INTEGER;
    lvl        INTEGER;
    reward_id  INTEGER;
BEGIN
    v_uid := CASE WHEN TG_OP = 'DELETE' THEN OLD.id_utilisateur ELSE NEW.id_utilisateur END;

    SELECT COUNT(*) * COALESCE(AVG(note_moyenne), 0)
    INTO v_score
    FROM RESUME
    WHERE id_utilisateur = v_uid;

    new_niveau := CASE
        WHEN v_score >= 45 THEN 9
        WHEN v_score >= 32 THEN 8
        WHEN v_score >= 22 THEN 7
        WHEN v_score >= 15 THEN 6
        WHEN v_score >= 10 THEN 5
        WHEN v_score >= 6  THEN 4
        WHEN v_score >= 3  THEN 3
        WHEN v_score >= 1  THEN 2
        ELSE 1
    END;

    SELECT niveau INTO old_niveau FROM UTILISATEUR WHERE id_utilisateur = v_uid;

    IF new_niveau > old_niveau THEN
        -- Attribuer un titre pour chaque palier franchi
        FOR lvl IN (old_niveau + 1)..new_niveau LOOP
            SELECT id_objet INTO reward_id
            FROM OBJET_COSMETIQUE
            WHERE niveau_requis = lvl AND type_cosmetique = 'titre'
            LIMIT 1;
            IF reward_id IS NOT NULL THEN
                INSERT INTO POSSEDE (id_utilisateur, id_objet, date_achat, est_actif)
                VALUES (v_uid, reward_id, CURRENT_DATE, FALSE)
                ON CONFLICT (id_utilisateur, id_objet) DO NOTHING;
            END IF;
        END LOOP;
    END IF;

    UPDATE UTILISATEUR SET niveau = new_niveau WHERE id_utilisateur = v_uid;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Déclenché par ajout/suppression de résumé
CREATE TRIGGER trg_niveau_resume
AFTER INSERT OR DELETE ON RESUME
FOR EACH ROW EXECUTE FUNCTION fn_recalc_niveau();

-- Déclenché par changement de note moyenne (mis à jour par trg_note_moyenne)
CREATE TRIGGER trg_niveau_note
AFTER UPDATE OF note_moyenne ON RESUME
FOR EACH ROW EXECUTE FUNCTION fn_recalc_niveau();

-- ────────────────────────────────────────
-- TRIGGER 6 : date_eval >= date_publication du résumé évalué
-- ────────────────────────────────────────
CREATE OR REPLACE FUNCTION check_eval_date()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.date_eval < (SELECT date_publication FROM RESUME WHERE id_resume = NEW.id_resume) THEN
        RAISE EXCEPTION 'date_eval (%) antérieure à date_publication du résumé (%)',
            NEW.date_eval,
            (SELECT date_publication FROM RESUME WHERE id_resume = NEW.id_resume);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_eval_date
BEFORE INSERT ON EVALUATION
FOR EACH ROW EXECUTE FUNCTION check_eval_date();

-- ────────────────────────────────────────
-- TRIGGER 7 : date_transaction >= date_inscription de l'utilisateur
-- ────────────────────────────────────────
CREATE OR REPLACE FUNCTION check_transaction_date()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.date_transaction::date < (SELECT date_inscription FROM UTILISATEUR WHERE id_utilisateur = NEW.id_utilisateur) THEN
        RAISE EXCEPTION 'date_transaction (%) antérieure à date_inscription de l''utilisateur (%)',
            NEW.date_transaction::date,
            (SELECT date_inscription FROM UTILISATEUR WHERE id_utilisateur = NEW.id_utilisateur);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_transaction_date
BEFORE INSERT ON TRANSACTION_POINTS
FOR EACH ROW EXECUTE FUNCTION check_transaction_date();

-- ────────────────────────────────────────
-- TRIGGER 8 : date_achat >= date_inscription de l'utilisateur
-- ────────────────────────────────────────
CREATE OR REPLACE FUNCTION check_achat_date()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.date_achat < (SELECT date_inscription FROM UTILISATEUR WHERE id_utilisateur = NEW.id_utilisateur) THEN
        RAISE EXCEPTION 'date_achat (%) antérieure à date_inscription de l''utilisateur (%)',
            NEW.date_achat,
            (SELECT date_inscription FROM UTILISATEUR WHERE id_utilisateur = NEW.id_utilisateur);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_achat_date
BEFORE INSERT ON POSSEDE
FOR EACH ROW EXECUTE FUNCTION check_achat_date();
