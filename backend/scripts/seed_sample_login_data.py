"""Woodful ERP - application user/login seeding.

Responsible ONLY for the five application users and their login/access
information (username, email, role, employee link). Does NOT touch
demo business data - that's scripts/seed_sample_data.py's job entirely,
and this script never creates/modifies a Client, Product, Estimate, or
any other business record.

PASSWORDS: this script does NOT invent or permanently seed passwords,
per explicit instruction. On CREATE, each new user gets a genuinely
random, cryptographically-generated placeholder password hash (a real,
valid bcrypt hash of a value nobody has ever seen or typed - not a
weak/guessable default like "changeme123") - this only satisfies the
database's NOT NULL constraint on password_hash and can never
successfully authenticate anyone, by construction. On UPDATE (a user
that already exists), password_hash is NEVER touched - re-running this
script can never overwrite a real password you've already set via CMD.
Use scripts/set_user_password.py (built alongside this script) to set
the real password afterward - see this script's own printed output for
the exact command.

Idempotent: matched by username. Existing users are updated (email,
full_name, role, employee_id) rather than duplicated. This script
NEVER creates an Employee record - it only looks up an EXISTING one
(Shweta/Pankaj/Arpit, seeded by seed_sample_data.py) to link. Garima
and Nikhil are Master/application users, not Woodful employees, and
are deliberately never linked to any Employee record.

Usage (from backend/):
    python scripts/seed_sample_login_data.py
"""
import sys
import os
import secrets
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.WARNING)  # keep output to this script's own prints


# (username, email, full_name, role, employee_name_to_link_or_None)
# role uses the app's ACTUAL existing terminology (master/user) - no
# new role invented, matching the explicit instruction.
#
# Garima and Nikhil are Master/application users, NOT Woodful
# employees (Founder and Developer/project user respectively) - they
# get employee_name=None deliberately, never linked to an Employee
# record. No joining date, no salary slips, no payroll eligibility.
# Shweta/Pankaj/Arpit ARE real Woodful employees as well as users, so
# they keep their employee link.
USERS = [
    ("garimas", "garimas@woodfulcreations.co.in", "Garima Sharma", "master", None),
    ("nikhils", "nikhils@woodfulcreations.co.in", "Nikhil Soni", "master", None),
    ("shwetav", "shwetav@woodfulcreations.co.in", "Shweta", "user", "Shweta"),
    ("pankajv", "pankajv@woodfulcreations.co.in", "Pankaj", "user", "Pankaj"),
    ("arpitv", "arpitv@woodfulcreations.co.in", "Arpit", "user", "Arpit"),
]


def _random_placeholder_password_hash(hash_password_fn) -> str:
    """A real, valid bcrypt hash of a value nobody has ever seen -
    satisfies the NOT NULL constraint, cannot authenticate anyone. Not
    logged, not returned, not derivable from anything printed by this
    script."""
    return hash_password_fn(secrets.token_urlsafe(48))


def main():
    from app.platform.database.database import SessionLocal
    from app.platform.security.security import hash_password
    from app.modules.auth.models import User
    from app.modules.hr.models import Employee

    db_path = os.environ.get("LOCAL_DATABASE_URL", "sqlite:///./woodful.db")
    print("SEED LOGIN DATA")
    print("=" * 60)
    print(f"Database: {db_path}")
    print()

    db = SessionLocal()
    results = []
    try:
        for stale_name in ("Garima Sharma", "Nikhil Soni"):
            stale = db.query(Employee).filter(Employee.name == stale_name).first()
            if stale:
                print(f"WARNING: an Employee record named {stale_name!r} exists ({stale.employee_code}). "
                      f"Garima and Nikhil are Master users, not employees, and should not have one. "
                      f"If this was created by an older version of this script, review and remove it "
                      f"via the Employees page - this script does not delete it automatically.")
        print()

        for username, email, full_name, role, employee_name in USERS:
            employee = None
            if employee_name:
                employee = db.query(Employee).filter(Employee.name == employee_name).first()
                if not employee:
                    # This script seeds logins only - it must never
                    # create an Employee record itself.
                    # A real employee should already exist via
                    # seed_sample_data.py; if not, that's a genuine
                    # data problem to surface, not paper over here.
                    print(f"WARNING: no existing Employee named {employee_name!r} found - "
                          f"{username} will be created without an employee link. "
                          f"Run seed_sample_data.py first if this employee should exist.")

            existing = db.query(User).filter(User.username == username).first()
            if existing:
                existing.email = email
                existing.full_name = full_name
                existing.role = role
                # Self-correcting: explicitly clears employee_id for
                # Garima/Nikhil even if a PREVIOUS run of an older,
                # buggy version of this script had already set it -
                # not just "never set it going forward".
                existing.employee_id = employee.id if employee else None
                db.commit()
                results.append((username, email, role, employee_name, "UPDATED (password_hash untouched)"))
            else:
                new_user = User(
                    username=username, email=email, full_name=full_name, role=role,
                    employee_id=employee.id if employee else None,
                    password_hash=_random_placeholder_password_hash(hash_password),
                    is_active=True,
                    cannot_be_deleted=(role == "master"),
                )
                db.add(new_user)
                db.commit()
                results.append((username, email, role, employee_name, "CREATED (placeholder password - see instructions below)"))
    finally:
        db.close()

    print(f"{'USERNAME':<12}{'EMAIL':<34}{'ROLE':<8}{'EMPLOYEE':<16}STATUS")
    print("-" * 100)
    for username, email, role, employee_name, status in results:
        print(f"{username:<12}{email:<34}{role:<8}{(employee_name or '-'):<16}{status}")

    print()
    print("Verify the database contains exactly these five username/email pairs:")
    for username, email, _, _, _ in USERS:
        print(f"  {username:<10}| {email}")

    db_file = db_path.replace("sqlite:///", "")
    if os.path.exists(db_file):
        size = os.path.getsize(db_file)
        print(f"\n{db_file}: exists, {size} bytes" + (" - WARNING: file is empty (0 bytes)" if size == 0 else ""))
    else:
        print(f"\nWARNING: {db_file} was not found on disk after running.")

    print()
    print("=" * 60)
    print("NEXT STEP - set real passwords (none were invented or seeded):")
    print("  python scripts/set_user_password.py --username garimas")
    print("  python scripts/set_user_password.py --username nikhils")
    print("  python scripts/set_user_password.py --username shwetav")
    print("  python scripts/set_user_password.py --username pankajv")
    print("  python scripts/set_user_password.py --username arpitv")
    print("Each prompts for the new password interactively (not echoed to the screen).")


if __name__ == "__main__":
    main()
