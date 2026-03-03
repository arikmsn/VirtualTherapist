#!/usr/bin/env python3
"""
Maintenance script: delete a therapist and ALL related data by email.

Usage (from project root, with the same environment as the running app):
    python scripts/delete_therapist.py arik@chimu.io

The script is idempotent — prints a message and exits cleanly if the
email is not found.  Uses raw SQL (no ORM cascade) so it works reliably
regardless of which migrations have been applied locally vs. production.

Deletion order (respects all foreign-key constraints):
    1. exercises          — FK to therapists + patients; not in any ORM cascade
    2. sessions.summary_id nulled out (sessions→session_summaries FK)
    3. session_summaries  — now safe to delete
    4. sessions           — FK to therapists + patients
    5. messages           — FK to therapists + patients
    6. patient_notes      — FK to therapists + patients
    7. therapist_notes    — FK to therapists
    8. patients           — FK to therapists
    9. therapist_profiles — FK to therapists
   10. therapists         — the root row
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.core.database import SessionLocal


def _fetch_one(db, sql, params=None):
    row = db.execute(text(sql), params or {}).fetchone()
    return row[0] if row else None


def _fetch_all(db, sql, params=None):
    return [r[0] for r in db.execute(text(sql), params or {}).fetchall()]


def _delete(db, table, where_sql, params, label):
    """Delete rows and return count.  Silently skips if table doesn't exist."""
    try:
        n = db.execute(text(f"DELETE FROM {table} WHERE {where_sql}"), params).rowcount
        if n:
            print(f"  deleted {n:>3} row(s) from {table}  ({label})")
        return n
    except Exception as exc:
        msg = str(exc).lower()
        if "no such table" in msg or "does not exist" in msg or "relation" in msg:
            # Table absent (e.g. older local DB missing a migration) — safe to skip
            return 0
        raise


def delete_therapist_by_email(email: str) -> None:
    db = SessionLocal()
    try:
        tid = _fetch_one(db, "SELECT id FROM therapists WHERE email = :email", {"email": email})
        if tid is None:
            print(f"[INFO] No therapist with email {email!r} — nothing to do.")
            return

        name = _fetch_one(db, "SELECT full_name FROM therapists WHERE id = :id", {"id": tid}) or ""
        provider = _fetch_one(db, "SELECT auth_provider FROM therapists WHERE id = :id", {"id": tid}) or "?"
        print(f"[INFO] Found therapist  id={tid}  name={name!r}  provider={provider!r}")

        # Collect IDs we'll need before anything is deleted
        patient_ids = _fetch_all(db, "SELECT id FROM patients WHERE therapist_id = :tid", {"tid": tid})
        session_ids = _fetch_all(db, "SELECT id FROM sessions WHERE therapist_id = :tid", {"tid": tid})
        summary_ids = _fetch_all(db, "SELECT summary_id FROM sessions WHERE therapist_id = :tid AND summary_id IS NOT NULL", {"tid": tid})

        print(f"[INFO] patients={len(patient_ids)}  sessions={len(session_ids)}  summaries={len(summary_ids)}")
        print()

        # ── 1. exercises ──────────────────────────────────────────────────
        # Has FK to both therapists and patients; not in any ORM cascade.
        _delete(db, "exercises", "therapist_id = :tid", {"tid": tid}, "therapist_id match")

        # ── 2. Null out sessions.summary_id ──────────────────────────────
        # sessions.summary_id is a FK to session_summaries.id.
        # Deleting a session_summaries row while sessions still reference it
        # would violate the FK (with PRAGMA foreign_keys=ON / PostgreSQL FKs).
        if summary_ids:
            db.execute(text("UPDATE sessions SET summary_id = NULL WHERE therapist_id = :tid"), {"tid": tid})
            print(f"  nulled  {len(session_ids):>3} sessions.summary_id")

        # ── 3. session_summaries ──────────────────────────────────────────
        if summary_ids:
            id_list = ", ".join(str(i) for i in summary_ids)
            n = db.execute(text(f"DELETE FROM session_summaries WHERE id IN ({id_list})")).rowcount
            print(f"  deleted {n:>3} row(s) from session_summaries")

        # ── 4. sessions ───────────────────────────────────────────────────
        _delete(db, "sessions", "therapist_id = :tid", {"tid": tid}, "therapist_id match")

        # ── 5. messages ───────────────────────────────────────────────────
        _delete(db, "messages", "therapist_id = :tid", {"tid": tid}, "therapist_id match")

        # ── 6. patient_notes ─────────────────────────────────────────────
        # Has FK to both patients and therapists.
        _delete(db, "patient_notes", "therapist_id = :tid", {"tid": tid}, "therapist_id match")

        # ── 7. therapist_notes ────────────────────────────────────────────
        _delete(db, "therapist_notes", "therapist_id = :tid", {"tid": tid}, "therapist_id match")

        # ── 8. patients ───────────────────────────────────────────────────
        _delete(db, "patients", "therapist_id = :tid", {"tid": tid}, "therapist_id match")

        # ── 9. therapist_profiles ─────────────────────────────────────────
        _delete(db, "therapist_profiles", "therapist_id = :tid", {"tid": tid}, "therapist_id match")

        # ── 10. therapist ─────────────────────────────────────────────────
        _delete(db, "therapists", "id = :tid", {"tid": tid}, "root row")

        db.commit()
        print(f"\n[OK] Therapist {email!r} (id={tid}) deleted — all related rows removed.\n")

    except Exception as exc:
        db.rollback()
        print(f"\n[ERROR] {exc}\n")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <email>")
        sys.exit(1)
    delete_therapist_by_email(sys.argv[1])
