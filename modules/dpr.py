"""Daily Progress Report (DPR) module for MAXEK ERP."""

import json
from datetime import date, datetime

import pandas as pd
import streamlit as st

from modules.database import (
    DATE_FMT,
    generate_id,
    get_boq_progress_stats,
    get_conn,
    load_company_staff_for_select,
    load_lookup,
    load_project_boq_by_project,
    load_project_names,
    resolve_project_id,
)
from modules.dpr_measurements import (
    build_measurement_record,
    compute_measurement,
    is_steel_boq_entry,
    normalize_boq_unit,
    unit_entry_label,
)
from modules.dpr_boq_lines import (
    build_boq_line,
    enrich_boq_lines_for_save,
    flatten_measurements,
    header_summary_from_boq_lines,
    line_progress_qty,
    load_boq_lines_for_dpr,
    load_legacy_single_boq_line,
    persist_boq_lines,
    delete_boq_lines_for_dpr,
)
from modules.dpr_steel_shapes import (
    STEEL_DIA_MM_OPTIONS,
    build_steel_measurement_record,
    compute_steel_measurement,
    get_steel_shape,
    load_steel_shapes,
    parse_steel_dia_mm,
    save_custom_steel_shape,
    steel_shape_diagram_path,
)
from modules.ui import render_delete_confirm_dialog, start_delete_confirm
from modules.pages import _save_upload

# Legacy labels for old DPR rows only
LEGACY_MEASUREMENT_TYPES = [
    "Concrete",
    "Shuttering",
    "Brick Work",
    "Straight Bar",
    "Ring",
    "Bent Bar",
]
DPR_STATUS_DRAFT = "Draft"
DPR_STATUS_SUBMITTED = "Submitted"
DPR_STATUS_ENGINEER_APPROVED = "Engineer Approved"
DPR_STATUS_CLIENT_APPROVED = "Client Approved"
DPR_STATUS_BILLED = "Billed"
DPR_STATUS_REJECTED = "Rejected"


def _avg_dim(value_1, value_2):
    values = [float(v) for v in (value_1, value_2) if v is not None and float(v) > 0]
    if not values:
        return 0.0
    return sum(values) / len(values)


def _steel_weight_ton(nos, length_m, dia_mm, multiplier=1.0):
    if nos <= 0 or length_m <= 0 or dia_mm <= 0:
        return 0.0
    kg = (float(dia_mm) ** 2 * float(length_m) * float(nos) * float(multiplier)) / 162.0
    return kg / 1000.0


def calculate_measurement_quantity(measurement_type, fields):
    w1 = fields.get("width_1", 0.0)
    w2 = fields.get("width_2", 0.0)
    l1 = fields.get("length_1", 0.0)
    l2 = fields.get("length_2", 0.0)
    height = fields.get("height", 0.0)
    depth = fields.get("depth", 0.0)
    nos = fields.get("nos", 0.0)
    dia_mm = fields.get("dia_mm", 0.0)
    bend = fields.get("bend", 1.0) or 1.0

    avg_w = _avg_dim(w1, w2)
    avg_l = _avg_dim(l1, l2)

    if measurement_type == "Concrete":
        h = depth if depth > 0 else height
        qty = avg_w * avg_l * h
        unit = "M3"
    elif measurement_type == "Brick Work":
        h = depth if depth > 0 else height
        qty = avg_w * avg_l * h
        unit = "M3"
    elif measurement_type == "Shuttering":
        qty = avg_l * height
        unit = "SQM"
    elif measurement_type == "Straight Bar":
        length_m = avg_l if avg_l > 0 else l1
        qty = _steel_weight_ton(nos, length_m, dia_mm)
        unit = "Ton"
        avg_w, avg_l = 0.0, length_m
    elif measurement_type == "Ring":
        w = avg_w if avg_w > 0 else w1
        l = avg_l if avg_l > 0 else l1
        qty = _steel_weight_ton(nos, w * l, dia_mm)
        unit = "Ton"
    elif measurement_type == "Bent Bar":
        l1v = l1 or avg_l
        l2v = l2 or depth or height
        qty = _steel_weight_ton(nos, l1v, dia_mm, multiplier=bend)
        unit = "Ton"
        avg_l = l1v
    else:
        qty = 0.0
        unit = ""

    return {
        "avg_width": avg_w,
        "avg_length": avg_l,
        "calculated_quantity": round(qty, 4),
        "unit": unit,
    }


def _ensure_dpr_drafts():
    st.session_state.setdefault("dpr_draft_boq_lines", [])
    st.session_state.setdefault("dpr_work_measurements", [])
    st.session_state.setdefault("dpr_draft_measurements", [])
    st.session_state.setdefault("dpr_draft_manpower", [])
    st.session_state.setdefault("dpr_editing_boq_line_id", None)


def _reset_dpr_drafts():
    st.session_state.dpr_draft_boq_lines = []
    st.session_state.dpr_work_measurements = []
    st.session_state.dpr_draft_measurements = []
    st.session_state.dpr_draft_manpower = []
    st.session_state.dpr_editing_boq_line_id = None


def _reset_work_measurements():
    st.session_state.dpr_work_measurements = []


def _load_dpr_trade_options():
    trades = set()
    for name in load_lookup("designations", "designation_name"):
        if name:
            trades.add(str(name).strip())
    conn = get_conn()
    for sql in (
        "SELECT DISTINCT trade_name FROM workers WHERE COALESCE(trade_name, '') != ''",
        "SELECT DISTINCT labour_type FROM subcontractor_labour_rates WHERE COALESCE(labour_type, '') != ''",
        "SELECT DISTINCT labour_type FROM dpr_manpower WHERE COALESCE(labour_type, '') != ''",
    ):
        try:
            for row in conn.execute(sql).fetchall():
                trades.add(str(row[0]).strip())
        except Exception:
            pass
    conn.close()
    for default in (
        "Mason",
        "Carpenter",
        "Bar Bender",
        "Steel Fixer",
        "Helper",
        "Electrician",
        "Plumber",
        "Painter",
        "Fitter",
        "Welder",
        "Supervisor",
        "Foreman",
    ):
        trades.add(default)
    return sorted(trades, key=str.lower)


def _restore_measurement_ui_from_line(line: dict):
    """When editing a BOQ line, restore Normal/Average inputs from saved measurements."""
    bid = line.get("boq_item_id") or ""
    suffix = _measurement_state_suffix(bid)
    for m in reversed(line.get("measurements") or []):
        dims = {}
        try:
            dims = json.loads(m.get("dimensions_json") or "{}")
        except (TypeError, json.JSONDecodeError):
            dims = {}
        method = dims.get("method") or m.get("measurement_method") or "Normal"
        if method == "Average":
            st.session_state.dpr_measurement_method = "Average"
            st.session_state[_lengths_key(bid)] = list(dims.get("lengths") or [0.0])
            st.session_state[_widths_key(bid)] = list(dims.get("widths") or [0.0])
            if dims.get("depths"):
                st.session_state[_depths_key(bid)] = list(dims.get("depths"))
            st.session_state[f"dpr_entry_qty_{suffix}"] = float(
                dims.get("qty") or m.get("qty") or 1
            )
            return
    st.session_state.dpr_measurement_method = "Normal"
    if line.get("measurements"):
        m0 = line["measurements"][0]
        st.session_state[f"dpr_norm_length_{suffix}"] = float(m0.get("avg_length") or 0)
        st.session_state[f"dpr_norm_width_{suffix}"] = float(m0.get("avg_width") or 0)
        st.session_state[f"dpr_norm_depth_{suffix}"] = float(m0.get("avg_depth") or 0)
        st.session_state[f"dpr_entry_qty_{suffix}"] = float(m0.get("qty") or 1)


def _apply_dpr_pending_ui_state():
    """Apply queued BOQ edit state before widgets with matching keys are drawn."""
    if "dpr_pending_boq_row_id" in st.session_state:
        st.session_state.dpr_boq_row_id = st.session_state.pop("dpr_pending_boq_row_id")
    if "dpr_pending_work_measurements" in st.session_state:
        st.session_state.dpr_work_measurements = st.session_state.pop("dpr_pending_work_measurements")
    if "dpr_pending_editing_boq_line_id" in st.session_state:
        st.session_state.dpr_editing_boq_line_id = st.session_state.pop("dpr_pending_editing_boq_line_id")
    if "dpr_pending_edit_line" in st.session_state:
        _restore_measurement_ui_from_line(st.session_state.pop("dpr_pending_edit_line"))


def _queue_edit_boq_line(line: dict, project_name: str):
    row_id = line.get("boq_row_id") or _resolve_boq_row_key(project_name, line.get("boq_item_id"))
    st.session_state.dpr_pending_boq_row_id = row_id
    st.session_state.dpr_pending_work_measurements = list(line.get("measurements") or [])
    st.session_state.dpr_pending_editing_boq_line_id = line.get("line_id")
    st.session_state.dpr_pending_edit_line = line
    st.rerun()


def _all_dpr_measurements():
    lines = st.session_state.get("dpr_draft_boq_lines") or []
    out = []
    for line in lines:
        out.extend(line.get("measurements") or [])
    out.extend(st.session_state.get("dpr_work_measurements") or [])
    return out


def _dpr_boq_line_count():
    return len(st.session_state.get("dpr_draft_boq_lines") or [])


def _commit_current_boq_to_dpr(
    boq_row_pick,
    boq_item_id,
    boq_number,
    boq_desc,
    unit,
    billing_measurement,
    stats,
) -> bool:
    if not boq_item_id:
        st.error("Select a BOQ item first.")
        return False
    work = list(st.session_state.get("dpr_work_measurements") or [])
    if not work:
        st.error("Add at least one measurement for this BOQ item, then save the BOQ line.")
        return False

    line = build_boq_line(
        boq_row_pick,
        boq_item_id,
        boq_number,
        boq_desc,
        unit,
        billing_measurement,
        stats,
        work,
    )
    editing_id = st.session_state.get("dpr_editing_boq_line_id")
    lines = list(st.session_state.get("dpr_draft_boq_lines") or [])
    if editing_id:
        replaced = False
        for idx, existing in enumerate(lines):
            if existing.get("line_id") == editing_id:
                line["line_id"] = editing_id
                lines[idx] = line
                replaced = True
                break
        if not replaced:
            line["line_id"] = generate_id("DBL", "dpr_boq_lines")
            lines.append(line)
        st.session_state.dpr_editing_boq_line_id = None
    else:
        for existing in lines:
            if existing.get("boq_item_id") == boq_item_id:
                st.error(
                    f"BOQ {boq_number} is already on this DPR. Use Edit on that line to change measurements."
                )
                return False
        line["line_id"] = generate_id("DBL", "dpr_boq_lines")
        lines.append(line)

    st.session_state.dpr_draft_boq_lines = lines
    st.session_state.dpr_work_measurements = []
    st.session_state.dpr_draft_measurements = flatten_measurements(lines)
    return True


def _measurement_state_suffix(boq_item_id: str = "") -> str:
    return str(boq_item_id or "default").strip() or "default"


def _lengths_key(boq_item_id: str) -> str:
    return f"dpr_lengths_{_measurement_state_suffix(boq_item_id)}"


def _widths_key(boq_item_id: str) -> str:
    return f"dpr_widths_{_measurement_state_suffix(boq_item_id)}"


def _depths_key(boq_item_id: str) -> str:
    return f"dpr_depths_{_measurement_state_suffix(boq_item_id)}"


def _init_average_dimension_lists(boq_item_id: str):
    lk, wk, dk = _lengths_key(boq_item_id), _widths_key(boq_item_id), _depths_key(boq_item_id)
    st.session_state.setdefault(lk, [0.0])
    st.session_state.setdefault(wk, [0.0])
    st.session_state.setdefault(dk, [0.0])


def _reset_dpr_measurement_session(unit_family="SQM", boq_item_id=""):
    st.session_state.dpr_unit_family = unit_family
    st.session_state.dpr_measurement_method = "Normal"
    suffix = _measurement_state_suffix(boq_item_id)
    st.session_state[_lengths_key(boq_item_id)] = [0.0]
    st.session_state[_widths_key(boq_item_id)] = [0.0]
    st.session_state[_depths_key(boq_item_id)] = [0.0]
    st.session_state[f"dpr_norm_length_{suffix}"] = 0.0
    st.session_state[f"dpr_norm_width_{suffix}"] = 0.0
    st.session_state[f"dpr_norm_depth_{suffix}"] = 0.0
    st.session_state[f"dpr_entry_qty_{suffix}"] = 1.0


def _dim_short_label(section_label, idx):
    prefix = {"Length": "L", "Width": "W", "Depth": "D"}.get(section_label, section_label[:1])
    return f"{prefix}{idx + 1}"


def _render_dimension_list(section_label, state_key):
    values = list(st.session_state.get(state_key) or [0.0])
    if not values:
        values = [0.0]
    st.session_state[state_key] = values
    short = {"Length": "L", "Width": "W", "Depth": "D"}.get(section_label, section_label[:1])
    st.caption(f"{short} (avg)")

    slot_count = max(len(values), 1)
    col_spec = [0.55] * min(slot_count, 6)
    if len(values) > 6:
        col_spec = [0.55] * 6
    col_spec += [0.45, 0.45, 3]
    cols = st.columns(col_spec)
    for idx in range(min(len(values), 6)):
        values[idx] = cols[idx].number_input(
            _dim_short_label(section_label, idx),
            min_value=0.0,
            step=0.01,
            value=float(values[idx] or 0),
            key=f"{state_key}_input_{idx}",
            label_visibility="collapsed",
        )
    btn_i = min(len(values), 6)
    if cols[btn_i].button("+", key=f"{state_key}_add", help=f"Add {section_label.lower()}"):
        values.append(0.0)
        st.session_state[state_key] = values
        st.rerun()
    if len(values) > 1 and cols[btn_i + 1].button("−", key=f"{state_key}_rm_last", help="Remove last"):
        values.pop()
        st.session_state[state_key] = values
        st.rerun()
    st.session_state[state_key] = values


def _collect_measurement_inputs(unit_family, method, boq_item_id=""):
    suffix = _measurement_state_suffix(boq_item_id)
    if method == "Normal":
        lengths = [float(st.session_state.get(f"dpr_norm_length_{suffix}") or 0)]
        widths = [float(st.session_state.get(f"dpr_norm_width_{suffix}") or 0)]
        depths = (
            [float(st.session_state.get(f"dpr_norm_depth_{suffix}") or 0)]
            if unit_family == "M3"
            else []
        )
    else:
        lengths = list(st.session_state.get(_lengths_key(boq_item_id)) or [0.0])
        widths = list(st.session_state.get(_widths_key(boq_item_id)) or [0.0])
        depths = (
            list(st.session_state.get(_depths_key(boq_item_id)) or [0.0])
            if unit_family == "M3"
            else []
        )
    qty = float(st.session_state.get(f"dpr_entry_qty_{suffix}") or 0)
    return lengths, widths, depths, qty


def _render_measurement_preview(calc):
    lines = calc.get("preview_lines") or ["Enter values to preview."]
    final_line = lines[-1] if lines else ""
    detail = "<br>".join(lines[:-1]) if len(lines) > 1 else ""
    st.markdown(
        f"""
        <div class="maxek-dpr-preview">
          <span class="maxek-dpr-preview-title">Preview</span>
          {f'<span class="maxek-dpr-preview-detail">{detail}</span>' if detail else ''}
          <span class="maxek-dpr-preview-final">{final_line}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_boq_measurement_entry(unit_family, boq_item_id=""):
    st.session_state.setdefault("dpr_measurement_method", "Normal")
    unit_family = normalize_boq_unit(unit_family)
    suffix = _measurement_state_suffix(boq_item_id)
    st.markdown('<div class="maxek-dpr-measure-compact">', unsafe_allow_html=True)
    st.caption(unit_entry_label(unit_family))
    method = st.radio(
        "Method",
        ["Normal", "Average"],
        horizontal=True,
        key="dpr_measurement_method",
        label_visibility="collapsed",
    )
    if method == "Average":
        _init_average_dimension_lists(boq_item_id)

    if unit_family in {"NOS", "KG", "TON"}:
        c1, _ = st.columns([0.6, 4])
        c1.number_input("Qty", min_value=0.0, step=0.01, key=f"dpr_entry_qty_{suffix}", label_visibility="collapsed")
    elif method == "Normal":
        if unit_family == "SQM":
            c1, c2, c3, _ = st.columns([0.55, 0.55, 0.5, 4])
            c1.number_input("L", min_value=0.0, step=0.01, key=f"dpr_norm_length_{suffix}")
            c2.number_input("W", min_value=0.0, step=0.01, key=f"dpr_norm_width_{suffix}")
            c3.number_input("Qty", min_value=0.0, step=0.01, key=f"dpr_entry_qty_{suffix}")
        elif unit_family == "M3":
            c1, c2, c3, c4, _ = st.columns([0.55, 0.55, 0.55, 0.5, 3])
            c1.number_input("L", min_value=0.0, step=0.01, key=f"dpr_norm_length_{suffix}")
            c2.number_input("W", min_value=0.0, step=0.01, key=f"dpr_norm_width_{suffix}")
            c3.number_input("D", min_value=0.0, step=0.01, key=f"dpr_norm_depth_{suffix}")
            c4.number_input("Qty", min_value=0.0, step=0.01, key=f"dpr_entry_qty_{suffix}")
        elif unit_family == "RM":
            c1, c2, _ = st.columns([0.55, 0.5, 4])
            c1.number_input("L", min_value=0.0, step=0.01, key=f"dpr_norm_length_{suffix}")
            c2.number_input("Qty", min_value=0.0, step=0.01, key=f"dpr_entry_qty_{suffix}")
        else:
            c1, c2, c3, _ = st.columns([0.55, 0.55, 0.5, 4])
            c1.number_input("L", min_value=0.0, step=0.01, key=f"dpr_norm_length_{suffix}")
            c2.number_input("W", min_value=0.0, step=0.01, key=f"dpr_norm_width_{suffix}")
            c3.number_input("Qty", min_value=0.0, step=0.01, key=f"dpr_entry_qty_{suffix}")
    else:
        if unit_family in {"SQM", "M3", "RM"}:
            _render_dimension_list("Length", _lengths_key(boq_item_id))
        if unit_family in {"SQM", "M3"}:
            _render_dimension_list("Width", _widths_key(boq_item_id))
        if unit_family == "M3":
            _render_dimension_list("Depth", _depths_key(boq_item_id))
        if unit_family in {"SQM", "M3", "RM"}:
            q1, _ = st.columns([0.5, 4])
            q1.number_input("Qty", min_value=0.0, step=0.01, key=f"dpr_entry_qty_{suffix}")

    lengths, widths, depths, qty = _collect_measurement_inputs(unit_family, method, boq_item_id)
    calc = compute_measurement(unit_family, lengths, widths, depths, qty, method)
    _render_measurement_preview(calc)
    st.markdown("</div>", unsafe_allow_html=True)
    return calc


def _is_steel_draft_row(measurement_row):
    try:
        payload = json.loads(measurement_row.get("dimensions_json") or "{}")
        return bool(payload.get("steel_shape_code"))
    except (TypeError, json.JSONDecodeError):
        return False


def _render_steel_dia_select(key_prefix: str = "entry"):
    dia_labels = [f"{d} mm" for d in STEEL_DIA_MM_OPTIONS] + ["Other"]
    pick = st.selectbox("Dia (mm)", dia_labels, key=f"dpr_{key_prefix}_steel_dia_pick")
    if pick == "Other":
        return st.number_input(
            "Dia — other (mm)",
            min_value=0.0,
            step=1.0,
            key=f"dpr_{key_prefix}_steel_dia_other",
        )
    return parse_steel_dia_mm(pick)


def _render_steel_dimension_inputs(shape_code: str, shape: dict, key_prefix: str = "entry") -> dict:
    dimensions = {}
    terms = shape.get("terms") or []
    layout = (shape.get("layout") or "").lower()
    is_ring = shape_code == "RING" or layout == "ring_6" or len(terms) == 6

    if is_ring and len(terms) >= 6:
        st.caption("Ring (mm)")
        row_a = st.columns([0.55, 0.55, 0.55, 3])
        row_b = st.columns([0.55, 0.55, 0.55, 3])
        short_labels = ("L1", "L2", "W1", "W2", "B1", "B2")
        for idx, term in enumerate(terms[:6]):
            col = row_a[idx] if idx < 3 else row_b[idx - 3]
            dimensions[term["key"]] = col.number_input(
                short_labels[idx],
                min_value=0.0,
                step=1.0,
                key=f"dpr_{key_prefix}_steel_dim_{shape_code}_{term['key']}",
            )
        return dimensions

    if terms:
        cols = st.columns([0.55] * min(len(terms), 4) + [4])
        for idx, term in enumerate(terms):
            mult = float(term.get("mult") or 1)
            label = term["label"].split("(")[0].strip()[:12]
            if mult != 1:
                label = f"{label}×{mult:g}"
            dimensions[term["key"]] = cols[idx].number_input(
                label,
                min_value=0.0,
                step=1.0,
                key=f"dpr_{key_prefix}_steel_dim_{shape_code}_{term['key']}",
            )
    return dimensions


def _render_steel_shape_creator(key_prefix: str = "admin"):
    """Custom shape editor — use unique key_prefix (only call from one tab per page)."""
    with st.expander("Create / edit steel shape", expanded=False):
        st.caption("Define custom shapes: each term is one input; multiplier is how many times it counts in total length (e.g. ring width ×2).")
        c1, c2 = st.columns(2)
        shape_code = c1.text_input(
            "Shape code",
            key=f"dpr_{key_prefix}_new_shape_code",
            placeholder="MY_SHAPE",
        )
        shape_name = c2.text_input(
            "Shape name",
            key=f"dpr_{key_prefix}_new_shape_name",
            placeholder="My custom shape",
        )
        input_unit = st.selectbox("Input unit", ["mm", "m"], key=f"dpr_{key_prefix}_new_shape_unit")
        diagram_hint = st.text_input("Formula hint (optional)", key=f"dpr_{key_prefix}_new_shape_hint")
        st.markdown("**Dimensions (up to 6)**")
        term_rows = []
        for idx in range(6):
            t1, t2, t3 = st.columns([2, 1, 1])
            label = t1.text_input(
                f"Label {idx + 1}",
                key=f"dpr_{key_prefix}_new_shape_lbl_{idx}",
                placeholder="Length side (mm)" if idx == 0 else "",
            )
            mult = t2.number_input(
                f"×{idx + 1}",
                min_value=0.0,
                step=0.5,
                key=f"dpr_{key_prefix}_new_shape_mult_{idx}",
                value=0.0 if idx else 1.0,
            )
            key_part = t3.text_input(
                f"Key {idx + 1}",
                key=f"dpr_{key_prefix}_new_shape_key_{idx}",
                placeholder=f"d{idx + 1}" if idx else "length",
            )
            if label.strip() and mult > 0:
                term_rows.append(
                    {
                        "key": (key_part.strip() or f"d{idx + 1}").lower().replace(" ", "_"),
                        "label": label.strip(),
                        "mult": float(mult),
                    }
                )
        if st.button("Save steel shape", key=f"dpr_{key_prefix}_save_steel_shape"):
            try:
                save_custom_steel_shape(shape_code, shape_name, input_unit, term_rows, diagram_hint)
                st.success(f"Shape saved: {shape_code.upper()}")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))


def _render_steel_measurement_entry(key_prefix: str = "entry"):
    st.session_state.setdefault("dpr_steel_shape_code", "STRAIGHT")
    shapes = load_steel_shapes()
    if not shapes:
        st.warning("No steel shapes defined.")
        return None

    options = {f"{s['shape_name']} ({s['shape_code']})": s["shape_code"] for s in shapes}
    labels = list(options.keys())
    default_code = st.session_state.get("dpr_steel_shape_code", "STRAIGHT")
    boq_hint = str(st.session_state.get("dpr_boq_desc_display") or "").lower()
    if default_code == "STRAIGHT" and any(w in boq_hint for w in ("ring", "stirrup", "stirrups")):
        default_code = "RING"
    default_label = next((lb for lb, code in options.items() if code == default_code), labels[0])

    st.markdown('<div class="maxek-dpr-measure-compact">', unsafe_allow_html=True)
    st.caption(unit_entry_label("TON"))
    pick = st.selectbox(
        "Shape code",
        labels,
        index=labels.index(default_label) if default_label in labels else 0,
        key=f"dpr_{key_prefix}_steel_shape_pick",
    )
    shape_code = options[pick]
    st.session_state.dpr_steel_shape_code = shape_code
    shape = get_steel_shape(shape_code) or shapes[0]
    diagram_path = steel_shape_diagram_path(shape_code)
    if diagram_path:
        form_col, img_col = st.columns([2.2, 1])
    else:
        form_col = st.container()
        img_col = None

    with form_col:
        if shape.get("diagram_hint"):
            st.caption(shape["diagram_hint"])

        dimensions = _render_steel_dimension_inputs(shape_code, shape, key_prefix)

        c1, c2, c3, _ = st.columns([0.7, 0.55, 0.55, 3])
        with c1:
            dia_mm = _render_steel_dia_select(key_prefix)
        nos = c2.number_input("Nos", min_value=0.0, step=1.0, key=f"dpr_{key_prefix}_steel_nos")
        bend_factor = 1.0
        if shape_code == "BENT_BAR":
            bend_factor = c3.number_input(
                "Bend×",
                min_value=0.0,
                step=0.01,
                value=1.0,
                key=f"dpr_{key_prefix}_steel_bend_factor",
            )

    if img_col is not None:
        with img_col:
            st.image(str(diagram_path), caption=f"{shape.get('shape_name')} — reference", width="stretch")

    calc = compute_steel_measurement(shape, dimensions, dia_mm, nos, bend_factor)
    _render_measurement_preview(calc)
    st.markdown("</div>", unsafe_allow_html=True)
    return calc


def _dpr_draft_measurement_summary():
    boq_lines = st.session_state.get("dpr_draft_boq_lines") or []
    work = st.session_state.get("dpr_work_measurements") or []
    meas_count = sum(len(ln.get("measurements") or []) for ln in boq_lines) + len(work)
    total_qty = sum(float(ln.get("progress_quantity") or 0) for ln in boq_lines)
    total_qty += line_progress_qty(work)
    return meas_count, total_qty, len(boq_lines)


def _render_steel_shapes_admin_tab():
    st.markdown("### Steel shapes library")
    st.caption("Built-in shapes: Straight bar, Ring/Stirrup, Chair, Bent bar, Starter. Add custom shapes below.")
    shapes = load_steel_shapes(active_only=False)
    if shapes:
        rows = []
        for s in shapes:
            terms = s.get("terms") or []
            formula = " + ".join(f"{t.get('mult', 1):g}×{t.get('label', t.get('key'))}" for t in terms)
            rows.append(
                {
                    "Code": s.get("shape_code"),
                    "Name": s.get("shape_name"),
                    "Unit": s.get("input_unit"),
                    "Formula": formula or s.get("diagram_hint"),
                    "Built-in": "Yes" if s.get("is_builtin") else "No",
                }
            )
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    _render_steel_shape_creator(key_prefix="admin")


def _timestamp():
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def _parse_dpr_date(value):
    if not value:
        return None
    text = str(value).strip()[:10]
    for fmt in (DATE_FMT, "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _fetch_dpr_report(dpr_id):
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM dpr_reports WHERE dpr_id = ? LIMIT 1",
        conn,
        params=(dpr_id,),
    )
    conn.close()
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def _load_dpr_measurements_draft(dpr_id):
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT measurement_type, measurement_method, width_1, width_2, length_1, length_2,
               height, depth, nos, dia_mm, bend, avg_width, avg_length, avg_depth, qty,
               calculated_quantity, unit, dimensions_json
        FROM dpr_measurements WHERE dpr_id = ?
        ORDER BY id
        """,
        conn,
        params=(dpr_id,),
    )
    conn.close()
    drafts = []
    for _, row in df.iterrows():
        dims = {}
        try:
            dims = json.loads(row.get("dimensions_json") or "{}")
        except json.JSONDecodeError:
            dims = {}
        preview_lines = []
        steel_code = dims.get("steel_shape_code")
        if steel_code:
            shape = get_steel_shape(steel_code)
            if shape:
                steel_calc = compute_steel_measurement(
                    shape,
                    dims.get("steel_dimensions") or {},
                    float(dims.get("dia_mm") or row.get("dia_mm") or 0),
                    float(dims.get("nos") or row.get("nos") or 0),
                    float(dims.get("bend_factor") or row.get("bend") or 1),
                )
                preview_lines = steel_calc.get("preview_lines") or []

        drafts.append(
            {
                "measurement_type": row["measurement_type"],
                "measurement_method": row.get("measurement_method") or "Normal",
                "unit": row.get("unit") or row["measurement_type"],
                "qty": float(row.get("qty") or 0),
                "length_1": float(row.get("length_1") or 0),
                "length_2": float(row.get("length_2") or 0),
                "width_1": float(row.get("width_1") or 0),
                "width_2": float(row.get("width_2") or 0),
                "depth": float(row.get("depth") or row.get("avg_depth") or 0),
                "height": float(row.get("height") or 0),
                "avg_length": float(row.get("avg_length") or 0),
                "avg_width": float(row.get("avg_width") or 0),
                "avg_depth": float(row.get("avg_depth") or 0),
                "calculated_quantity": float(row.get("calculated_quantity") or 0),
                "nos": float(row.get("nos") or 0),
                "dia_mm": float(row.get("dia_mm") or 0),
                "bend": float(row.get("bend") or 0),
                "lengths": dims.get("lengths") or [],
                "widths": dims.get("widths") or [],
                "depths": dims.get("depths") or [],
                "dimensions_json": row.get("dimensions_json") or "",
                "preview_lines": preview_lines,
            }
        )
    return drafts


def _load_dpr_manpower_draft(dpr_id):
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT labour_type, nos, working_hours, remarks FROM dpr_manpower WHERE dpr_id = ? ORDER BY id",
        conn,
        params=(dpr_id,),
    )
    conn.close()
    return df.to_dict("records") if not df.empty else []


def _resolve_boq_row_key(project_name, boq_item_id):
    if not project_name or not boq_item_id:
        return ""
    boq_df = load_project_boq_by_project(project_name)
    if boq_df.empty:
        return ""
    match = boq_df[boq_df["boq_item_id"] == boq_item_id]
    if match.empty:
        return str(boq_item_id)
    row = match.iloc[0]
    if "id" in match.columns:
        return str(int(row["id"]))
    return str(boq_item_id)


def _populate_dpr_edit_session(dpr_id):
    report = _fetch_dpr_report(dpr_id)
    if not report:
        return False
    boq_lines = load_boq_lines_for_dpr(dpr_id)
    if not boq_lines:
        boq_lines = load_legacy_single_boq_line(dpr_id, report)
    for line in boq_lines:
        if not line.get("boq_row_id"):
            line["boq_row_id"] = _resolve_boq_row_key(
                report.get("project_name") or "",
                line.get("boq_item_id") or "",
            )
    st.session_state.dpr_draft_boq_lines = boq_lines
    st.session_state.dpr_work_measurements = []
    st.session_state.dpr_editing_boq_line_id = None
    st.session_state.dpr_draft_measurements = flatten_measurements(boq_lines)
    st.session_state.dpr_draft_manpower = _load_dpr_manpower_draft(dpr_id)
    st.session_state["dpr_project"] = report.get("project_name") or ""
    st.session_state["dpr_last_project_name"] = report.get("project_name") or ""
    parsed_date = _parse_dpr_date(report.get("dpr_date"))
    if parsed_date:
        st.session_state["dpr_date"] = parsed_date
    staff_label = ""
    if report.get("site_incharge_id") and report.get("site_incharge_name"):
        staff_label = f"{report['site_incharge_id']} - {report['site_incharge_name']}"
    st.session_state["dpr_site_incharge"] = staff_label
    st.session_state["dpr_boq_row_id"] = _resolve_boq_row_key(
        report.get("project_name") or "",
        report.get("boq_item_id") or "",
    )
    billing = (report.get("billing_measurement") or "No").strip().title()
    st.session_state["dpr_billing"] = billing if billing in ("Yes", "No") else "No"
    st.session_state["dpr_remarks"] = report.get("remarks") or ""
    st.session_state["dpr_weather"] = report.get("weather") or ""
    st.session_state["dpr_equipment"] = report.get("equipment_usage") or ""
    st.session_state["dpr_delay"] = report.get("delay_reason") or ""
    return True


def _clear_dpr_edit_session():
    for key in (
        "dpr_edit_id",
        "dpr_edit_loaded",
        "dpr_date",
        "dpr_project",
        "dpr_site_incharge",
        "dpr_boq_row_id",
        "dpr_remarks",
        "dpr_weather",
        "dpr_equipment",
        "dpr_delay",
        "dpr_billing",
        "dpr_draft_pick",
    ):
        st.session_state.pop(key, None)
    _reset_dpr_drafts()


def _delete_dpr(dpr_id):
    conn = get_conn()
    billed = conn.execute(
        "SELECT COALESCE(billed_quantity, 0), status FROM dpr_reports WHERE dpr_id = ?",
        (dpr_id,),
    ).fetchone()
    if not billed:
        conn.close()
        return False, "DPR not found."
    if float(billed[0] or 0) > 0 or str(billed[1] or "") == DPR_STATUS_BILLED:
        conn.close()
        return False, "Cannot delete: this DPR has billing recorded."
    conn.execute("DELETE FROM dpr_measurements WHERE dpr_id = ?", (dpr_id,))
    conn.execute("DELETE FROM dpr_boq_lines WHERE dpr_id = ?", (dpr_id,))
    conn.execute("DELETE FROM dpr_manpower WHERE dpr_id = ?", (dpr_id,))
    conn.execute("DELETE FROM dpr_reports WHERE dpr_id = ?", (dpr_id,))
    conn.commit()
    conn.close()
    return True, ""


def _reject_dpr_to_draft(dpr_id, reason, user):
    conn = get_conn()
    row = conn.execute(
        "SELECT status, COALESCE(billed_quantity, 0) FROM dpr_reports WHERE dpr_id = ?",
        (dpr_id,),
    ).fetchone()
    if not row:
        conn.close()
        return False, "DPR not found."
    if float(row[1] or 0) > 0:
        conn.close()
        return False, "Cannot reject: billing already started for this DPR."
    conn.execute(
        """
        UPDATE dpr_reports SET
            status = ?,
            engineer_approval = 'Pending',
            client_approval = 'Pending',
            engineer_approved_by = NULL,
            engineer_approved_at = NULL,
            client_approved_by = NULL,
            client_approved_at = NULL,
            rejection_reason = ?,
            rejected_by = ?,
            rejected_at = ?
        WHERE dpr_id = ?
        """,
        (DPR_STATUS_DRAFT, reason.strip(), user, _timestamp(), dpr_id),
    )
    conn.commit()
    conn.close()
    return True, ""


def _staff_options():
    df = load_company_staff_for_select()
    if df.empty:
        return [""], {}
    labels = []
    mapping = {}
    for _, row in df.iterrows():
        label = f"{row['employee_id']} - {row['employee_name']}"
        labels.append(label)
        mapping[label] = (row["employee_id"], row["employee_name"])
    return [""] + labels, mapping


def _insert_measurements(conn, dpr_id, measurements):
    for row in measurements:
        measurement_id = generate_id("DPM", "dpr_measurements", conn=conn)
        conn.execute(
            """
            INSERT INTO dpr_measurements(
                measurement_id, dpr_id, measurement_type, measurement_method,
                width_1, width_2, length_1, length_2,
                height, depth, nos, dia_mm, bend,
                avg_width, avg_length, avg_depth, qty,
                calculated_quantity, unit, dimensions_json, boq_item_id, boq_line_id
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                measurement_id,
                dpr_id,
                row["measurement_type"],
                row.get("measurement_method", "Normal"),
                row.get("width_1", 0),
                row.get("width_2", 0),
                row.get("length_1", 0),
                row.get("length_2", 0),
                row.get("height", 0),
                row.get("depth", row.get("avg_depth", 0)),
                row.get("nos", 0),
                row.get("dia_mm", 0),
                row.get("bend", 0),
                row.get("avg_width", 0),
                row.get("avg_length", 0),
                row.get("avg_depth", 0),
                row.get("qty", 0),
                row["calculated_quantity"],
                row.get("unit", ""),
                row.get("dimensions_json", ""),
                row.get("boq_item_id", ""),
                row.get("boq_line_id", ""),
            ),
        )


def _insert_dpr_records(
    conn,
    dpr_row,
    boq_lines,
    measurements,
    manpower_rows,
):
    conn.execute(
        """
        INSERT INTO dpr_reports(
            dpr_id, dpr_date, project_name, project_id, client_name, site_incharge_id, site_incharge_name,
            boq_item_id, boq_number, boq_description, unit, billing_measurement,
            total_boq_quantity, done_quantity, billed_quantity, balance_quantity,
            pending_billing_quantity, progress_quantity, remarks, document_upload, site_photo,
            weather, equipment_usage, delay_reason, engineer_approval, client_approval,
            status, created_by, created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            dpr_row["dpr_id"],
            dpr_row["dpr_date"],
            dpr_row["project_name"],
            dpr_row.get("project_id", ""),
            dpr_row.get("client_name", ""),
            dpr_row["site_incharge_id"],
            dpr_row["site_incharge_name"],
            dpr_row["boq_item_id"],
            dpr_row["boq_number"],
            dpr_row["boq_description"],
            dpr_row["unit"],
            dpr_row["billing_measurement"],
            dpr_row["total_boq_quantity"],
            dpr_row["done_quantity"],
            dpr_row["billed_quantity"],
            dpr_row["balance_quantity"],
            dpr_row["pending_billing_quantity"],
            dpr_row["progress_quantity"],
            dpr_row["remarks"],
            dpr_row.get("document_upload", ""),
            dpr_row.get("site_photo", ""),
            dpr_row.get("weather", ""),
            dpr_row.get("equipment_usage", ""),
            dpr_row.get("delay_reason", ""),
            "Pending",
            "Pending",
            dpr_row["status"],
            dpr_row["created_by"],
            dpr_row["created_at"],
        ),
    )
    persist_boq_lines(conn, dpr_row["dpr_id"], boq_lines)
    _insert_measurements(conn, dpr_row["dpr_id"], measurements)
    for row in manpower_rows:
        manpower_id = generate_id("DPL", "dpr_manpower")
        conn.execute(
            """
            INSERT INTO dpr_manpower(manpower_id, dpr_id, labour_type, nos, working_hours, remarks)
            VALUES(?,?,?,?,?,?)
            """,
            (
                manpower_id,
                dpr_row["dpr_id"],
                row["labour_type"],
                int(row["nos"]),
                row["working_hours"],
                row.get("remarks", ""),
            ),
        )


def _update_dpr_records(conn, dpr_id, dpr_row, boq_lines, measurements, manpower_rows):
    conn.execute(
        """
        UPDATE dpr_reports SET
            dpr_date = ?, project_name = ?, project_id = ?, client_name = ?,
            site_incharge_id = ?, site_incharge_name = ?,
            boq_item_id = ?, boq_number = ?, boq_description = ?, unit = ?,
            billing_measurement = ?, total_boq_quantity = ?, done_quantity = ?,
            billed_quantity = ?, balance_quantity = ?, pending_billing_quantity = ?,
            progress_quantity = ?, remarks = ?, document_upload = ?, site_photo = ?,
            weather = ?, equipment_usage = ?, delay_reason = ?,
            engineer_approval = 'Pending', client_approval = 'Pending',
            engineer_approved_by = NULL, engineer_approved_at = NULL,
            client_approved_by = NULL, client_approved_at = NULL,
            status = ?, rejection_reason = NULL, rejected_by = NULL, rejected_at = NULL
        WHERE dpr_id = ?
        """,
        (
            dpr_row["dpr_date"],
            dpr_row["project_name"],
            dpr_row.get("project_id", ""),
            dpr_row.get("client_name", ""),
            dpr_row["site_incharge_id"],
            dpr_row["site_incharge_name"],
            dpr_row["boq_item_id"],
            dpr_row["boq_number"],
            dpr_row["boq_description"],
            dpr_row["unit"],
            dpr_row["billing_measurement"],
            dpr_row["total_boq_quantity"],
            dpr_row["done_quantity"],
            dpr_row["billed_quantity"],
            dpr_row["balance_quantity"],
            dpr_row["pending_billing_quantity"],
            dpr_row["progress_quantity"],
            dpr_row["remarks"],
            dpr_row.get("document_upload", ""),
            dpr_row.get("site_photo", ""),
            dpr_row.get("weather", ""),
            dpr_row.get("equipment_usage", ""),
            dpr_row.get("delay_reason", ""),
            dpr_row["status"],
            dpr_id,
        ),
    )
    conn.execute("DELETE FROM dpr_measurements WHERE dpr_id = ?", (dpr_id,))
    delete_boq_lines_for_dpr(conn, dpr_id)
    conn.execute("DELETE FROM dpr_manpower WHERE dpr_id = ?", (dpr_id,))
    persist_boq_lines(conn, dpr_id, boq_lines)
    _insert_measurements(conn, dpr_id, measurements)
    for row in manpower_rows:
        manpower_id = generate_id("DPL", "dpr_manpower", conn=conn)
        conn.execute(
            """
            INSERT INTO dpr_manpower(manpower_id, dpr_id, labour_type, nos, working_hours, remarks)
            VALUES(?,?,?,?,?,?)
            """,
            (
                manpower_id,
                dpr_id,
                row["labour_type"],
                int(row["nos"]),
                row["working_hours"],
                row.get("remarks", ""),
            ),
        )


def _render_measurement_fields(measurement_type):
    c1, c2, c3, c4 = st.columns(4)
    fields = {"measurement_type": measurement_type}
    if measurement_type in {"Concrete", "Brick Work"}:
        fields["length_1"] = c1.number_input("Length 1 (m)", min_value=0.0, step=0.01, key="dpr_m_len1")
        fields["length_2"] = c2.number_input("Length 2 (m)", min_value=0.0, step=0.01, key="dpr_m_len2")
        fields["width_1"] = c3.number_input("Width 1 (m)", min_value=0.0, step=0.01, key="dpr_m_w1")
        fields["width_2"] = c4.number_input("Width 2 (m)", min_value=0.0, step=0.01, key="dpr_m_w2")
        fields["depth"] = st.number_input("Depth / Height (m)", min_value=0.0, step=0.01, key="dpr_m_depth")
    elif measurement_type == "Shuttering":
        fields["length_1"] = c1.number_input("Length 1 (m)", min_value=0.0, step=0.01, key="dpr_m_len1")
        fields["length_2"] = c2.number_input("Length 2 (m)", min_value=0.0, step=0.01, key="dpr_m_len2")
        fields["height"] = c3.number_input("Height (m)", min_value=0.0, step=0.01, key="dpr_m_height")
        fields["width_1"] = 0.0
        fields["width_2"] = 0.0
    elif measurement_type == "Straight Bar":
        fields["nos"] = c1.number_input("Nos", min_value=0.0, step=1.0, key="dpr_m_nos")
        fields["length_1"] = c2.number_input("Length (m)", min_value=0.0, step=0.01, key="dpr_m_len1")
        fields["dia_mm"] = c3.number_input("Dia (mm)", min_value=0.0, step=1.0, key="dpr_m_dia")
    elif measurement_type == "Ring":
        fields["nos"] = c1.number_input("Nos", min_value=0.0, step=1.0, key="dpr_m_nos")
        fields["width_1"] = c2.number_input("Width (m)", min_value=0.0, step=0.01, key="dpr_m_w1")
        fields["length_1"] = c3.number_input("Length (m)", min_value=0.0, step=0.01, key="dpr_m_len1")
        fields["dia_mm"] = c4.number_input("Dia (mm)", min_value=0.0, step=1.0, key="dpr_m_dia")
    elif measurement_type == "Bent Bar":
        fields["nos"] = c1.number_input("Nos", min_value=0.0, step=1.0, key="dpr_m_nos")
        fields["length_1"] = c2.number_input("Length 1 (m)", min_value=0.0, step=0.01, key="dpr_m_len1")
        fields["length_2"] = c3.number_input("Length 2 (m)", min_value=0.0, step=0.01, key="dpr_m_len2")
        fields["bend"] = c4.number_input("Bend Factor", min_value=0.0, step=0.1, value=1.0, key="dpr_m_bend")
        fields["dia_mm"] = st.number_input("Dia (mm)", min_value=0.0, step=1.0, key="dpr_m_dia")
    return fields


def _render_draft_queue():
    conn = get_conn()
    drafts_df = pd.read_sql_query(
        """
        SELECT dpr_id, dpr_date, project_name, boq_number, progress_quantity, status,
               COALESCE(rejection_reason, '') AS rejection_reason
        FROM dpr_reports
        WHERE status = ?
        ORDER BY id DESC
        LIMIT 50
        """,
        conn,
        params=(DPR_STATUS_DRAFT,),
    )
    conn.close()
    if drafts_df.empty:
        return
    st.markdown("#### Draft / returned for correction")
    st.dataframe(
        drafts_df.rename(columns={"rejection_reason": "Rejection reason"}),
        width="stretch",
        hide_index=True,
    )
    options = {
        f"{row['dpr_id']} | {row['dpr_date']} | {row['project_name']} | BOQ {row['boq_number']}": row["dpr_id"]
        for _, row in drafts_df.iterrows()
    }
    c1, c2 = st.columns([4, 1])
    pick_label = c1.selectbox("Open draft to edit", [""] + list(options.keys()), key="dpr_draft_pick")
    if c2.button("EDIT DRAFT", width="stretch", key="dpr_open_draft"):
        if not pick_label:
            st.error("Select a draft DPR first.")
        else:
            st.session_state.dpr_edit_id = options[pick_label]
            st.session_state.pop("dpr_edit_loaded", None)
            st.rerun()


def _render_new_dpr_tab():
    _ensure_dpr_drafts()
    _render_draft_queue()
    edit_id = st.session_state.get("dpr_edit_id")
    if edit_id and st.session_state.get("dpr_edit_loaded") != edit_id:
        if _populate_dpr_edit_session(edit_id):
            st.session_state.dpr_edit_loaded = edit_id
        else:
            st.error("Draft DPR not found.")
            _clear_dpr_edit_session()
            st.stop()

    if edit_id:
        report = _fetch_dpr_report(edit_id)
        reason = (report or {}).get("rejection_reason") or ""
        st.warning(
            f"Editing DPR **{edit_id}**. Update below and save draft or submit again."
            + (f" Rejection note: {reason}" if reason else "")
        )
        if st.button("Cancel edit / new DPR", key="dpr_cancel_edit"):
            _clear_dpr_edit_session()
            st.rerun()

    st.markdown("### DPR Main Entry")
    projects = [""] + load_project_names()
    staff_labels, staff_map = _staff_options()
    if len(staff_labels) <= 1:
        st.warning("No active staff found. Add Monthly or Daily Wage staff in Employee Management.")

    m1, m2, m3 = st.columns(3)
    date_default = st.session_state.get("dpr_date") if edit_id else date.today()
    if not isinstance(date_default, date):
        date_default = date.today()
    dpr_date = m1.date_input("Date", value=date_default, key="dpr_date")
    project_name = m2.selectbox("Project Name", projects, key="dpr_project")
    site_pick = m3.selectbox(
        "Site Incharge",
        staff_labels,
        key="dpr_site_incharge",
        placeholder="Select staff" if staff_labels else "No staff",
    )

    current_project_id = resolve_project_id(project_name) if project_name else ""
    if st.session_state.get("dpr_last_project_name") != project_name:
        st.session_state.dpr_last_project_name = project_name
        for key in ("dpr_boq_row_id", "dpr_boq_item_id", "dpr_boq_pick", "dpr_last_boq_pick"):
            st.session_state.pop(key, None)

    boq_df = load_project_boq_by_project(project_name) if project_name else pd.DataFrame()
    if current_project_id and not boq_df.empty and "project_id" in boq_df.columns:
        boq_df = boq_df[
            boq_df["project_id"].fillna("").astype(str).str.strip() == current_project_id
        ].reset_index(drop=True)

    boq_label_map = {"": "Select BOQ"}
    boq_row_ids = [""]
    if not boq_df.empty and "id" in boq_df.columns:
        for _, row in boq_df.iterrows():
            row_key = str(int(row["id"]))
            desc = str(row.get("description") or "")[:40]
            boq_label_map[row_key] = f"{row['boq_number']} | {desc}"
            boq_row_ids.append(row_key)
    elif not boq_df.empty:
        for _, row in boq_df.iterrows():
            row_key = str(row["boq_item_id"])
            desc = str(row.get("description") or "")[:40]
            boq_label_map[row_key] = f"{row['boq_number']} | {desc}"
            boq_row_ids.append(row_key)

    _apply_dpr_pending_ui_state()

    b1, b2, b3 = st.columns(3)
    if project_name and boq_df.empty:
        st.caption("No BOQ items found for this project. Add BOQ under Clients & Projects.")

    boq_row_pick = b1.selectbox(
        "BOQ Number",
        boq_row_ids,
        format_func=lambda row_key: boq_label_map.get(row_key, "Select BOQ"),
        key="dpr_boq_row_id",
    )
    billing_measurement = b2.selectbox("Billing Measurement", ["No", "Yes"], key="dpr_billing")
    dpr_no_display = edit_id or generate_id("DPR", "dpr_reports")
    b3.text_input("DPR No", value=dpr_no_display, disabled=True, key="dpr_no_preview")

    boq_desc = ""
    unit = ""
    stats = {
        "total_qty": 0.0,
        "done_qty": 0.0,
        "billed_qty": 0.0,
        "balance_qty": 0.0,
        "pending_billing_qty": 0.0,
    }
    boq_item_id = ""
    boq_number = ""
    project_id = ""
    unit_family = ""
    if boq_row_pick and not boq_df.empty:
        if "id" in boq_df.columns:
            match = boq_df[boq_df["id"].astype(int).astype(str) == str(boq_row_pick)]
        else:
            match = boq_df[boq_df["boq_item_id"] == boq_row_pick]
        if not match.empty:
            row = match.iloc[0]
            boq_item_id = row["boq_item_id"]
            boq_number = row["boq_number"]
            boq_desc = row["description"]
            unit = row["unit"]
            unit_family = normalize_boq_unit(unit)
            project_id = row.get("project_id", "") or current_project_id
            stats = get_boq_progress_stats(boq_item_id)
            if st.session_state.get("dpr_last_boq_pick") != boq_row_pick:
                st.session_state.dpr_last_boq_pick = boq_row_pick
                _reset_dpr_measurement_session(unit_family, boq_item_id)

    d1, d2, d3 = st.columns(3)
    d1.text_input("BOQ Description", value=boq_desc, disabled=True, key="dpr_boq_desc_display")
    d2.text_input("BOQ Unit", value=unit, disabled=True, key="dpr_unit_display")
    if unit_family:
        d3.markdown(
            f'<div class="maxek-dpr-unit-badge">Auto entry: <strong>{unit_family}</strong></div>',
            unsafe_allow_html=True,
        )

    q1, q2, q3, q4, q5 = st.columns(5)
    q1.metric("BOQ Qty", f"{stats['total_qty']:,.2f}")
    q2.metric("Done Qty", f"{stats['done_qty']:,.2f}")
    q3.metric("Billed Qty", f"{stats['billed_qty']:,.2f}")
    q4.metric("Balance Qty", f"{stats['balance_qty']:,.2f}")
    q5.metric("Pending Billing", f"{stats['pending_billing_qty']:,.2f}")

    remarks = st.text_area("Remarks", key="dpr_remarks")
    e1, e2, e3 = st.columns(3)
    weather = e1.text_input("Weather", key="dpr_weather")
    equipment_usage = e2.text_input("Equipment Usage", key="dpr_equipment")
    delay_reason = e3.text_input("Delay Reason", key="dpr_delay")
    doc_upload = st.file_uploader("Shape / Sketch / Document Upload", key="dpr_doc")
    site_photo = st.file_uploader("Daily Site Photo", type=["jpg", "jpeg", "png"], key="dpr_photo")

    st.markdown("### BOQ items on this DPR (one day, multiple items)")
    meas_count, total_qty, boq_count = _dpr_draft_measurement_summary()
    if boq_count:
        st.success(
            f"**{boq_count}** BOQ item(s) saved · **{meas_count}** measurement line(s) · "
            f"total progress **{total_qty:,.4f}**. Add another BOQ below, or save the full DPR at the bottom."
        )
    else:
        st.info(
            "**Step 1:** Select a BOQ → enter measurements → **Save BOQ item to DPR**. "
            "**Step 2:** Repeat for other BOQ items on the same day. "
            "**Step 3:** **Save Draft** or **Submit DPR** when all items are done."
        )

    saved_lines = st.session_state.get("dpr_draft_boq_lines") or []
    if saved_lines:
        st.markdown("#### Saved BOQ lines")
        summary_rows = []
        for ln in saved_lines:
            summary_rows.append(
                {
                    "BOQ": ln.get("boq_number"),
                    "Description": str(ln.get("boq_description", ""))[:50],
                    "Unit": ln.get("unit"),
                    "Lines": len(ln.get("measurements") or []),
                    "Progress": ln.get("progress_quantity", 0),
                    "Billing": ln.get("billing_measurement"),
                }
            )
        st.dataframe(pd.DataFrame(summary_rows), width="stretch", hide_index=True)
        for idx, ln in enumerate(saved_lines):
            c1, c2, c3 = st.columns([4, 1, 1])
            c1.caption(
                f"#{idx + 1} BOQ {ln.get('boq_number')} — {len(ln.get('measurements') or [])} measurement(s), "
                f"qty {ln.get('progress_quantity', 0):,.4f}"
            )

            def _remove_boq_line(index=idx):
                st.session_state.dpr_draft_boq_lines.pop(index)
                st.session_state.dpr_draft_measurements = flatten_measurements(
                    st.session_state.dpr_draft_boq_lines
                )
                st.rerun()

            if c2.button("Edit", key=f"dpr_edit_boq_{idx}"):
                _queue_edit_boq_line(ln, project_name)
            if c3.button("Remove", key=f"dpr_rm_boq_{idx}"):
                _remove_boq_line()

    editing = st.session_state.get("dpr_editing_boq_line_id")
    if editing:
        st.warning("Editing a saved BOQ line — change measurements and click **Save BOQ item to DPR** again.")

    st.markdown("#### Add / update BOQ item")
    if not boq_item_id:
        st.caption("Select a BOQ item, then add measurements for that item.")
    else:
        work_count = len(st.session_state.get("dpr_work_measurements") or [])
        if work_count:
            st.caption(f"Current BOQ ({boq_number}): **{work_count}** measurement line(s) not saved to DPR yet.")
        use_steel = is_steel_boq_entry(unit, boq_desc)
        if use_steel:
            st.caption(
                "Steel: shape (Ring = 6 fields), dia dropdown, nos → MT. Then save this BOQ item to the DPR."
            )
            calc = _render_steel_measurement_entry(key_prefix="entry")
            if st.button("ADD MEASUREMENT FOR THIS BOQ", key="dpr_add_measurement", type="secondary"):
                if not calc:
                    st.error("Select a steel shape and enter dimensions.")
                else:
                    entry = build_steel_measurement_record(calc)
                    if entry["calculated_quantity"] <= 0:
                        st.error("Weight (MT) must be greater than zero.")
                    else:
                        st.session_state.dpr_work_measurements.append(entry)
                        st.success(f"Measurement #{len(st.session_state.dpr_work_measurements)} added for BOQ {boq_number}.")
                        st.rerun()
        else:
            st.caption(
                "Area / volume: pick **Normal** (one L×W) or **Average** (many lengths & widths — use **+ Add length** / **+ Add width**)."
            )
            calc = _render_boq_measurement_entry(unit_family, boq_item_id)
            if st.button("ADD MEASUREMENT FOR THIS BOQ", key="dpr_add_measurement", type="secondary"):
                method = st.session_state.get("dpr_measurement_method", "Normal")
                lengths, widths, depths, qty = _collect_measurement_inputs(
                    unit_family, method, boq_item_id
                )
                entry = build_measurement_record(unit_family, method, lengths, widths, depths, qty)
                if entry["calculated_quantity"] <= 0:
                    st.error("Calculated quantity must be greater than zero.")
                else:
                    st.session_state.dpr_work_measurements.append(entry)
                    st.success(f"Measurement #{len(st.session_state.dpr_work_measurements)} added for BOQ {boq_number}.")
                    st.rerun()

        if st.session_state.dpr_work_measurements:
            st.markdown("**Measurements for current BOQ (not saved to DPR yet)**")
            wr = []
            for m in st.session_state.dpr_work_measurements:
                wr.append(
                    {
                        "Method": m.get("measurement_method", "Normal"),
                        "Avg L": m.get("avg_length", 0),
                        "Avg W": m.get("avg_width", 0),
                        "Qty": m.get("qty", 0),
                        "Total": m.get("calculated_quantity", 0),
                        "Unit": m.get("unit", ""),
                    }
                )
            st.dataframe(pd.DataFrame(wr), width="stretch", hide_index=True)

        if st.button("SAVE BOQ ITEM TO DPR", type="primary", key="dpr_save_boq_line"):
            if _commit_current_boq_to_dpr(
                boq_row_pick,
                boq_item_id,
                boq_number,
                boq_desc,
                unit,
                billing_measurement,
                stats,
            ):
                st.success(f"BOQ {boq_number} saved on this DPR. Select the next BOQ item to continue.")
                st.rerun()

    st.markdown("### Manpower Entry")
    trade_options = _load_dpr_trade_options()
    mp1, mp2, mp3, mp4 = st.columns(4)
    trade_pick = mp1.selectbox("Trade", [""] + trade_options + ["Other"], key="dpr_labour_trade")
    if trade_pick == "Other":
        labour_type = mp1.text_input("Trade (other)", key="dpr_labour_trade_other", placeholder="Enter trade")
    else:
        labour_type = trade_pick
    labour_nos = mp2.number_input("Nos", min_value=0, step=1, key="dpr_labour_nos")
    working_hours = mp3.selectbox("Working Hours", ["8 Hours", "10 Hours", "12 Hours", "Custom"], key="dpr_hours")
    labour_remarks = mp4.text_input("Manpower Remarks", key="dpr_labour_remarks")
    if st.button("ADD MANPOWER LINE", key="dpr_add_manpower"):
        if not str(labour_type or "").strip():
            st.error("Trade is required.")
        elif labour_nos <= 0:
            st.error("Nos must be greater than zero.")
        else:
            st.session_state.dpr_draft_manpower.append(
                {
                    "labour_type": labour_type.strip(),
                    "nos": labour_nos,
                    "working_hours": working_hours,
                    "remarks": labour_remarks,
                }
            )
            st.rerun()
    if st.session_state.dpr_draft_manpower:
        st.dataframe(pd.DataFrame(st.session_state.dpr_draft_manpower), width="stretch", hide_index=True)

    st.markdown("---")
    st.markdown("### Save this DPR (all BOQ items)")
    if not st.session_state.get("dpr_draft_boq_lines"):
        st.warning("Save at least one BOQ item (with measurements) before saving the full DPR.")
    c_save, c_submit = st.columns(2)
    if c_save.button("SAVE DRAFT (full DPR)", width="stretch"):
        _save_dpr(
            dpr_date,
            project_name,
            project_id,
            site_pick,
            staff_map,
            remarks,
            weather,
            equipment_usage,
            delay_reason,
            doc_upload,
            site_photo,
            DPR_STATUS_DRAFT,
        )
    if c_submit.button("SUBMIT DPR (full DPR)", type="primary", width="stretch"):
        _save_dpr(
            dpr_date,
            project_name,
            project_id,
            site_pick,
            staff_map,
            remarks,
            weather,
            equipment_usage,
            delay_reason,
            doc_upload,
            site_photo,
            DPR_STATUS_SUBMITTED,
        )


def _save_dpr(
    dpr_date,
    project_name,
    project_id,
    site_pick,
    staff_map,
    remarks,
    weather,
    equipment_usage,
    delay_reason,
    doc_upload,
    site_photo,
    status,
):
    if not project_name:
        st.error("Project Name is required.")
        return
    if not site_pick or site_pick not in staff_map:
        st.error("Site Incharge (staff) is required.")
        return

    boq_lines = list(st.session_state.get("dpr_draft_boq_lines") or [])
    if st.session_state.get("dpr_work_measurements"):
        st.warning("You have unsaved measurements for the current BOQ. Click **Save BOQ item to DPR** first.")
        return
    if not boq_lines:
        st.error("Save at least one BOQ item (with measurements) to this DPR.")
        return

    expected_pid = resolve_project_id(project_name)
    if expected_pid:
        conn_chk = get_conn()
        for line in boq_lines:
            boq_row = conn_chk.execute(
                "SELECT project_id FROM project_boq_items WHERE boq_item_id = ? LIMIT 1",
                (line["boq_item_id"],),
            ).fetchone()
            if boq_row and (boq_row[0] or "").strip() not in ("", expected_pid):
                conn_chk.close()
                st.error(f"BOQ {line.get('boq_number')} does not belong to this project.")
                return
        conn_chk.close()

    edit_id = st.session_state.get("dpr_edit_id")
    boq_lines = enrich_boq_lines_for_save(boq_lines, edit_id or "")
    header = header_summary_from_boq_lines(boq_lines)
    progress_qty = float(header.get("progress_quantity") or 0)

    staff_id, staff_name = staff_map[site_pick]
    dpr_id = edit_id or generate_id("DPR", "dpr_reports")
    doc_path = _save_upload(doc_upload, "uploads/dpr", f"{dpr_id}_doc")
    photo_path = _save_upload(site_photo, "uploads/dpr", f"{dpr_id}_photo")

    old_billed = 0.0
    if edit_id:
        existing = _fetch_dpr_report(edit_id)
        if existing:
            old_billed = float(existing.get("billed_quantity") or 0)
            if not doc_path:
                doc_path = existing.get("document_upload") or ""
            if not photo_path:
                photo_path = existing.get("site_photo") or ""

    client_name = ""
    conn_lookup = get_conn()
    client_row = conn_lookup.execute(
        "SELECT client_name FROM projects WHERE project_name = ? LIMIT 1",
        (project_name,),
    ).fetchone()
    conn_lookup.close()
    if client_row:
        client_name = client_row[0] or ""

    dpr_row = {
        "dpr_id": dpr_id,
        "dpr_date": dpr_date.strftime(DATE_FMT),
        "project_name": project_name,
        "project_id": project_id or "",
        "client_name": client_name,
        "site_incharge_id": staff_id,
        "site_incharge_name": staff_name,
        "boq_item_id": header.get("boq_item_id", ""),
        "boq_number": header.get("boq_number", ""),
        "boq_description": header.get("boq_description", ""),
        "unit": header.get("unit", ""),
        "billing_measurement": header.get("billing_measurement", "No"),
        "total_boq_quantity": header.get("total_boq_quantity", 0),
        "done_quantity": header.get("done_quantity", 0),
        "billed_quantity": old_billed if edit_id else header.get("billed_quantity", 0),
        "balance_quantity": header.get("balance_quantity", 0),
        "pending_billing_quantity": header.get("pending_billing_quantity", 0),
        "progress_quantity": progress_qty,
        "remarks": remarks,
        "document_upload": doc_path,
        "site_photo": photo_path,
        "weather": weather,
        "equipment_usage": equipment_usage,
        "delay_reason": delay_reason,
        "status": status,
        "created_by": st.session_state.get("user_name", "User"),
        "created_at": _timestamp(),
    }
    all_measurements = flatten_measurements(boq_lines)
    conn = get_conn()
    if edit_id:
        _update_dpr_records(
            conn,
            edit_id,
            dpr_row,
            boq_lines,
            all_measurements,
            st.session_state.dpr_draft_manpower,
        )
    else:
        _insert_dpr_records(
            conn,
            dpr_row,
            boq_lines,
            all_measurements,
            st.session_state.dpr_draft_manpower,
        )
    conn.commit()
    conn.close()
    _clear_dpr_edit_session()
    st.success(f"DPR {'updated' if edit_id else 'saved'}. ID: {dpr_id} · Status: {status}")
    st.rerun()


def _render_dpr_approval_actions(pending_df, pick_key, prefix, role, can_act, approve_status, approve_sql_extra):
    if pending_df.empty or not can_act:
        return
    pick = st.selectbox("Select DPR", [""] + pending_df["dpr_id"].tolist(), key=pick_key)
    if not pick:
        return
    reject_reason = st.text_input("Rejection reason (required to reject)", key=f"{prefix}_reject_reason")
    c1, c2, c3, c4 = st.columns(4)
    user = st.session_state.get("user_name", "User")

    if c1.button("APPROVE", type="primary", width="stretch", key=f"{prefix}_approve"):
        conn = get_conn()
        conn.execute(
            approve_sql_extra,
            (approve_status, user, _timestamp(), pick),
        )
        conn.commit()
        conn.close()
        st.success(f"{pick} approved.")
        st.rerun()

    if c2.button("REJECT", width="stretch", key=f"{prefix}_reject"):
        if not reject_reason.strip():
            st.error("Enter a rejection reason.")
        else:
            ok, err = _reject_dpr_to_draft(pick, reject_reason, user)
            if not ok:
                st.error(err)
            else:
                st.session_state.dpr_edit_id = pick
                st.session_state.pop("dpr_edit_loaded", None)
                st.success(
                    f"{pick} returned to **Draft**. Open the **New DPR** tab to edit and resubmit."
                )
                st.rerun()

    if c3.button("EDIT IN ENTRY", width="stretch", key=f"{prefix}_edit_entry"):
        report = _fetch_dpr_report(pick)
        if report and str(report.get("status") or "") == DPR_STATUS_DRAFT:
            st.session_state.dpr_edit_id = pick
            st.session_state.pop("dpr_edit_loaded", None)
            st.info(f"Open **New DPR** tab to edit {pick}.")
            st.rerun()
        ok, err = _reject_dpr_to_draft(pick, reject_reason.strip() or "Sent back for correction", user)
        if not ok:
            st.error(err)
        else:
            st.session_state.dpr_edit_id = pick
            st.session_state.pop("dpr_edit_loaded", None)
            st.success(f"{pick} moved to Draft. Open **New DPR** tab to edit.")
            st.rerun()

    if c4.button("DELETE", width="stretch", key=f"{prefix}_delete"):
        start_delete_confirm(prefix, pick, pick)

    def _do_delete(dpr_to_delete):
        if str(st.session_state.get("dpr_edit_id") or "") == str(dpr_to_delete):
            _clear_dpr_edit_session()
        ok, err = _delete_dpr(dpr_to_delete)
        if not ok:
            st.error(err)
        else:
            st.success(f"DPR {dpr_to_delete} deleted.")
            st.rerun()

    render_delete_confirm_dialog(prefix, _do_delete, message=f"Delete DPR {pick}? This cannot be undone.")


def _render_approvals_tab(role):
    conn = get_conn()
    st.markdown("### Engineer & Client Approval")
    st.caption("Reject sends the DPR back to **New DPR** as a draft for editing and resubmission.")
    submitted = pd.read_sql_query(
        """
        SELECT dpr_id, dpr_date, project_name, boq_number, progress_quantity, unit, billing_measurement, status
        FROM dpr_reports WHERE status = ?
        ORDER BY id DESC
        """,
        conn,
        params=(DPR_STATUS_SUBMITTED,),
    )
    engineer_pending = pd.read_sql_query(
        """
        SELECT dpr_id, dpr_date, project_name, boq_number, progress_quantity, unit, billing_measurement, status
        FROM dpr_reports WHERE status = ?
        ORDER BY id DESC
        """,
        conn,
        params=(DPR_STATUS_ENGINEER_APPROVED,),
    )
    conn.close()

    if not submitted.empty:
        st.markdown("#### Pending Engineer Approval")
        st.dataframe(submitted, width="stretch", hide_index=True)
        _render_dpr_approval_actions(
            submitted,
            "dpr_eng_pick",
            "dpr_eng",
            role,
            role in {"Admin", "Project Manager"},
            DPR_STATUS_ENGINEER_APPROVED,
            """
            UPDATE dpr_reports
            SET status = ?, engineer_approval = 'Approved', engineer_approved_by = ?, engineer_approved_at = ?
            WHERE dpr_id = ?
            """,
        )
    else:
        st.info("No DPRs waiting for engineer approval.")

    if not engineer_pending.empty:
        st.markdown("#### Pending Client Approval")
        st.dataframe(engineer_pending, width="stretch", hide_index=True)
        _render_dpr_approval_actions(
            engineer_pending,
            "dpr_cli_pick",
            "dpr_cli",
            role,
            role in {"Admin", "MD"},
            DPR_STATUS_CLIENT_APPROVED,
            """
            UPDATE dpr_reports
            SET status = ?, client_approval = 'Approved', client_approved_by = ?, client_approved_at = ?
            WHERE dpr_id = ?
            """,
        )
    else:
        st.info("No DPRs waiting for client approval.")


def _render_billing_tab():
    st.markdown("### Pending Client Billing")
    st.caption(
        "Step 1: Mark measured qty here. Step 2: Create client invoice in **Billing → Client Bill** "
        "(amount = qty × BOQ rate, print/PDF)."
    )
    conn = get_conn()
    pending_df = pd.read_sql_query(
        """
        SELECT dpr_id, dpr_date, project_name, boq_number, boq_description, progress_quantity,
               billed_quantity, unit, status
        FROM dpr_reports
        WHERE UPPER(COALESCE(billing_measurement, '')) = 'YES'
          AND status IN (?, ?)
          AND COALESCE(progress_quantity, 0) > COALESCE(billed_quantity, 0)
        ORDER BY id DESC
        """,
        conn,
        params=(DPR_STATUS_ENGINEER_APPROVED, DPR_STATUS_CLIENT_APPROVED),
    )
    conn.close()
    if pending_df.empty:
        st.info("No pending billing measurements.")
        return
    st.dataframe(pending_df, width="stretch", hide_index=True)
    pick = st.selectbox("Select DPR to bill", [""] + pending_df["dpr_id"].tolist(), key="dpr_bill_pick")
    if not pick:
        return
    row = pending_df[pending_df["dpr_id"] == pick].iloc[0]
    max_bill = float(row["progress_quantity"]) - float(row["billed_quantity"])
    bill_qty = st.number_input("Bill Quantity (partial allowed)", min_value=0.0, max_value=max_bill, value=max_bill, step=0.01)
    if st.button("MARK BILLED", type="primary", key="dpr_mark_billed"):
        new_billed = float(row["billed_quantity"]) + bill_qty
        new_status = DPR_STATUS_BILLED if new_billed >= float(row["progress_quantity"]) else row["status"]
        conn = get_conn()
        conn.execute(
            """
            UPDATE dpr_reports
            SET billed_quantity = ?, status = ?
            WHERE dpr_id = ?
            """,
            (new_billed, new_status, pick),
        )
        conn.execute(
            """
            UPDATE dpr_measurements SET billed = 1, billed_quantity = calculated_quantity
            WHERE dpr_id = ?
            """,
            (pick,),
        )
        conn.commit()
        conn.close()
        st.success(f"Billed {bill_qty:,.4f} for {pick}")
        st.rerun()


def _render_history_tab():
    st.markdown("### DPR Register & Measurement History")
    conn = get_conn()
    dpr_df = pd.read_sql_query(
        """
        SELECT dpr_id, dpr_date, project_name, site_incharge_name, boq_number, boq_description,
               progress_quantity, unit, billing_measurement, balance_quantity, status,
               engineer_approval, client_approval, weather
        FROM dpr_reports
        ORDER BY id DESC
        LIMIT 300
        """,
        conn,
    )
    meas_df = pd.read_sql_query(
        """
        SELECT m.dpr_id, d.dpr_date, d.project_name,
               COALESCE(bl.boq_number, d.boq_number) AS boq_number,
               m.measurement_type, m.avg_width, m.avg_length,
               m.calculated_quantity, m.unit, m.billed
        FROM dpr_measurements m
        JOIN dpr_reports d ON d.dpr_id = m.dpr_id
        LEFT JOIN dpr_boq_lines bl ON bl.line_id = m.boq_line_id
        ORDER BY m.id DESC
        LIMIT 500
        """,
        conn,
    )
    mp_df = pd.read_sql_query(
        """
        SELECT d.dpr_id, d.dpr_date, d.project_name, m.labour_type, m.nos, m.working_hours, m.remarks
        FROM dpr_manpower m
        JOIN dpr_reports d ON d.dpr_id = m.dpr_id
        ORDER BY m.id DESC
        LIMIT 500
        """,
        conn,
    )
    conn.close()
    st.dataframe(dpr_df, width="stretch", hide_index=True)
    st.markdown("#### Measurement History")
    st.dataframe(meas_df, width="stretch", hide_index=True)
    st.markdown("#### Manpower History")
    st.dataframe(mp_df, width="stretch", hide_index=True)


def _render_steel_shapes_tab_safe():
    if hasattr(st, "fragment"):

        @st.fragment
        def _inner():
            _render_steel_shapes_admin_tab()

        _inner()
    else:
        _render_steel_shapes_admin_tab()


def page_dpr():
    st.subheader("Daily Progress Report (DPR)")
    role = st.session_state.get("user_role", "Admin")
    tabs = st.tabs(["New DPR", "Approvals", "Pending Billing", "Register & History", "Steel Shapes"])
    with tabs[0]:
        _render_new_dpr_tab()
    with tabs[1]:
        _render_approvals_tab(role)
    with tabs[2]:
        if role in {"Admin", "Accountant", "Accounts Manager", "MD"}:
            _render_billing_tab()
        else:
            st.info("Billing is handled by Accounts / MD.")
    with tabs[3]:
        _render_history_tab()
    with tabs[4]:
        _render_steel_shapes_tab_safe()
