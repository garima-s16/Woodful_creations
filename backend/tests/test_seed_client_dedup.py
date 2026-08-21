"""Tests for the permanent-roster client-deduplication fix in
seed_sample_data.py (resolve_woodful_client_duplicates /
seed_woodful_clients). Verifies the seed functions themselves against
a fresh, isolated test database - not the dev database the
__main__ block populates - so this exercises exactly the logic that
runs at seed time, using the same demo rows seed_clients/seed_orders/
seed_estimates would create.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from seed_sample_data import (
    seed_clients, seed_orders, seed_estimates,
    resolve_woodful_client_duplicates, seed_woodful_clients,
    WOODFUL_CLIENTS,
)
from app.models.client import Client
from app.models.order import Order
from app.models.estimate import Estimate


def _run_full_client_seed(db):
    """Mirrors the exact __main__ call order for the client-related
    seed steps."""
    clients = seed_clients(db)
    orders = seed_orders(db, clients)
    estimates = seed_estimates(db, clients, orders)
    resolve_woodful_client_duplicates(db)
    seed_woodful_clients(db)
    return clients, orders, estimates


def test_shrangi_is_a_single_client_with_roster_phone_and_address(db_session):
    _run_full_client_seed(db_session)

    shrangis = db_session.query(Client).filter(Client.name == "Shrangi").all()
    assert len(shrangis) == 1, f"Expected exactly one Shrangi client, found {len(shrangis)}"

    shrangi = shrangis[0]
    assert shrangi.phone == "7009870098"
    assert shrangi.address == "42 Scheme No. 54, Indore, Madhya Pradesh - 452010"


def test_shrangi_transactions_all_point_to_the_single_client(db_session):
    _run_full_client_seed(db_session)

    shrangi = db_session.query(Client).filter(Client.name == "Shrangi").one()

    # Exactly 2 Orders and 2 Estimates - the coffee table (given April,
    # converted to an Order in June) and the sofa (given May 15,
    # remains an independent Estimate). The unrelated CL-003 "Anaya"
    # (a different early demo client, coincidentally also named
    # Shrangi before that rename) is a distinct person and must NOT be
    # merged into this count.
    order_codes = {"WC-2026-007", "WC-2026-008"}
    estimate_codes = {"EST-007", "EST-008"}

    orders = db_session.query(Order).filter(Order.order_code.in_(order_codes)).all()
    assert len(orders) == len(order_codes)
    assert all(o.client_id == shrangi.id for o in orders)

    estimates = db_session.query(Estimate).filter(Estimate.estimate_code.in_(estimate_codes)).all()
    assert len(estimates) == len(estimate_codes)
    assert all(e.client_id == shrangi.id for e in estimates)


def test_shrangi_has_exactly_two_estimates_and_two_orders(db_session):
    """Final Shrangi verification (bulk-data test spec): 1 Client, 2
    Estimates, 2 Orders - coffee table Estimate -> coffee table Order,
    sofa Estimate remains an Estimate, wardrobe is an independent
    Direct Order."""
    _run_full_client_seed(db_session)
    shrangi = db_session.query(Client).filter(Client.name == "Shrangi").one()

    all_orders = db_session.query(Order).filter(Order.client_id == shrangi.id).all()
    all_estimates = db_session.query(Estimate).filter(Estimate.client_id == shrangi.id).all()
    assert len(all_orders) == 2, f"Expected exactly 2 Orders for Shrangi, found {len(all_orders)}: {[o.order_code for o in all_orders]}"
    assert len(all_estimates) == 2, f"Expected exactly 2 Estimates for Shrangi, found {len(all_estimates)}: {[e.estimate_code for e in all_estimates]}"

    coffee_order = next(o for o in all_orders if o.order_code == "WC-2026-007")
    wardrobe_order = next(o for o in all_orders if o.order_code == "WC-2026-008")
    coffee_estimate = next(e for e in all_estimates if e.estimate_code == "EST-007")
    sofa_estimate = next(e for e in all_estimates if e.estimate_code == "EST-008")

    # Coffee Table: Estimate -> Order conversion
    assert coffee_estimate.order_id == coffee_order.id
    assert coffee_estimate.status == "closed"
    assert coffee_order.project_status == "Completed"
    assert coffee_order.advance == coffee_order.order_value  # fully paid

    # Sofa: remains an independent Estimate, never converted
    assert sofa_estimate.order_id is None

    # Wardrobe: a completely independent Direct Order, not connected
    # to any Estimate at all
    assert wardrobe_order.id != coffee_order.id
    assert not any(e.order_id == wardrobe_order.id for e in all_estimates)


def test_no_duplicate_clients_for_any_roster_name(db_session):
    _run_full_client_seed(db_session)

    for name, phone, _address in WOODFUL_CLIENTS:
        matches = db_session.query(Client).filter(Client.name == name).all()
        assert len(matches) == 1, f"{name} has {len(matches)} client records, expected 1"
        assert matches[0].phone == phone


def test_client_dedup_is_idempotent_on_rerun(db_session):
    _run_full_client_seed(db_session)
    before_count = db_session.query(Client).count()
    before_ids = sorted(c.id for c in db_session.query(Client).all())

    # Re-running the same two steps against the now-corrected data must
    # not create or delete anything further.
    resolve_woodful_client_duplicates(db_session)
    seed_woodful_clients(db_session)

    after_count = db_session.query(Client).count()
    after_ids = sorted(c.id for c in db_session.query(Client).all())
    assert after_count == before_count
    assert after_ids == before_ids


def test_non_roster_demo_clients_are_untouched(db_session):
    """Khushaal, Pratharv, and Anaya aren't on the permanent roster, so
    the dedup pass must never touch or remove them. Anaya (CL-003) was
    coincidentally also named "Shrangi" in an earlier, unrelated demo
    scenario before being renamed specifically to avoid colliding with
    the roster's own distinct Shrangi (CL-008) - this asserts that
    rename stuck and she's her own person, not merged into anyone."""
    _run_full_client_seed(db_session)

    khushaal = db_session.query(Client).filter(Client.name == "Khushaal").one_or_none()
    pratharv = db_session.query(Client).filter(Client.name == "Pratharv").one_or_none()
    anaya = db_session.query(Client).filter(Client.name == "Anaya").one_or_none()
    assert khushaal is not None
    assert pratharv is not None
    assert anaya is not None

    shrangi_matches = db_session.query(Client).filter(Client.name == "Shrangi").all()
    assert len(shrangi_matches) == 1, "Anaya's rename must leave exactly one Shrangi (the roster's own)"
