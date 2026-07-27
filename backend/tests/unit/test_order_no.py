from app.services.order_no_service import generate_order_no


def test_generate_order_no_increments_per_prefix_per_day(app_client):  # noqa: ARG001
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        first = generate_order_no(db, "CG")
        db.commit()
        second = generate_order_no(db, "CG")
        db.commit()
        sale = generate_order_no(db, "XS")
        db.commit()

    assert first.startswith("CG")
    assert first.endswith("0001")
    assert second.endswith("0002")
    assert sale.startswith("XS")
    assert sale.endswith("0001")
