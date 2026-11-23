from datetime import date

from flask import Blueprint, render_template

from ..db import get_db, rows_as_dicts

bp = Blueprint("reports", __name__)


@bp.route("/report")
def report():
    conn = get_db()
    today = date.today().strftime("%Y-%m-%d")
    month = today[:7]

    def totals(prefix: str) -> dict:
        r = conn.execute(
            """SELECT COUNT(*) AS bills,
                      COALESCE(SUM(total), 0) AS income,
                      COALESCE(SUM(profit), 0) AS profit
               FROM sales WHERE created LIKE ?""",
            (prefix + "%",),
        ).fetchone()
        return dict(r)

    day = totals(today)
    mon = totals(month)
    recent = conn.execute(
        "SELECT id, created, customer, total FROM sales ORDER BY id DESC LIMIT 15"
    ).fetchall()
    conn.close()
    return render_template("report.html", day=day, mon=mon, recent=rows_as_dicts(recent))
