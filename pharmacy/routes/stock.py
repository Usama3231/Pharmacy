import re
from datetime import date

from flask import Blueprint, flash, redirect, render_template, request

from ..db import get_db, rows_as_dicts

bp = Blueprint("stock", __name__)


@bp.route("/")
def home():
    return redirect("/stock-in")


@bp.route("/stock-in", methods=["GET", "POST"])
def stock_in():
    conn = get_db()

    if request.method == "POST":
        f = request.form
        name = f.get("name", "").strip()
        strength = f.get("strength", "").strip()
        company = f.get("company", "").strip()
        distributor = f.get("distributor", "").strip()
        invoice_no = f.get("invoice_no", "").strip()
        batch_no = f.get("batch_no", "").strip()
        expiry = f.get("expiry", "").strip()

        try:
            qty = int(f.get("qty", 0))
            bonus = int(f.get("bonus") or 0)
            cost_box = float(f.get("cost_box", 0))
            sale_box = float(f.get("sale_box", 0))
            spb = int(f.get("strips_per_box") or 1)
        except (TypeError, ValueError):
            flash("Enter valid numbers for quantity, prices and strips per box.")
            conn.close()
            return redirect("/stock-in")

        if not name or qty <= 0:
            flash("Enter a medicine name and a quantity above 0.")
            conn.close()
            return redirect("/stock-in")
        if bonus < 0 or spb <= 0:
            flash("Bonus cannot be negative and strips per box must be above 0.")
            conn.close()
            return redirect("/stock-in")
        if cost_box <= 0 or sale_box <= 0:
            flash("Purchase and selling prices must be above 0.")
            conn.close()
            return redirect("/stock-in")
        if not batch_no:
            flash("Enter a batch number.")
            conn.close()
            return redirect("/stock-in")
        if not re.fullmatch(r"\d{4}-\d{2}", expiry):
            flash("Expiry must be in YYYY-MM format.")
            conn.close()
            return redirect("/stock-in")

        med = conn.execute(
            """SELECT * FROM medicines
               WHERE name = ? COLLATE NOCASE AND strength = ? COLLATE NOCASE""",
            (name, strength),
        ).fetchone()

        if med is None:
            cur = conn.execute(
                """INSERT INTO medicines (name, strength, company, strips_per_box)
                   VALUES (?, ?, ?, ?)""",
                (name, strength, company, spb),
            )
            med_id = cur.lastrowid
        else:
            med_id = med["id"]
            spb = med["strips_per_box"]

        total_boxes = qty + bonus
        real_cost = cost_box * qty / total_boxes

        conn.execute(
            """INSERT INTO batches
               (medicine_id, distributor, invoice_no, batch_no, expiry,
                strips, cost_box, sale_box, received_on)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (med_id, distributor, invoice_no, batch_no, expiry, total_boxes * spb,
             real_cost, sale_box, str(date.today())),
        )
        conn.commit()
        conn.close()
        flash(f"Saved: {name} {strength} ({total_boxes} boxes added to stock)")
        return redirect("/stock-in")

    rows = conn.execute(
        """SELECT m.name, m.strength, m.company, m.strips_per_box,
                  (SELECT sale_box FROM batches b
                   WHERE b.medicine_id = m.id
                   ORDER BY b.id DESC LIMIT 1) AS sale_box
           FROM medicines m
           ORDER BY m.name, m.strength"""
    ).fetchall()
    conn.close()
    return render_template("stock_in.html", medicines=rows_as_dicts(rows))


@bp.route("/stock")
def stock():
    conn = get_db()
    rows = conn.execute(
        """SELECT m.name, m.strength, m.company, m.strips_per_box,
                  COALESCE(SUM(b.strips), 0) AS strips,
                  MIN(CASE WHEN b.strips > 0 THEN b.expiry END) AS expiry
           FROM medicines m
           LEFT JOIN batches b ON b.medicine_id = m.id
           GROUP BY m.id
           ORDER BY m.name, m.strength"""
    ).fetchall()
    conn.close()

    today = date.today()
    this_month = today.strftime("%Y-%m")
    y, m = today.year, today.month + 3
    if m > 12:
        m -= 12
        y += 1
    soon_limit = f"{y}-{m:02d}"

    items = []
    expired = soon = low = 0
    for r in rows:
        spb = r["strips_per_box"]
        status = ""
        if r["strips"] == 0:
            status = "out"
        elif r["expiry"] < this_month:
            status = "expired"
            expired += 1
        elif r["expiry"] <= soon_limit:
            status = "soon"
            soon += 1
        elif r["strips"] < spb * 2:
            status = "low"
            low += 1
        items.append({
            "name": r["name"],
            "strength": r["strength"],
            "company": r["company"],
            "boxes": r["strips"] // spb,
            "loose": r["strips"] % spb,
            "expiry": r["expiry"],
            "status": status,
        })

    return render_template("stock.html", items=items, expired=expired, soon=soon, low=low)
