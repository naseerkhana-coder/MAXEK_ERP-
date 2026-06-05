"""Stock register updates on GRN, issue, and return."""

import pytest

from modules.database import (
    StockInsufficientError,
    apply_stock_receipt,
    get_conn,
    get_stock_balance,
    save_material_issue,
)
from modules.erp_data import save_grn, save_stock_return


def test_grn_increments_and_issue_decrements(tmp_db):
    conn = get_conn()
    apply_stock_receipt(conn, "CEM-01", "Cement", 100.0)
    conn.commit()
    conn.close()

    assert get_stock_balance("CEM-01", "Cement") == pytest.approx(100.0)

    save_material_issue(
        {
            "project_name": "Site A",
            "material_code": "CEM-01",
            "material_name": "Cement",
            "quantity": 30,
        },
        "tester",
    )
    assert get_stock_balance("CEM-01", "Cement") == pytest.approx(70.0)


def test_issue_blocks_negative_stock(tmp_db):
    with pytest.raises(StockInsufficientError):
        save_material_issue(
            {
                "project_name": "Site A",
                "material_code": "STEEL-1",
                "material_name": "Steel",
                "quantity": 5,
            },
            "tester",
        )


def test_grn_and_return_paths(tmp_db):
    save_grn(
        {
            "grn_no": "GRN-T1",
            "grn_date": "01/06/2026",
            "material_name": "Sand",
            "quantity": 50,
        },
        "store",
    )
    assert get_stock_balance("", "Sand") == pytest.approx(50.0)

    save_stock_return(
        {
            "return_date": "02/06/2026",
            "project_name": "Site A",
            "material_code": "SND-1",
            "material_name": "Sand",
            "quantity": 10,
        },
        "store",
    )
    assert get_stock_balance("SND-1", "Sand") == pytest.approx(60.0)
