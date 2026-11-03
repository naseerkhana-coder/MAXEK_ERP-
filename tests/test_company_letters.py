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
        ("reference_no", "", "Reference number is required"),
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


def test_suggested_reference_continues_per_year(ctx, client):
    db, _ = ctx
    cl.ensure_company_letters_schema(db)
    assert cl.suggest_reference(db, "2026-11-03") == "MAX/LT/26/001"
    client.post(f"{BASE}/new", data=form(reference_no="MAX/LT/26/116"))
    client.post(f"{BASE}/new", data=form(reference_no="MAX/LT/27/005"))
    client.post(f"{BASE}/new", data=form(reference_no="custom-ref"))   # free-form numbers are allowed
    assert cl.suggest_reference(db, "2026-01-01") == "MAX/LT/26/117"
    assert cl.suggest_reference(db, "2027-06-01") == "MAX/LT/27/006"
    assert cl.suggest_reference(db, "2028-06-01") == "MAX/LT/28/001"
    assert 'value="MAX/LT/' in client.get(f"{BASE}/new").get_data(as_text=True)


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
    assert "Site Engineer" in d["offer_body_html"] and "15/11/2026" in d["offer_body_html"]
    assert "30000" not in str(d)                                   # salary is never auto-filled
    assert client.get(f"{BASE}/employee/99999").status_code == 404

    client.post(f"{BASE}/new", data=form(employee_id=str(sid), recipient_name="Anita Menon"))
    assert db.execute("SELECT employee_id FROM company_letters").fetchone()[0] == sid
    assert "Anita Menon (EMP9001)" in client.get(f"{BASE}/1/edit").get_data(as_text=True)
    assert "Anita Menon" in client.get(f"{BASE}/1").get_data(as_text=True)


def test_unknown_employee_id_is_dropped_not_saved(ctx, client):
    db, _ = ctx
    html = client.post(f"{BASE}/new", data=form(employee_id="424242")).get_data(as_text=True)
    assert "selected employee no longer exists" in html and count(db) == 0


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
        sess["role"] = session_vals["role"]
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
