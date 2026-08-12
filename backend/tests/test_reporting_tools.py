"""AI reporting tool tests (real DB; model_router mocked where needed).

Each test seeds real rows with known amounts/dates and asserts the computed
aggregates match hand-calculated expected values exactly.
"""
import sys
import uuid

sys.path.insert(0, ".")

from datetime import date, datetime, timezone, timedelta

import pytest

from sqlalchemy import text


def _teardown(db, org):
    deletes = [
        "DELETE FROM activities WHERE organization_id = :id",
        "DELETE FROM invoice_items WHERE organization_id = :id",
        "DELETE FROM invoices WHERE organization_id = :id",
        "DELETE FROM tasks WHERE organization_id = :id",
        "DELETE FROM attendance WHERE organization_id = :id",
        "DELETE FROM expenses WHERE organization_id = :id",
        "DELETE FROM expense_categories WHERE organization_id = :id",
        "DELETE FROM deals WHERE organization_id = :id",
        "DELETE FROM employees WHERE organization_id = :id",
        "DELETE FROM users WHERE organization_id = :id",
        "DELETE FROM customers WHERE organization_id = :id",
        "DELETE FROM organizations WHERE id = :id",
    ]
    for statement in deletes:
        db.execute(text(statement), {"id": org.id})
    db.commit()


def _org(db):
    from app.models.organization import Organization

    org = Organization(
        name="Reporting Org",
        slug=f"reporting-{uuid.uuid4().hex[:10]}",
        settings={},
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _customer(db, org, name):
    from app.models.customer import Customer

    c = Customer(organization_id=org.id, name=name)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _invoice(db, org, customer, amount, created_at, status="paid"):
    from app.models.invoice import Invoice

    inv = Invoice(
        organization_id=org.id,
        customer_id=customer.id,
        invoice_number=f"INV-{uuid.uuid4().hex[:6].upper()}",
        amount=amount,
        status=status,
        created_at=created_at,
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


def _category(db, org, name):
    from app.models.finance import ExpenseCategory

    cat = ExpenseCategory(organization_id=org.id, name=name)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def _expense(db, org, category_id, title, amount, expense_date):
    from app.models.finance import Expense

    exp = Expense(
        organization_id=org.id,
        category_id=category_id,
        title=title,
        amount=amount,
        currency="USD",
        expense_date=expense_date,
        status="approved",
    )
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


def _deal(db, org, title, value, stage, created_at):
    from app.models.pipeline import Deal

    deal = Deal(
        organization_id=org.id,
        title=title,
        value=value,
        stage=stage,
        created_at=created_at,
    )
    db.add(deal)
    db.commit()
    db.refresh(deal)
    return deal


def _user(db, org, full_name):
    from app.models.user import User

    u = User(organization_id=org.id, full_name=full_name)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _employee(db, org, user, first_name, last_name="", status="active"):
    from app.models.hr import Employee

    emp = Employee(
        organization_id=org.id,
        user_id=user.id,
        first_name=first_name,
        last_name=last_name,
        status=status,
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


def _task(db, org, assigned_to, title, status, created_at, updated_at=None, due_date=None):
    from app.models.task import Task

    t = Task(
        organization_id=org.id,
        assigned_to=assigned_to,
        title=title,
        status=status,
        created_at=created_at,
        updated_at=updated_at if updated_at is not None else created_at,
        due_date=due_date,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _attendance(db, org, employee_id, check_in):
    from app.models.hr import Attendance

    a = Attendance(
        organization_id=org.id,
        employee_id=employee_id,
        check_in=check_in,
        status="present",
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def _activity(db, org, customer_id, created_at):
    from app.models.activity import Activity

    act = Activity(
        organization_id=org.id,
        entity_type="customer",
        entity_id=customer_id,
        action="note",
        created_at=created_at,
    )
    db.add(act)
    db.commit()
    db.refresh(act)
    return act


def _now():
    return datetime.now(timezone.utc)


def _days_ago(days, at_midnight=False):
    dt = _now() - timedelta(days=days)
    return dt


# ------------------------------------------------------------------- revenue


def test_revenue_report_aggregates_exact(db, monkeypatch):
    from app.ai.tools.reporting_tools import REPORTING_TOOLS

    # Never call the LLM in the exact-number assertions.
    monkeypatch.setattr(
        "app.ai.tools.reporting_tools.model_router.complete",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("LLM must not be called")),
    )

    org = _org(db)
    a = _customer(db, org, "Alpha")
    b = _customer(db, org, "Beta")
    try:
        _invoice(db, org, a, "100.00", _days_ago(1))
        _invoice(db, org, a, "50.00", _days_ago(2))
        _invoice(db, org, b, "200.00", _days_ago(3))
        _invoice(db, org, a, "99999.00", _days_ago(90), status="paid")  # out of range
        _invoice(db, org, b, "999.00", _days_ago(1), status="unpaid")  # not paid

        result = REPORTING_TOOLS["generate_revenue_report"].handler(
            db, org.id, None, {"period": "last_30_days"}
        )
        assert result["total_revenue"] == 350.0
        assert result["invoice_count"] == 3
        assert result["average_invoice_value"] == round(350.0 / 3, 2)
        by_customer = result["revenue_by_customer"]
        assert by_customer[0]["customer_name"] == "Beta"
        assert by_customer[0]["revenue"] == 200.0
        assert by_customer[1]["customer_name"] == "Alpha"
        assert by_customer[1]["revenue"] == 150.0
        assert any("concentration" in flag for flag in result["observations"])
    finally:
        _teardown(db, org)


def test_revenue_last_year_includes_and_excludes(db, monkeypatch):
    from app.ai.tools.reporting_tools import REPORTING_TOOLS

    monkeypatch.setattr(
        "app.ai.tools.reporting_tools.model_router.complete",
        lambda *a, **k: None,
    )
    org = _org(db)
    a = _customer(db, org, "Alpha")
    try:
        last_year1 = date(_now().year - 1, 6, 15)
        last_year2 = date(_now().year - 1, 12, 15)
        included1 = datetime(
            last_year1.year, last_year1.month, last_year1.day, tzinfo=timezone.utc
        )
        included2 = datetime(
            last_year2.year, last_year2.month, last_year2.day, tzinfo=timezone.utc
        )
        _invoice(db, org, a, "500.00", included1)  # within last_year
        _invoice(db, org, a, "800.00", included2)  # within last_year
        _invoice(db, org, a, "900.00", _now())  # this year, NOT last_year

        last_year_result = REPORTING_TOOLS["generate_revenue_report"].handler(
            db, org.id, None, {"period": "last_year"}
        )
        assert last_year_result["total_revenue"] == 1300.0
        assert last_year_result["invoice_count"] == 2
    finally:
        _teardown(db, org)


# ------------------------------------------------------------------- expense


def test_expense_report_aggregates_exact(db, monkeypatch):
    from app.ai.tools.reporting_tools import REPORTING_TOOLS

    monkeypatch.setattr(
        "app.ai.tools.reporting_tools.model_router.complete",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("LLM must not be called")),
    )
    org = _org(db)
    travel = _category(db, org, "Travel")
    software = _category(db, org, "Software")
    try:
        _expense(db, org, travel.id, "Flight", "100.00", date.today() - timedelta(days=2))
        _expense(db, org, software.id, "License", "250.00", date.today() - timedelta(days=3))
        _expense(db, org, travel.id, "Taxi", "50.00", date.today() - timedelta(days=4))
        _expense(db, org, None, "Misc", "30.00", date.today() - timedelta(days=1))
        _expense(db, org, software.id, "Old", "777.00", date.today() - timedelta(days=10))
        _expense(db, org, travel.id, "Stale", "999.00", date.today() - timedelta(days=40))

        last7 = REPORTING_TOOLS["generate_expense_report"].handler(
            db, org.id, None, {"period": "last_7_days"}
        )
        assert last7["total_expenses"] == 430.0
        assert last7["expense_count"] == 4
        cats = {c["category"]: c["amount"] for c in last7["by_category"]}
        assert cats["Travel"] == 150.0
        assert cats["Software"] == 250.0
        assert cats["Uncategorized"] == 30.0
        assert last7["top_expenses"][0]["amount"] == 250.0

        last30 = REPORTING_TOOLS["generate_expense_report"].handler(
            db, org.id, None, {"period": "last_30_days"}
        )
        assert last30["total_expenses"] == 1207.0
        assert last30["expense_count"] == 5
        cats30 = {c["category"]: c["amount"] for c in last30["by_category"]}
        assert cats30["Software"] == 1027.0
        assert cats30["Travel"] == 150.0
    finally:
        _teardown(db, org)


# ---------------------------------------------------------------- pipeline


def test_sales_pipeline_report_aggregates_exact(db, monkeypatch):
    from app.ai.tools.reporting_tools import REPORTING_TOOLS

    monkeypatch.setattr(
        "app.ai.tools.reporting_tools.model_router.complete",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("LLM must not be called")),
    )
    org = _org(db)
    try:
        _deal(db, org, "Proposal", "300.00", "proposal", _days_ago(1))
        _deal(db, org, "Lead", "100.00", "lead", _days_ago(2))
        _deal(db, org, "BigWon", "500.00", "closed_won", _days_ago(3))
        _deal(db, org, "SmallWon", "250.00", "won", _days_ago(4))
        _deal(db, org, "Lost1", "150.00", "lost", _days_ago(5))
        _deal(db, org, "Lost2", "400.00", "closed_lost", _days_ago(6))
        _deal(db, org, "Archived", "700.00", "archived", _days_ago(1))
        _deal(db, org, "OldOpen", "1000.00", "lead", _days_ago(100))  # snapshot only

        result = REPORTING_TOOLS["generate_sales_pipeline_report"].handler(
            db, org.id, None, {"period": "last_30_days"}
        )
        assert result["open_pipeline_value"] == 1400.0
        assert result["won_count"] == 2
        assert result["won_value"] == 750.0
        assert result["lost_count"] == 2
        assert result["win_rate"] == 0.5
        stage = {s["stage"]: s for s in result["stage_distribution"]}
        assert stage["archived"]["count"] == 1
        assert stage["archived"]["value"] == 700.0
        assert stage["closed_won"]["value"] == 500.0
        assert stage["lead"]["value"] == 100.0
    finally:
        _teardown(db, org)


# ------------------------------------------------------------- period guard


def test_invalid_period_returns_error_before_llm_or_db(db, monkeypatch):
    from app.ai.tools.reporting_tools import REPORTING_TOOLS

    calls = []
    monkeypatch.setattr(
        "app.ai.tools.reporting_tools.model_router.complete",
        lambda *a, **k: calls.append(1) or "{}",
    )
    org = _org(db)
    try:
        for tool in (
            "generate_revenue_report",
            "generate_expense_report",
            "generate_sales_pipeline_report",
            "generate_productivity_report",
            "generate_forecast_report",
            "generate_customer_cohort_report",
        ):
            bad = REPORTING_TOOLS[tool].handler(db, org.id, None, {"period": "next_week"})
            assert "error" in bad
            assert "last_7_days" in bad["error"]
            missing = REPORTING_TOOLS[tool].handler(db, org.id, None, {})
            assert "error" in missing
        assert calls == []
    finally:
        _teardown(db, org)


# --------------------------------------------------- LLM-failure resilience


def test_llm_failure_keeps_real_numbers(db, monkeypatch):
    from app.ai.tools.reporting_tools import REPORTING_TOOLS

    def boom(*a, **k):
        raise RuntimeError("LLM down")

    monkeypatch.setattr("app.ai.tools.reporting_tools.model_router.complete", boom)

    org = _org(db)
    a = _customer(db, org, "Alpha")
    try:
        _invoice(db, org, a, "424.00", _days_ago(1))
        _invoice(db, org, a, "76.00", _days_ago(2))

        result = REPORTING_TOOLS["generate_revenue_report"].handler(
            db, org.id, None, {"period": "last_30_days"}
        )
        assert result["total_revenue"] == 500.0
        assert result["invoice_count"] == 2
        assert result["source"] == "data"
        assert "500.00" in result["narrative"]
    finally:
        _teardown(db, org)


def test_llm_success_returns_numbers_and_narrative(db, monkeypatch):
    from app.ai.tools.reporting_tools import REPORTING_TOOLS

    payload = '{"narrative": "Growth looks strong.", "observations": ["Solid."]}'
    monkeypatch.setattr(
        "app.ai.tools.reporting_tools.model_router.complete",
        lambda *a, **k: payload,
    )
    org = _org(db)
    a = _customer(db, org, "Alpha")
    try:
        _invoice(db, org, a, "123.45", _days_ago(1))
        result = REPORTING_TOOLS["generate_expense_report"].handler(
            db, org.id, None, {"period": "month_to_date"}
        )
        # Expenses still exact; LLM only provides commentary.
        assert result["total_expenses"] == 0.0
        assert result["source"] == "llm"
        assert result["narrative"] == "Growth looks strong."

        rev = REPORTING_TOOLS["generate_revenue_report"].handler(
            db, org.id, None, {"period": "month_to_date"}
        )
        assert rev["total_revenue"] == 123.45
        assert rev["source"] == "llm"
        assert rev["narrative"] == "Growth looks strong."
    finally:
        _teardown(db, org)


# ------------------------------------------------------------ productivity


def test_productivity_report_aggregates_exact(db, monkeypatch):
    from app.ai.tools.reporting_tools import REPORTING_TOOLS

    monkeypatch.setattr(
        "app.ai.tools.reporting_tools.model_router.complete",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("LLM must not be called")),
    )
    org = _org(db)
    ua = _user(db, org, "Alice")
    ub = _user(db, org, "Bob")
    alice = _employee(db, org, ua, "Alice")
    bob = _employee(db, org, ub, "Bob")
    try:
        # Alice: 2 completed in period, 1 overdue, no overdue future.
        _task(db, org, ua.id, "A1", "done", _days_ago(10), updated_at=_days_ago(1))
        _task(db, org, ua.id, "A2", "done", _days_ago(2), updated_at=_days_ago(2))
        _task(db, org, ua.id, "A3", "in_progress", _days_ago(3), due_date=_days_ago(1))
        _task(db, org, ua.id, "A4", "done", _days_ago(300), updated_at=_days_ago(90))  # outside period
        # Bob: 2 completed in period, 1 overdue.
        _task(db, org, ub.id, "B1", "done", _days_ago(5), updated_at=_days_ago(4))
        _task(db, org, ub.id, "B2", "done", _days_ago(4), updated_at=_days_ago(3))
        _task(db, org, ub.id, "B3", "todo", _days_ago(6), due_date=_days_ago(2))

        _attendance(db, org, alice.id, _days_ago(1))
        _attendance(db, org, alice.id, _days_ago(2))
        _attendance(db, org, bob.id, _days_ago(1))

        result = REPORTING_TOOLS["generate_productivity_report"].handler(
            db, org.id, None, {"period": "last_30_days"}
        )
        assert result["team_total_tasks_completed"] == 4
        assert result["team_total_tasks_overdue"] == 2
        assert result["team_avg_completion_hours"] == 66.0
        emps = {e["name"]: e for e in result["per_employee"]}
        assert emps["Alice"]["tasks_completed"] == 2
        assert emps["Alice"]["tasks_overdue"] == 1
        assert emps["Alice"]["days_present"] == 2
        assert emps["Alice"]["avg_completion_hours"] == 108.0
        assert emps["Bob"]["tasks_completed"] == 2
        assert emps["Bob"]["tasks_overdue"] == 1
        assert emps["Bob"]["days_present"] == 1
        assert emps["Bob"]["avg_completion_hours"] == 24.0
        assert any("overdue tasks" in flag for flag in result["observations"])
    finally:
        _teardown(db, org)


def test_productivity_llm_failure_keeps_numbers(db, monkeypatch):
    from app.ai.tools.reporting_tools import REPORTING_TOOLS

    def boom(*a, **k):
        raise RuntimeError("LLM down")

    monkeypatch.setattr("app.ai.tools.reporting_tools.model_router.complete", boom)
    org = _org(db)
    ua = _user(db, org, "Alice")
    _employee(db, org, ua, "Alice")
    try:
        _task(db, org, ua.id, "A1", "done", _days_ago(2), updated_at=_days_ago(1))
        result = REPORTING_TOOLS["generate_productivity_report"].handler(
            db, org.id, None, {"period": "last_30_days"}
        )
        assert result["team_total_tasks_completed"] == 1
        assert result["source"] == "data"
        assert "1" in result["narrative"]
    finally:
        _teardown(db, org)


# ----------------------------------------------------------------- forecast


def test_forecast_reports_hand_computed_values(db, monkeypatch):
    from app.ai.tools.reporting_tools import REPORTING_TOOLS

    monkeypatch.setattr(
        "app.ai.tools.reporting_tools.model_router.complete",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("LLM must not be called")),
    )
    org = _org(db)
    a = _customer(db, org, "Alpha")
    try:
        # three comparable 30-day windows before now:
        # [now-90, now-60): 100 ; [now-60, now-30): 200 ; [now-30, now): 300
        _invoice(db, org, a, "100.00", _days_ago(70))
        _invoice(db, org, a, "200.00", _days_ago(40))
        _invoice(db, org, a, "300.00", _days_ago(10))

        result = REPORTING_TOOLS["generate_forecast_report"].handler(
            db, org.id, None, {"period": "last_30_days"}
        )
        assert result["method"] == "3-period moving average"
        revenues = [r["revenue"] for r in result["historical_revenues"]]
        assert revenues == [100.0, 200.0, 300.0]
        assert result["projected_revenue"] == 200.0
    finally:
        _teardown(db, org)


def test_forecast_llm_failure_keeps_numbers(db, monkeypatch):
    from app.ai.tools.reporting_tools import REPORTING_TOOLS

    def boom(*a, **k):
        raise RuntimeError("LLM down")

    monkeypatch.setattr("app.ai.tools.reporting_tools.model_router.complete", boom)
    org = _org(db)
    a = _customer(db, org, "Alpha")
    try:
        _invoice(db, org, a, "100.00", _days_ago(70))
        _invoice(db, org, a, "200.00", _days_ago(40))
        _invoice(db, org, a, "300.00", _days_ago(10))

        result = REPORTING_TOOLS["generate_forecast_report"].handler(
            db, org.id, None, {"period": "last_30_days"}
        )
        assert result["projected_revenue"] == 200.0
        assert result["source"] == "data"
        assert "200.00" in result["narrative"]
    finally:
        _teardown(db, org)


# ------------------------------------------------------------------ cohort


def test_customer_cohort_report_aggregates_exact(db, monkeypatch):
    from app.ai.tools.reporting_tools import REPORTING_TOOLS

    monkeypatch.setattr(
        "app.ai.tools.reporting_tools.model_router.complete",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("LLM must not be called")),
    )
    org = _org(db)
    try:
        c1 = _customer(db, org, "NewActive")
        _customer(db, org, "EngagedOld")
        _customer(db, org, "SilentOld")
        _customer(db, org, "InactiveOne")
        _customer(db, org, "NoActivity")

        # Age all customers out of the period, then bring only c1 in.
        from app.models.customer import Customer

        db.query(Customer).filter(Customer.organization_id == org.id).update(
            {"created_at": _days_ago(100)}
        )
        db.query(Customer).filter(Customer.id == c1.id).update({"created_at": _days_ago(2)})
        db.query(Customer).filter(Customer.name == "InactiveOne").update(
            {"status": "inactive"}
        )
        db.commit()

        engaged_old = db.query(Customer).filter(Customer.name == "EngagedOld").first()
        silent = db.query(Customer).filter(Customer.name == "SilentOld").first()
        inactive = db.query(Customer).filter(Customer.name == "InactiveOne").first()

        _activity(db, org, c1.id, _days_ago(1))           # new + engaged
        _activity(db, org, engaged_old.id, _days_ago(1))  # engaged
        _activity(db, org, silent.id, _days_ago(50))      # prior-period only -> churn
        _activity(db, org, inactive.id, _days_ago(1))     # inactive, ignored

        # DBG-BEGIN
        from app.models.activity import Activity as _Act
        db.expire_all()
        _custs = db.query(Customer).filter(Customer.organization_id == org.id).all()
        _acts = db.query(_Act).filter(_Act.organization_id == org.id).all()
        print("\nDBG custs:", [(str(c.id), c.name) for c in _custs])
        print("DBG acts:", [(str(a.entity_id), a.created_at.isoformat()) for a in _acts])
        import app.ai.tools.reporting_tools as _rt
        _s, _e = _rt._period_bounds("last_30_days")
        _ids = {c.id for c in _custs}
        print("DBG engaged set:", sorted(str(x) for x in ({a.entity_id for a in _acts if _s <= a.created_at <= _e} & _ids)))
        # DBG-END

        result = REPORTING_TOOLS["generate_customer_cohort_report"].handler(
            db, org.id, None, {"period": "last_30_days"}
        )
        assert result["new_customers_acquired"] == 1
        assert result["active_customers"] == 4
        assert result["engaged_customers"] == 2
        assert result["churn_candidates"] == 1
        assert result["segmentation"] is None
        assert "segment" in result["segmentation_note"]
    finally:
        _teardown(db, org)


def test_customer_cohort_llm_failure_keeps_numbers(db, monkeypatch):
    from app.ai.tools.reporting_tools import REPORTING_TOOLS

    def boom(*a, **k):
        raise RuntimeError("LLM down")

    monkeypatch.setattr("app.ai.tools.reporting_tools.model_router.complete", boom)
    org = _org(db)
    c1 = _customer(db, org, "NewActive")
    try:
        from app.models.customer import Customer

        db.query(Customer).filter(Customer.id == c1.id).update({"created_at": _days_ago(2)})
        db.commit()
        _activity(db, org, c1.id, _days_ago(1))

        res = REPORTING_TOOLS["generate_customer_cohort_report"].handler(
            db, org.id, None, {"period": "last_30_days"}
        )
        assert res["new_customers_acquired"] == 1
        assert res["engaged_customers"] == 1
        assert res["source"] == "data"
        assert "1" in res["narrative"]
    finally:
        _teardown(db, org)