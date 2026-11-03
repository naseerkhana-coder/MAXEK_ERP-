"""Administration -> Company Letters: saving, editing, permissions, references,
employee autofill, register, print options and real A4 PDF output."""
from __future__ import annotations

import hashlib
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile

import pytest

import company_letters as cl
from test_payroll_sunday_rule import add_staff, client, ctx  # noqa: F401  (fixtures)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET = os.path.join(ROOT, "static", "assets", "letterhead", "maxek-letterhead.png")
# sha256 of the letterhead image supplied by the user (A4, 2482 x 3508 px @ 300 dpi).
SUPPLIED_SHA256 = "d2d685daf22dfe40c008"

BASE = "/administration/company-letters"


def form(**over):
    data = {
        "reference_no": "MAX/LT/26/001", "letter_date": "2026-11-03",
        "letter_type": "General Administration Letter", "recipient_name": "HiLITE Contracting",
        "recipient_org": "Projects", "recipient_address": "Kozhikode\n673014",
        "subject": "Revised work order", "salutation": "Dear Sir,",
        "body_html": "<p>Please revise.</p>", "closing": "Yours faithfully,",
        "signatory_name": "N. Khan", "signatory_designation": "Director",
    }
    data.update(over)
    return data


def set_counter(db, n, fy="2026-27"):
    """Configure the letter counter the way the ERP's numbering service stores it."""
    import document_numbering_service as numbering
    numbering.seed_default_sequences(db, fy)
    db.execute("UPDATE document_number_sequences SET current_sequence=? WHERE doc_type='company_letter_no' AND fiscal_year=?", (n, fy))
    db.commit()


def make_user(db, name, workflow_role, *, role="user", department="Administration", customer_id=None, company_id=None):
    db.execute(
        "INSERT INTO users(username, password, role, status, workflow_role, department, customer_id, company_id) "
        "VALUES(?,?,?,?,?,?,?,?)", (name, "x", role, "Active", workflow_role, department, customer_id, company_id))
    db.commit()
    return db.execute("SELECT id FROM users WHERE username=?", (name,)).fetchone()[0]


def client_for(app, db, uid, **session_vals):
    """A client logged in as an existing user row (no admin shortcut)."""
    row = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    c = app.test_client()
    with c.session_transaction() as sess:
        sess.update(user_id=uid, username=row["username"], role=row["role"],
                    workflow_role=row["workflow_role"], department=row["department"],
                    customer_id=row["customer_id"], company_id=row["company_id"])
        sess.update(session_vals)
    return c


def grant_tabs(db, uid, *labels, dept="administration"):
    db.execute("DELETE FROM user_tab_permissions WHERE user_id=? AND department_slug=?", (uid, dept))
    for ep, label in labels:
        db.execute("INSERT INTO user_tab_permissions(user_id, department_slug, tab_key, endpoint, label, granted, updated_at) "
                   "VALUES(?,?,?,?,?,1,'2026-11-03')", (uid, dept, f"{ep}::{label}", ep, label))
    db.commit()


def grant_employee_data(db, uid):
    """Explicit Employee Master grant under HR & Payroll (the ERP's own department tab permissions)."""
    from user_permission_service import ensure_user_tab_permissions_schema
    ensure_user_tab_permissions_schema(db)
    db.execute("INSERT INTO user_tab_permissions(user_id, department_slug, tab_key, endpoint, label, granted, updated_at) "
               "VALUES(?,?,?,?,?,1,'2026-11-03')", (uid, "hr-payroll", "staff::Employee Master", "staff", "Employee Master"))
    db.commit()


def count(db, table="company_letters"):
    return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


# ───────────────────────────── saving / editing ─────────────────────────────


def test_create_edit_and_view(ctx, client):
    db, _ = ctx
    r = client.post(f"{BASE}/new", data=form(), follow_redirects=False)
    assert r.status_code == 302 and r.headers["Location"].endswith(f"{BASE}/1")
    row = dict(db.execute("SELECT * FROM company_letters").fetchone())
    assert row["reference_no"] == "MAX/LT/26/001" and row["created_by"] and row["subject"] == "Revised work order"

    page = client.get(f"{BASE}/1/edit").get_data(as_text=True)
    assert 'value="MAX/LT/26/001"' in page and "Revised work order" in page

    r = client.post(f"{BASE}/1/edit", data=form(subject="Changed subject", body_html="<p><b>New</b> body</p>"))
    assert r.status_code == 302
    row = dict(db.execute("SELECT * FROM company_letters").fetchone())
    assert row["subject"] == "Changed subject" and "<b>New</b>" in row["body_html"] and row["modified_at"]
    assert count(db) == 1
    view = client.get(f"{BASE}/1").get_data(as_text=True)
    assert "Changed subject" in view and "N. Khan" in view


def test_offer_letter_type_and_all_types_are_accepted(ctx, client):
    db, _ = ctx
    assert cl.LETTER_TYPES[:2] == ("Offer Letter", "General Administration Letter")
    client.post(f"{BASE}/new", data=form(letter_type="Offer Letter"))
    assert db.execute("SELECT letter_type FROM company_letters").fetchone()[0] == "Offer Letter"
    client.post(f"{BASE}/new", data=form(reference_no="X-2", letter_type="Nonsense"))
    assert count(db) == 1


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("recipient_name", "", "Recipient name is required"),
        ("subject", " ", "Subject is required"),
        ("body_html", "<p> </p>", "body cannot be empty"),
        ("signatory_name", "", "signatory name is required"),
        ("letter_date", "", "Letter date is required"),
        ("letter_date", "31/10/2026", "not a valid date"),
        ("reference_no", "", "No starting number is recorded"),
        ("letter_type", "Bogus", "valid letter type"),
    ],
)
def test_validation_messages_and_nothing_saved(ctx, client, field, value, message):
    db, _ = ctx
    html = client.post(f"{BASE}/new", data=form(**{field: value})).get_data(as_text=True)
    assert message in html
    assert count(db) == 0
    assert 'value="Revised work order"' in html or field == "subject"   # the user's input is kept


def test_body_is_sanitised_on_save_and_on_render(ctx, client):
    db, _ = ctx
    evil = '<p onclick="x()">ok <b>bold</b></p><script>alert(1)</script><img src=x onerror=alert(2)><a href="javascript:1">l</a>'
    client.post(f"{BASE}/new", data=form(body_html=evil))
    stored = db.execute("SELECT body_html FROM company_letters").fetchone()[0]
    for bad in ("script", "onclick", "onerror", "<img", "javascript", "<a "):
        assert bad not in stored
    assert "<b>bold</b>" in stored and "ok" in stored
    assert cl.sanitize_letter_html('<p style="text-align:center;color:red">x</p>') == '<p style="text-align:center">x</p>'
    assert "alert" not in client.get(f"{BASE}/1/preview").get_data(as_text=True).replace("alert(1)", "")


# ───────────────────────────── reference numbers ─────────────────────────────


def test_reference_numbers_are_unique_even_with_case_and_spacing(ctx, client):
    db, _ = ctx
    client.post(f"{BASE}/new", data=form())
    for dup in ("MAX/LT/26/001", " max/lt/26/001 "):
        html = client.post(f"{BASE}/new", data=form(reference_no=dup)).get_data(as_text=True)
        assert "already used by another letter" in html
    assert count(db) == 1
    # Editing a letter may keep its own number but may not take another's.
    client.post(f"{BASE}/new", data=form(reference_no="MAX/LT/26/002"))
    assert client.post(f"{BASE}/2/edit", data=form(reference_no="MAX/LT/26/002", subject="s2")).status_code == 302
    html = client.post(f"{BASE}/2/edit", data=form(reference_no="MAX/LT/26/001")).get_data(as_text=True)
    assert "already used by another letter" in html
    assert db.execute("SELECT reference_no FROM company_letters WHERE id=2").fetchone()[0] == "MAX/LT/26/002"


def test_database_itself_enforces_uniqueness(ctx):
    import sqlite3
    db, _ = ctx
    cl.ensure_company_letters_schema(db)
    values, errs = cl.validate_letter_form(db, form())
    assert errs == []
    cl.save_letter(db, values, "t")
    with pytest.raises(ValueError, match="already used"):    # bypassing validation still cannot duplicate
        cl.save_letter(db, dict(values, reference_no=" MAX/LT/26/001"), "t")
    db.rollback()


def test_suggestion_is_not_guessed_from_one_sample(ctx, client):
    """With nothing recorded for the year there is NO suggestion; the user must enter the number."""
    db, _ = ctx
    cl.ensure_company_letters_schema(db)
    sug = cl.suggest_reference(db, "2026-11-03")
    assert sug["reference"] == "" and sug["configured"] is False and "2026-27" in sug["basis"]
    page = client.get(f"{BASE}/new").get_data(as_text=True)
    assert "No letter number is recorded" in page and 'name="reference_no"' in page
    assert "MAX/LT/26/117" not in page and "MAX/LT/26/001" not in page
    # saving without entering one is refused with an explanation, nothing is invented
    html = client.post(f"{BASE}/new", data=form(reference_no="")).get_data(as_text=True)
    assert "Enter the reference number manually" in html and count(db) == 0


def test_provisional_sample_number_is_only_used_when_entered(ctx, client):
    """MAX/LT/26/117 is one sample: entering it makes later numbers continue, nothing more."""
    db, _ = ctx
    client.post(f"{BASE}/new", data=form(reference_no="MAX/LT/26/117"))
    sug = cl.suggest_reference(db, "2026-11-03")
    assert sug["reference"] == "MAX/LT/26/118" and "Continues from MAX/LT/26/117" in sug["basis"]
    page = client.get(f"{BASE}/new").get_data(as_text=True)
    assert 'value="MAX/LT/26/118"' in page and "Check it against your register" in page


def test_existing_references_in_other_registers_are_inspected(ctx, client):
    """The next number is above everything already recorded, wherever it was recorded."""
    db, _ = ctx
    cl.ensure_company_letters_schema(db)
    client.post("/office/letters", data={
        "letter_type": "Official Letter", "letter_date": "2026-11-01", "to_name": "Old", "to_address": "x",
        "subject": "Old subject", "body": "Body", "signed_by": "A"})
    db.execute("UPDATE office_letters SET letter_number='MAX/LT/26/131', reference_no='MAX/LT/26/131'")
    db.commit()
    assert cl.suggest_reference(db, "2026-11-03")["reference"] == "MAX/LT/26/132"
    cl.ensure_company_letters_schema(db)
    db.execute("INSERT INTO office_outward(register_number, reference_no) VALUES('MAX/LT/26/140','MAX/LT/26/141')")
    db.commit()
    assert cl.suggest_reference(db, "2026-11-03")["reference"] == "MAX/LT/26/142"
    set_counter(db, 150)                                         # the configured counter can be ahead too
    assert cl.suggest_reference(db, "2026-11-03")["reference"] == "MAX/LT/26/151"
    # free-form references in the registers are ignored, not misread
    db.execute("INSERT INTO office_outward(register_number) VALUES('custom-99')")
    db.commit()
    assert cl.suggest_reference(db, "2026-11-03")["reference"] == "MAX/LT/26/151"


def test_numbers_restart_each_financial_year_and_year_change_needs_a_first_number(ctx, client):
    """April-March years, one counter each. A new year has no number until one is entered."""
    db, _ = ctx
    cl.ensure_company_letters_schema(db)
    set_counter(db, 116)
    assert cl.suggest_reference(db, "2027-03-31")["reference"] == "MAX/LT/26/117"   # still FY 2026-27
    nxt = cl.suggest_reference(db, "2027-04-01")                                    # FY 2027-28 starts
    assert nxt["reference"] == "" and nxt["configured"] is False and nxt["fiscal_year"] == "2027-28"
    assert cl.suggest_reference(db, "2026-03-31")["fiscal_year"] == "2025-26"       # previous year, own counter
    client.post(f"{BASE}/new", data=form(reference_no="MAX/LT/27/001", letter_date="2027-04-02"))
    assert cl.suggest_reference(db, "2027-04-10")["reference"] == "MAX/LT/27/002"
    assert cl.suggest_reference(db, "2027-03-01")["reference"] == "MAX/LT/26/117"   # old year untouched


def test_auto_number_is_allocated_and_counter_advances(ctx, client):
    db, _ = ctx
    set_counter(db, 116)
    html = client.get(f"{BASE}/new").get_data(as_text=True)
    assert 'value="MAX/LT/26/117"' in html
    client.post(f"{BASE}/new", data=form(reference_no="MAX/LT/26/117", suggested_reference="MAX/LT/26/117"))
    client.post(f"{BASE}/new", data=form(reference_no="MAX/LT/26/118", suggested_reference="MAX/LT/26/118"))
    refs = [r[0] for r in db.execute("SELECT reference_no FROM company_letters ORDER BY id")]
    assert refs == ["MAX/LT/26/117", "MAX/LT/26/118"]
    cur = db.execute("SELECT current_sequence FROM document_number_sequences WHERE doc_type='company_letter_no' AND fiscal_year='2026-27'").fetchone()[0]
    assert cur == 118


def test_stale_suggestion_gets_a_fresh_number_and_user_is_told(ctx, client):
    """Two people open the form at the same time; the second save must not duplicate or fail silently."""
    db, _ = ctx
    set_counter(db, 116)
    a = client.get(f"{BASE}/new").get_data(as_text=True)          # both see ...117
    client.post(f"{BASE}/new", data=form(reference_no="MAX/LT/26/117", suggested_reference="MAX/LT/26/117", subject="first"))
    r = client.post(f"{BASE}/new", data=form(reference_no="MAX/LT/26/117", suggested_reference="MAX/LT/26/117", subject="second"),
                    follow_redirects=True)
    refs = [r_[0] for r_ in db.execute("SELECT reference_no FROM company_letters ORDER BY id")]
    assert refs == ["MAX/LT/26/117", "MAX/LT/26/118"]
    assert "was taken by another letter" in r.get_data(as_text=True) and "MAX/LT/26/118" in r.get_data(as_text=True)
    # a hand-typed number is never silently changed: it is refused
    html = client.post(f"{BASE}/new", data=form(reference_no="MAX/LT/26/117", suggested_reference="MAX/LT/26/150")).get_data(as_text=True)
    assert "already used by another letter" in html and count(db) == 2


def test_concurrent_saves_never_duplicate_a_number(ctx, tmp_path):
    """Separate connections (as separate requests/workers use) saving at the same instant."""
    import sqlite3
    import threading
    db, _ = ctx
    cl.ensure_company_letters_schema(db)
    set_counter(db, 116)
    path = db.execute("PRAGMA database_list").fetchone()[2]
    results, errors = [], []
    barrier = threading.Barrier(8)

    def worker(i):
        conn = sqlite3.connect(path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            values, errs = cl.validate_letter_form(conn, form(reference_no="", subject=f"s{i}"))
            assert not errs
            barrier.wait()
            lid, ref = cl.save_letter(conn, values, f"u{i}")
            conn.commit()
            results.append(ref)
        except Exception as exc:                                  # pragma: no cover - reported below
            errors.append(repr(exc))
            conn.rollback()
        finally:
            conn.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors, errors
    assert sorted(results) == [f"MAX/LT/26/{n}" for n in range(117, 125)]
    assert len(set(results)) == 8
    db.rollback()
    assert db.execute("SELECT COUNT(DISTINCT reference_no) FROM company_letters").fetchone()[0] == 8
    assert db.execute("SELECT current_sequence FROM document_number_sequences WHERE doc_type='company_letter_no'").fetchone()[0] == 124


def test_numbering_service_default_layout():
    import document_numbering_service as n
    assert n.DEFAULT_PREFIXES["company_letter_no"] == "MAX/LT"
    assert n.format_document_number("MAX/LT", "2026-27", 117, n.DEFAULT_PATTERNS["company_letter_no"]) == "MAX/LT/26/117"
    assert n.format_document_number("PO", "2026-27", 5) == "PO/2627/0005"      # other types unchanged


# ───────────────────────────── employee autofill ─────────────────────────────


def test_employee_search_and_autofill(ctx, client):
    db, _ = ctx
    sid = add_staff(db, "Anita Menon", "EMP9001", salary=30000, joining="2026-11-15")
    db.execute("UPDATE staff SET designation='Site Engineer', department='Projects', mobile='9999', email='a@x.in' WHERE id=?", (sid,))
    db.commit()
    found = client.get(f"{BASE}/employees?q=anita").get_json()["employees"]
    assert [e["staff_name"] for e in found] == ["Anita Menon"]
    assert client.get(f"{BASE}/employees?q=EMP9001").get_json()["employees"][0]["id"] == sid

    d = client.get(f"{BASE}/employee/{sid}").get_json()
    assert d["name"] == "Anita Menon" and d["designation"] == "Site Engineer"
    assert d["joining_date_display"] == "15/11/2026" and d["email"] == "a@x.in"
    assert d["salutation"] == "Dear Anita Menon," and d["recipient_org"] == "Site Engineer, Projects"
    assert "offer_body_html" not in d                                # no pre-written terms
    assert "Date of joining: 15/11/2026" in d["facts_html"] and "Site Engineer" in d["facts_html"]
    assert "30000" not in str(d)                                   # salary is never auto-filled
    assert not re.search(r"(?i)salary|probation|notice|leave|stipend|ctc", d["facts_html"])
    assert client.get(f"{BASE}/employee/99999").status_code == 404

    client.post(f"{BASE}/new", data=form(employee_id=str(sid), recipient_name="Anita Menon"))
    assert db.execute("SELECT employee_id FROM company_letters").fetchone()[0] == sid
    assert "Anita Menon (EMP9001)" in client.get(f"{BASE}/1/edit").get_data(as_text=True)
    assert "Anita Menon" in client.get(f"{BASE}/1").get_data(as_text=True)


def test_unknown_employee_id_is_dropped_not_saved(ctx, client):
    db, _ = ctx
    html = client.post(f"{BASE}/new", data=form(employee_id="424242")).get_data(as_text=True)
    assert "selected employee was not found" in html and count(db) == 0


# ───────────────────────────── register ─────────────────────────────


def test_register_search_filter_and_pagination(ctx, client):
    db, _ = ctx
    cl.ensure_company_letters_schema(db)
    for i in range(1, 26):
        values, errs = cl.validate_letter_form(
            db, form(reference_no=f"MAX/LT/26/{i:03d}", recipient_name=f"Recipient {i}",
                     subject=("Quarterly audit" if i % 5 == 0 else f"Subject {i}"),
                     letter_type="Offer Letter" if i % 2 else "General Administration Letter",
                     letter_date=f"2026-10-{i:02d}"))
        assert not errs
        cl.save_letter(db, values, "t")
    db.commit()
    page1 = client.get(BASE).get_data(as_text=True)
    assert "25 letters" in page1 and "page 1 of 2" in page1 and page1.count(">Preview<") == 20
    assert "MAX/LT/26/025" in page1 and "MAX/LT/26/001" not in page1      # newest first
    page2 = client.get(f"{BASE}?page=2").get_data(as_text=True)
    assert "MAX/LT/26/001" in page2 and "MAX/LT/26/025" not in page2
    assert "page 3" not in client.get(f"{BASE}?page=9").get_data(as_text=True)    # clamped
    hit = client.get(f"{BASE}?q=audit").get_data(as_text=True)
    assert "5 letters" in hit and "Quarterly audit" in hit
    assert "13 letters" in client.get(f"{BASE}?type=Offer+Letter").get_data(as_text=True)
    assert "No letters match" in client.get(f"{BASE}?q=zzzz").get_data(as_text=True)
    row_actions = client.get(f"{BASE}?q=MAX/LT/26/005").get_data(as_text=True)
    for label in (">View<", ">Edit<", ">Preview<", ">Print<"):
        assert label in row_actions
    assert "print=1" in row_actions


# ───────────────────────────── permissions ─────────────────────────────


def test_anonymous_users_are_sent_to_login(ctx):
    _, app = ctx
    anon = app.test_client()
    for path in (BASE, f"{BASE}/new", f"{BASE}/1", f"{BASE}/1/edit", f"{BASE}/1/preview",
                 f"{BASE}/employees", f"{BASE}/employee/1"):
        r = anon.get(path)
        assert r.status_code == 302 and "/login" in r.headers["Location"], path
    assert anon.post(f"{BASE}/new", data=form()).status_code == 302


@pytest.mark.parametrize(
    "session_vals",
    [{"role": "guest"}, {"role": "user", "department": "HR & Payroll", "workflow_role": "maker"}],
)
def test_guest_and_base_hr_users_are_refused(ctx, client, session_vals, monkeypatch):
    import app as app_module
    db, _ = ctx
    client.post(f"{BASE}/new", data=form())                      # as admin
    monkeypatch.setattr(app_module, "is_admin_user", lambda: False)   # the test login is an admin
    with client.session_transaction() as sess:
        sess.update(session_vals)
    for path in (BASE, f"{BASE}/new", f"{BASE}/1", f"{BASE}/1/edit", f"{BASE}/1/preview"):
        r = client.get(path)
        assert r.status_code == 302 and "dashboard" in r.headers["Location"], path
    r = client.post(f"{BASE}/new", data=form(reference_no="MAX/LT/26/777"))
    assert r.status_code == 302 and count(db) == 1
    assert client.get(f"{BASE}/employees").status_code == 403
    assert client.get(f"{BASE}/employee/1").status_code == 403


def test_nav_entry_is_present_for_authorised_users(ctx, client):
    html = client.get(BASE).get_data(as_text=True)
    assert "Company Letters" in html and BASE in html


ALL_GETS = ("", "/new", "/1", "/1/edit", "/1/preview", "/employees", "/employee/1", "/1/content")


def _status(client, path):
    return client.get(BASE + path).status_code


def test_roles_decide_view_create_edit_print_issue(ctx, client):
    """Maker creates/edits, Checker and Approver can view and print, only Approver (or admin) issues."""
    db, app = ctx
    sid = add_staff(db, "Anita Menon", "EMP9001")
    client.post(f"{BASE}/new", data=form())                       # letter 1, created by admin
    users = {}
    for wf in ("Maker", "Checker", "Approver"):
        uid = make_user(db, wf.lower(), wf)
        grant_employee_data(db, uid)                              # employee-data access held by all three ...
        users[wf] = client_for(app, db, uid)                      # ... so only the letter permission differs

    # view + print: every role that has the tab
    for wf, c in users.items():
        assert _status(c, "") == 200 and _status(c, "/1") == 200 and _status(c, "/1/preview") == 200, wf
        html = c.get(BASE).get_data(as_text=True)
        assert ("New Letter" in html) == (wf == "Maker"), wf        # buttons follow the permission

    # create / edit / employee autofill: Maker only (administrators too)
    for wf, c in users.items():
        expect = 200 if wf == "Maker" else 302
        assert _status(c, "/new") == expect and _status(c, "/1/edit") == expect, wf
        expect_json = 200 if wf == "Maker" else 403
        assert _status(c, "/employees?q=ani") == expect_json and _status(c, f"/employee/{sid}") == expect_json, wf
        assert _status(c, "/1/content") == expect_json, wf
        before = count(db)
        r = c.post(f"{BASE}/new", data=form(reference_no=f"X-{wf}", subject=wf))
        assert (count(db) == before + 1) == (wf == "Maker"), wf     # the POST itself is refused, not just the page
        r = c.post(f"{BASE}/1/edit", data=form(subject=f"changed by {wf}"))
        changed = db.execute("SELECT subject FROM company_letters WHERE id=1").fetchone()[0] == f"changed by {wf}"
        assert changed == (wf == "Maker"), wf

    # issuing: Approver / administrator only, with the confirmation tick
    for wf in ("Maker", "Checker"):
        users[wf].post(f"{BASE}/1/issue", data={"confirm_content": "1"})
        assert db.execute("SELECT status FROM company_letters WHERE id=1").fetchone()[0] == "Draft", wf
    assert "Issue letter" not in users["Maker"].get(f"{BASE}/1").get_data(as_text=True)
    assert "Issue letter" in users["Approver"].get(f"{BASE}/1").get_data(as_text=True)
    users["Approver"].post(f"{BASE}/1/issue", data={})            # no confirmation
    assert db.execute("SELECT status FROM company_letters WHERE id=1").fetchone()[0] == "Draft"
    users["Approver"].post(f"{BASE}/1/issue", data={"confirm_content": "1"})
    row = db.execute("SELECT status, issued_by FROM company_letters WHERE id=1").fetchone()
    assert (row[0], row[1]) == ("Issued", "approver")


def test_department_tab_grants_are_enforced_on_the_server(ctx, client):
    db, app = ctx
    client.post(f"{BASE}/new", data=form())
    uid = make_user(db, "maker2", "Maker")
    c = client_for(app, db, uid)
    assert _status(c, "") == 200                                   # no tab rows saved = unrestricted (ERP default)
    grant_tabs(db, uid, ("office_inward", "Inward Register"))      # restricted to other tabs only
    for path in ("", "/new", "/1", "/1/preview"):
        assert _status(c, path) == 302, path
    for path in ("/employees?q=a", "/employee/1", "/1/content"):
        assert _status(c, path) == 403, path
    before = count(db)
    c.post(f"{BASE}/new", data=form(reference_no="X-9"))
    assert count(db) == before
    grant_tabs(db, uid, ("company_letters", "Company Letters"))
    assert _status(c, "") == 200 and _status(c, "/new") == 200 and _status(c, "/1/preview") == 200
    # a grant for the same tab under another department does not open this one
    grant_tabs(db, uid, ("office_inward", "Inward Register"))
    grant_tabs(db, uid, ("company_letters", "Company Letters"), dept="procurement")
    assert _status(c, "") == 302 and _status(c, "/new") == 302
    # administrators are never locked out by tab rows
    grant_tabs(db, 1, ("office_inward", "Inward Register"))
    assert _status(client, "") == 200 and _status(client, "/new") == 200


def test_tenant_and_company_restrictions_apply_to_letters_and_employees(ctx, client):
    import tenant_isolation
    db, app = ctx
    tenant_isolation.ensure_tenant_isolation_schema(db)
    cl.ensure_company_letters_schema(db)
    mine = make_user(db, "mk_a", "Maker", customer_id=1, company_id=10)
    other = make_user(db, "mk_b", "Maker", customer_id=2, company_id=20)
    sibling = make_user(db, "mk_c", "Maker", customer_id=1, company_id=11)
    for u in (mine, other, sibling):
        grant_employee_data(db, u)
    ca, cb, cc = (client_for(app, db, u) for u in (mine, other, sibling))
    s_a = add_staff(db, "Alpha Person", "A1")
    s_b = add_staff(db, "Beta Person", "B1")
    db.execute("UPDATE staff SET customer_id=1, company_id=10 WHERE id=?", (s_a,))
    db.execute("UPDATE staff SET customer_id=2, company_id=20 WHERE id=?", (s_b,))
    db.commit()
    set_counter(db, 116)

    assert ca.post(f"{BASE}/new", data=form(employee_id=str(s_a), reference_no="", subject="A letter")).status_code == 302
    row = dict(db.execute("SELECT * FROM company_letters").fetchone())
    assert (row["customer_id"], row["company_id"]) == (1, 10)

    # another tenant can neither see, open, edit, print, nor copy it
    assert "A letter" not in cb.get(BASE).get_data(as_text=True)
    for path in ("/1", "/1/edit", "/1/preview"):
        r = cb.get(BASE + path)
        assert r.status_code == 302 and r.headers["Location"].endswith(BASE), path
    assert cb.get(f"{BASE}/1/content").status_code == 404
    cb.post(f"{BASE}/1/edit", data=form(subject="hijacked"))
    assert db.execute("SELECT subject FROM company_letters").fetchone()[0] == "A letter"
    # ... nor use the other tenant's staff for autofill, nor attach them to a letter
    assert cb.get(f"{BASE}/employee/{s_a}").status_code == 404
    assert cb.get(f"{BASE}/employees?q=Person").get_json()["employees"][0]["staff_name"] == "Beta Person"
    assert [e["staff_name"] for e in ca.get(f"{BASE}/employees?q=Person").get_json()["employees"]] == ["Alpha Person"]
    html = cb.post(f"{BASE}/new", data=form(employee_id=str(s_a), reference_no="T-1")).get_data(as_text=True)
    assert "selected employee was not found" in html
    # same tenant, different company: restricted the same way
    assert "A letter" not in cc.get(BASE).get_data(as_text=True)
    assert cc.get(f"{BASE}/1").status_code == 302
    assert cc.get(f"{BASE}/employee/{s_a}").status_code == 404
    # the same reference text may exist in two tenants without clashing
    assert cb.post(f"{BASE}/new", data=form(reference_no="MAX/LT/26/117", subject="B letter")).status_code == 302
    assert db.execute("SELECT COUNT(*) FROM company_letters").fetchone()[0] == 2


def test_issued_letter_cannot_be_edited_by_a_maker_and_edit_returns_to_draft(ctx, client):
    db, app = ctx
    client.post(f"{BASE}/new", data=form())
    maker = client_for(app, db, make_user(db, "mk", "Maker"))
    client.post(f"{BASE}/1/issue", data={"confirm_content": "1"})
    assert db.execute("SELECT status FROM company_letters").fetchone()[0] == "Issued"
    assert maker.get(f"{BASE}/1/edit").status_code == 302
    maker.post(f"{BASE}/1/edit", data=form(subject="sneaky"))
    assert db.execute("SELECT subject FROM company_letters").fetchone()[0] == "Revised work order"
    client.post(f"{BASE}/1/edit", data=form(subject="approved change"))           # admin may; back to Draft
    row = db.execute("SELECT status, issued_by FROM company_letters").fetchone()
    assert (row[0], row[1]) == ("Draft", None)


# ───────────────────────────── offer letters ─────────────────────────────


def test_offer_letter_has_no_prewritten_terms_and_needs_user_content(ctx, client):
    db, _ = ctx
    sid = add_staff(db, "Anita Menon", "EMP9001", salary=30000, joining="2026-11-15")
    form_page = client.get(f"{BASE}/new").get_data(as_text=True)
    js = client.get("/static/js/company-letter-form.js").get_data(as_text=True)
    src = open(os.path.join(ROOT, "company_letters.py")).read()
    for needle in ("probation", "notice period", "terms and conditions", "pleased to offer", "OFFER_LETTER_BODY"):
        assert needle.lower() not in (form_page + js + src).lower(), needle
    assert "offer_body" not in form_page and "offerBody" not in js
    # choosing Offer Letter and an employee leaves the body empty; saving it blank is refused
    html = client.post(f"{BASE}/new", data=form(letter_type="Offer Letter", employee_id=str(sid),
                                               body_html="", reference_no="MAX/LT/26/200")).get_data(as_text=True)
    assert "body cannot be empty" in html and count(db) == 0
    assert 'id="cl-copy-from"' in form_page and 'id="cl-insert-facts"' in form_page


def test_offer_letter_prints_as_draft_until_issued(ctx, client):
    client.post(f"{BASE}/new", data=form(letter_type="Offer Letter", body_html="<p>Content chosen by the user.</p>"))
    draft = client.get(f"{BASE}/1/preview").get_data(as_text=True)
    assert "DRAFT" in draft and "Content chosen by the user." in draft
    html = client.get(f"{BASE}/1").get_data(as_text=True)
    assert "Draft" in html and "Issue letter" in html
    no_tick = client.post(f"{BASE}/1/issue", data={}, follow_redirects=True).get_data(as_text=True)
    assert "Tick the confirmation" in no_tick
    client.post(f"{BASE}/1/issue", data={"confirm_content": "1"})
    issued = client.get(f"{BASE}/1/preview").get_data(as_text=True)
    assert "DRAFT" not in issued
    assert "Issued" in client.get(f"{BASE}/1").get_data(as_text=True)


def test_copy_content_from_an_earlier_letter(ctx, client):
    client.post(f"{BASE}/new", data=form(body_html="<p>Standard wording <b>A</b>.</p>", subject="Earlier"))
    d = client.get(f"{BASE}/1/content").get_json()
    assert "Standard wording" in d["body_html"] and d["subject"] == "Earlier"
    assert client.get(f"{BASE}/99/content").status_code == 404
    page = client.get(f"{BASE}/new").get_data(as_text=True)
    assert "MAX/LT/26/001" in page and "Copy content from an earlier letter" in page


# ───────────────────────────── existing letters preserved ─────────────────────────────


def test_existing_office_letters_are_untouched_and_gain_print_options(ctx, client):
    db, _ = ctx
    client.post("/office/letters", data={
        "letter_type": "Official Letter", "letter_date": "2026-11-01", "to_name": "Old Recipient",
        "to_address": "Old Address", "subject": "Old subject", "body": "First paragraph.\n\nSecond paragraph.",
        "signed_by": "A. Signer"})
    before = [dict(r) for r in db.execute("SELECT * FROM office_letters")]
    assert len(before) == 1
    client.post(f"{BASE}/new", data=form())
    client.post(f"{BASE}/1/edit", data=form(subject="edited"))
    assert [dict(r) for r in db.execute("SELECT * FROM office_letters")] == before
    assert "Old subject" in client.get("/office/letters").get_data(as_text=True)
    lid = before[0]["id"]
    page = client.get(f"/office/letters/{lid}/print").get_data(as_text=True)
    assert "Print with MAXEK Letterhead" in page and "Print on Preprinted Paper" in page
    assert "First paragraph." in page and "Second paragraph." in page and "A. Signer" in page
    assert "assets/letterhead/maxek-letterhead.png" in page


# ───────────────────────────── print screen & assets ─────────────────────────────


def test_print_screen_has_both_options_and_the_managed_letterhead(ctx, client):
    client.post(f"{BASE}/new", data=form())
    page = client.get(f"{BASE}/1/preview").get_data(as_text=True)
    assert "Print with MAXEK Letterhead" in page and "Print on Preprinted Paper" in page
    assert 'src="/static/assets/letterhead/maxek-letterhead.png"' in page
    assert "D:\\" not in page and "OneDrive" not in page          # nothing depends on the local path
    css = client.get("/static/css/letter-print.css").get_data(as_text=True)
    assert "size: A4 portrait" in css and "margin: 0" in css
    assert "position: fixed" in css and "z-index: -1" in css       # behind the text, every page
    assert "print-color-adjust" in css
    assert "display: table-header-group" in css and "display: table-footer-group" in css
    assert ".lp-toolbar, .no-print { display: none" in css          # controls hidden when printing
    printed = css.split("@media print", 1)[1]
    assert "background-image" not in printed                       # nothing needs 'background graphics'
    assert client.get(f"{BASE}/999/preview", follow_redirects=False).status_code == 302


def test_managed_letterhead_is_the_supplied_image_unchanged():
    from PIL import Image
    assert hashlib.sha256(open(ASSET, "rb").read()).hexdigest().startswith(SUPPLIED_SHA256)
    im = Image.open(ASSET)
    assert im.size == (2482, 3508) and abs(im.size[0] / im.size[1] - 210 / 297) < 0.001   # A4 proportions (0.06% off exact; invisible)
    assert im.info.get("dpi", (0,))[0] > 299


def test_letterhead_is_served_by_the_app(ctx, client):
    r = client.get("/static/assets/letterhead/maxek-letterhead.png")
    assert r.status_code == 200 and r.mimetype == "image/png"
    assert hashlib.sha256(r.data).hexdigest() == hashlib.sha256(open(ASSET, "rb").read()).hexdigest()


# ───────────────────────────── real A4 PDF output ─────────────────────────────

LONG_BODY = "".join(
    f"<p>Paragraph {i}. " + "The quantities, rates and conditions referred to above shall remain as agreed. " * 6 + "</p>"
    for i in range(1, 15)
)


def _render_pdf(html: str, mode: str, path: str):
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1100, "height": 900})

        def handle(route):
            url = route.request.url
            if "/static/" in url:
                f = os.path.join(ROOT, "static", url.split("/static/", 1)[1].split("?")[0])
                route.fulfill(path=f, content_type=mimetypes.guess_type(f)[0] or "application/octet-stream")
            else:
                route.fulfill(body=html, content_type="text/html")

        page.route("**/*", handle)
        page.goto(f"http://example.test/letter?mode={mode}")
        page.wait_for_timeout(300)
        page.emulate_media(media="print")
        # print_background=False: the letterhead must not depend on "background graphics".
        page.pdf(path=path, prefer_css_page_size=True, print_background=False)
        browser.close()


def _words(pdf: str):
    if not shutil.which("pdftotext"):
        pytest.skip("pdftotext not available")
    xml = subprocess.run(["pdftotext", "-bbox", pdf, "-"], capture_output=True, text=True, check=True).stdout
    pages = xml.split("<page ")[1:]
    out = []
    for pg in pages:
        out.append([(float(a), float(b), float(c), float(d)) for a, b, c, d in
                    re.findall(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)"', pg)])
    return out


@pytest.mark.parametrize("body,expected_pages", [("<p>Short letter.</p>", 1), (LONG_BODY, 3)])
def test_pdf_output_letterhead_and_preprinted(ctx, client, tmp_path, body, expected_pages):
    pypdf = pytest.importorskip("pypdf")
    client.post(f"{BASE}/new", data=form(body_html=body))
    html = client.get(f"{BASE}/1/preview").get_data(as_text=True)

    with_lh = str(tmp_path / "lh.pdf")
    _render_pdf(html, "letterhead", with_lh)
    reader = pypdf.PdfReader(with_lh)
    n = len(reader.pages)
    assert n == expected_pages, f"unexpected page count {n}"            # no blank/extra pages
    for page in reader.pages:
        assert [round(float(x) / 72 * 25.4) for x in page.mediabox[2:]] == [210, 297]
        sizes = [im.image.size for im in page.images]
        assert (2482, 3508) in sizes                                   # letterhead on EVERY page, native size

    # All text stays inside the usable area (47 mm .. 273 mm), clear of header and footer art.
    top, bottom = 47 / 25.4 * 72 - 1, 273 / 25.4 * 72 + 1
    for words in _words(with_lh):
        assert words, "blank page"
        assert min(w[1] for w in words) >= top and max(w[3] for w in words) <= bottom
        assert min(w[0] for w in words) >= 20 / 25.4 * 72 - 1 and max(w[2] for w in words) <= (210 - 20) / 25.4 * 72 + 1

    # Signature block is never split: closing, name and designation share the last page.
    last = pypdf.PdfReader(with_lh).pages[-1].extract_text()
    assert "Yours faithfully" in last and "N. Khan" in last and "Director" in last

    plain = str(tmp_path / "plain.pdf")
    _render_pdf(html, "preprinted", plain)
    pr = pypdf.PdfReader(plain)
    assert len(pr.pages) == n                                          # same reserved spacing and flow
    assert all(len(p.images) == 0 for p in pr.pages)                   # content only
    assert [[(round(w[1]), round(w[3])) for w in ws] for ws in _words(plain)] == \
           [[(round(w[1]), round(w[3])) for w in ws] for ws in _words(with_lh)]


# ───────────────────────────── phone width (390 px) ─────────────────────────────


def _phone_page(html: str, width=390):
    """Open ``html`` in Chromium at phone width with the app's static files served from disk."""
    pw = pytest.importorskip("playwright.sync_api")
    p = pw.sync_playwright().start()
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": width, "height": 844})

    def handle(route):
        url = route.request.url
        if "/static/" in url:
            f = os.path.join(ROOT, "static", url.split("/static/", 1)[1].split("?")[0])
            if os.path.exists(f):
                return route.fulfill(path=f, content_type=mimetypes.guess_type(f)[0] or "application/octet-stream")
            return route.fulfill(status=404, body="")
        if url.startswith("http://example.test/page"):
            return route.fulfill(body=html, content_type="text/html")
        return route.abort()                                # no network: fonts/CDNs are not needed

    page.route("**/*", handle)
    page.goto("http://example.test/page")
    page.wait_for_timeout(400)
    return p, browser, page


def _overflow(page):
    return page.evaluate("document.documentElement.scrollWidth")


def test_phone_width_register_form_view_and_preview(ctx, client):
    client.post(f"{BASE}/new", data=form(reference_no="MAX/LT/26/001", body_html="<p>Body.</p>"))
    pages = {name: client.get(BASE + path).get_data(as_text=True) for name, path in
             (("register", ""), ("form", "/new"), ("view", "/1"), ("preview", "/1/preview"))}
    for name, html in pages.items():
        p, browser, page = _phone_page(html)
        try:
            assert _overflow(page) <= 390, f"{name}: page scrolls sideways ({_overflow(page)}px)"
            if name != "preview":
                # the shell sidebar must not eat the width: the main card keeps most of the screen
                card = page.evaluate(
                    "(() => { const c = document.querySelector('.erp-form-card, .erp-table-panel');"
                    " return c ? c.getBoundingClientRect().width : 0; })()")
                assert card >= 300, f"{name}: content is only {card}px wide (sidebar crowding)"
                assert page.evaluate("!!document.querySelector('[data-pro-dash-shell].is-sidebar-collapsed')"), name
            if name == "register":
                assert page.evaluate("getComputedStyle(document.querySelector('.cl-reg thead')).display") == "none"
                actions = page.locator(".cl-actions a").all()
                assert len(actions) >= 4 and all(a.is_visible() for a in actions)   # View/Edit/Preview/Print reachable
                box = page.locator(".cl-actions").first.bounding_box()
                assert box["x"] >= 0 and box["x"] + box["width"] <= 390
            if name == "form":
                for sel in ("#cl-editor", "#cl-copy-from", "#cl-insert-facts", "button[type=submit]"):
                    b = page.locator(sel).first.bounding_box()
                    assert b and b["x"] >= 0 and b["x"] + b["width"] <= 390, sel
            if name == "preview":
                w = page.evaluate("document.querySelector('.lp-sheet').getBoundingClientRect().width")
                assert 300 <= w <= 390, f"sheet is {w}px"                     # scaled to fit, not clipped
                assert page.evaluate("document.getElementById('lp-stage').classList.contains('lp-scaled')")
                for btn in page.locator(".lp-toolbar button").all():
                    b = btn.bounding_box()
                    assert b["x"] >= 0 and b["x"] + b["width"] <= 391
                # printing is never scaled: A4 width, no transform
                page.emulate_media(media="print")
                pw_mm = page.evaluate("document.querySelector('.lp-sheet').getBoundingClientRect().width") / 96 * 25.4
                assert abs(pw_mm - 210) < 0.5
                assert page.evaluate("getComputedStyle(document.querySelector('.lp-sheet')).transform") == "none"
        finally:
            browser.close()
            p.stop()


# ───────────────────────────── employee-data access for autofill ─────────────────────────────


def test_autofill_needs_employee_data_access_as_well_as_letter_create(ctx, client):
    db, app = ctx
    sid = add_staff(db, "Anita Menon", "EMP9001", salary=30000)
    db.execute("UPDATE staff SET designation='Site Engineer' WHERE id=?", (sid,))
    db.commit()
    uid = make_user(db, "maker_nohr", "Maker", department="Procurement")
    c = client_for(app, db, uid)

    # letter-create alone: can write letters, cannot read employee records
    assert _status(c, "/new") == 200
    assert _status(c, "/employees?q=ani") == 403 and _status(c, f"/employee/{sid}") == 403
    page = c.get(f"{BASE}/new").get_data(as_text=True)
    assert 'id="cl-emp-search"' not in page and 'id="cl-insert-facts"' not in page
    assert "Anita" not in page
    # a forged employee_id is neither looked up nor stored, and does not leak whether it exists
    set_counter(db, 10)
    r = c.post(f"{BASE}/new", data=form(reference_no="", employee_id=str(sid), subject="no link"))
    assert r.status_code == 302
    assert db.execute("SELECT employee_id FROM company_letters WHERE subject='no link'").fetchone()[0] is None

    # an existing employee link (made by someone allowed) is kept when this user edits other fields,
    # but the employee's name is not shown to them
    client.post(f"{BASE}/new", data=form(reference_no="", employee_id=str(sid), subject="linked"))
    lid = db.execute("SELECT id FROM company_letters WHERE subject='linked'").fetchone()[0]
    assert db.execute("SELECT employee_id FROM company_letters WHERE id=?", (lid,)).fetchone()[0] == sid
    c.post(f"{BASE}/{lid}/edit", data=form(reference_no=db.execute("SELECT reference_no FROM company_letters WHERE id=?", (lid,)).fetchone()[0], subject="linked, edited", employee_id=""))
    row = db.execute("SELECT employee_id, subject FROM company_letters WHERE id=?", (lid,)).fetchone()
    assert (row[0], row[1]) == (sid, "linked, edited")
    assert "Anita Menon" not in c.get(f"{BASE}/{lid}").get_data(as_text=True)
    assert "Anita Menon" in client.get(f"{BASE}/{lid}").get_data(as_text=True)        # administrator sees it

    # an explicit Employee Master grant (HR & Payroll tab permissions) opens it ...
    grant_employee_data(db, uid)
    assert _status(c, "/employees?q=ani") == 200 and _status(c, f"/employee/{sid}") == 200
    assert 'id="cl-emp-search"' in c.get(f"{BASE}/new").get_data(as_text=True)
    assert "Anita Menon" in c.get(f"{BASE}/{lid}").get_data(as_text=True)
    # ... a grant under some other department does not
    other = make_user(db, "maker_other", "Maker", department="Procurement")
    db.execute("INSERT INTO user_tab_permissions(user_id, department_slug, tab_key, endpoint, label, granted, updated_at) "
               "VALUES(?,?,?,?,?,1,'x')", (other, "procurement", "staff::Employee Master", "staff", "Employee Master"))
    db.commit()
    assert _status(client_for(app, db, other), "/employees?q=ani") == 403


def test_hr_department_staff_and_administrators_have_employee_data_access(ctx, client):
    db, app = ctx
    sid = add_staff(db, "Anita Menon", "EMP9001")
    # works in HR & Payroll (a manager-type role: base HR makers are refused Company Letters altogether)
    hr = client_for(app, db, make_user(db, "hr_mgr", "Maker", role="Manager", department="HR & Payroll"))
    assert _status(hr, "/employees?q=ani") == 200 and _status(hr, f"/employee/{sid}") == 200
    assert client.get(f"{BASE}/employees?q=ani").status_code == 200                     # administrator
    # access to employee data without letter-create permission is still not enough
    checker = client_for(app, db, make_user(db, "hr_chk", "Checker", role="Manager", department="HR & Payroll"))
    assert _status(checker, "/employees?q=ani") == 403


# ───────────────────────────── numbering stays configurable ─────────────────────────────

NUM = f"{BASE}/numbering"


def test_administrator_can_configure_prefix_layout_year_basis_and_last_number(ctx, client):
    db, _ = ctx
    page = client.get(BASE).get_data(as_text=True)
    assert "Letter numbering settings" in page and "not set yet" in page                # nothing assumed
    r = client.post(NUM, data={"prefix": "MAX/LT", "pattern": "{prefix}/{yy}/{seq:03d}", "basis": "financial", "last_number": "116"})
    assert r.status_code == 302
    assert cl.suggest_reference(db, "2026-11-03")["reference"] == "MAX/LT/26/117"
    assert "next number: <span>MAX/LT/26/117" in client.get(BASE).get_data(as_text=True)
    # a different real sequence and layout are accepted without code changes
    client.post(NUM, data={"prefix": "MXK", "pattern": "{prefix}-{fy}-{seq:04d}", "basis": "financial", "last_number": "40"})
    assert cl.suggest_reference(db, "2026-11-03")["reference"] == "MXK-2627-0041"
    # existing letters are never renumbered
    client.post(f"{BASE}/new", data=form(reference_no="", subject="after settings"))
    assert db.execute("SELECT reference_no FROM company_letters").fetchone()[0] == "MXK-2627-0041"
    client.post(NUM, data={"prefix": "MAX/LT", "pattern": "{prefix}/{yy}/{seq:03d}", "basis": "financial", "last_number": "116"})
    assert db.execute("SELECT reference_no FROM company_letters").fetchone()[0] == "MXK-2627-0041"


def test_calendar_year_basis_and_new_year_inherits_the_configured_layout(ctx, client):
    db, _ = ctx
    client.post(NUM, data={"prefix": "MAX/LT", "pattern": "{prefix}/{yy}/{seq:03d}", "basis": "calendar", "last_number": "9"})
    assert cl.get_year_basis(db) == "calendar"
    assert cl.suggest_reference(db, "2027-01-15")["fiscal_year"] == "CY2027"
    assert cl.suggest_reference(db, "2026-12-31")["reference"] == "MAX/LT/26/010"        # December is still 2026
    assert cl.suggest_reference(db, "2027-01-01")["reference"] == ""                       # new year: number must be entered
    client.post(f"{BASE}/new", data=form(reference_no="MAX/LT/27/001", letter_date="2027-01-02"))
    assert cl.suggest_reference(db, "2027-02-01")["reference"] == "MAX/LT/27/002"          # inherits prefix and layout
    # switching back to financial years uses its own counter
    client.post(NUM, data={"prefix": "MAX/LT", "pattern": "{prefix}/{yy}/{seq:03d}", "basis": "financial", "last_number": "116"})
    assert cl.suggest_reference(db, "2026-11-03")["reference"] == "MAX/LT/26/117"


@pytest.mark.parametrize(
    "data,message",
    [
        ({"prefix": "", "pattern": "{prefix}/{seq:03d}", "basis": "financial", "last_number": "1"}, "Prefix is required"),
        ({"prefix": "X", "pattern": "{prefix}/001", "basis": "financial", "last_number": "1"}, "must contain {seq"),
        ({"prefix": "X", "pattern": "{prefix}/{bogus}/{seq}", "basis": "financial", "last_number": "1"}, "may only use"),
        ({"prefix": "X", "pattern": "{prefix}/{seq:03d}", "basis": "lunar", "last_number": "1"}, "financial year or calendar"),
        ({"prefix": "X", "pattern": "{prefix}/{seq:03d}", "basis": "financial", "last_number": "-3"}, "whole number"),
        ({"prefix": "X", "pattern": "{prefix}/{seq:03d}", "basis": "financial", "last_number": "abc"}, "whole number"),
    ],
)
def test_numbering_settings_validation(ctx, client, data, message):
    db, _ = ctx
    r = client.post(NUM, data=data, follow_redirects=True)
    assert message in r.get_data(as_text=True)
    assert cl.get_year_basis(db) == "financial"
    assert db.execute("SELECT COUNT(*) FROM document_number_sequences WHERE doc_type='company_letter_no' AND current_sequence>0").fetchone()[0] == 0


def test_only_administrators_can_change_numbering(ctx, client):
    db, app = ctx
    cl.ensure_company_letters_schema(db)
    maker = client_for(app, db, make_user(db, "mk_num", "Maker"))
    approver = client_for(app, db, make_user(db, "ap_num", "Approver"))
    for c in (maker, approver):
        assert "Letter numbering settings" not in c.get(BASE).get_data(as_text=True)
        c.post(NUM, data={"prefix": "HACK", "pattern": "{prefix}/{seq}", "basis": "calendar", "last_number": "999"})
    assert cl.get_year_basis(db) == "financial"
    assert db.execute("SELECT COUNT(*) FROM document_number_sequences WHERE prefix='HACK'").fetchone()[0] == 0
    assert client.post(NUM, data={"prefix": "OK", "pattern": "{prefix}/{seq:03d}", "basis": "financial", "last_number": "5"}).status_code == 302
    assert cl.suggest_reference(db, "2026-11-03")["reference"] == "OK/006"
    anon = app.test_client()
    assert anon.post(NUM, data={"prefix": "X"}).status_code == 302 and "/login" in anon.post(NUM, data={}).headers["Location"]
