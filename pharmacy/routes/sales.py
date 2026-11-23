from datetime import datetime

from flask import Blueprint, abort, jsonify, render_template, request

from ..db import get_db, rows_as_dicts

bp = Blueprint("sales", __name__)


@bp.route("/sale")
def sale():
    conn = get_db()
    rows = conn.execute(
        """SELECT m.id, m.name, m.strength, m.strips_per_box,
                  COALESCE(SUM(b.strips), 0) AS strips,
                  (SELECT sale_box FROM batches b2
                   WHERE b2.medicine_id = m.id AND b2.strips > 0
                   ORDER BY b2.expiry, b2.id LIMIT 1) AS price_box
           FROM medicines m
           LEFT JOIN batches b ON b.medicine_id = m.id
           GROUP BY m.id
           HAVING strips > 0
           ORDER BY m.name, m.strength"""
    ).fetchall()
    conn.close()
    return render_template("sale.html", medicines=rows_as_dicts(rows))


@bp.route("/sell", methods=["POST"])
def sell():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        data = {}
    lines = data.get("lines", [])
    customer = (data.get("customer") or "").strip()
    if not isinstance(lines, list) or not lines:
        return jsonify(error="The bill is empty."), 400

    conn = get_db()
    total = profit = 0.0
    items = []
    try:
        for ln in lines:
            if not isinstance(ln, dict):
                raise ValueError("Invalid sale line.")
            med = conn.execute(
                "SELECT * FROM medicines WHERE id = ?", (ln.get("id"),)
            ).fetchone()
            if med is None:
                raise ValueError("Unknown medicine in the bill.")
            mode = ln.get("mode")
            if mode not in ("box", "strip"):
                raise ValueError("Invalid sale mode.")
            try:
                qty = int(ln.get("qty", 0))
            except (TypeError, ValueError):
                raise ValueError("Invalid quantity.")
            if qty <= 0:
                raise ValueError("Quantity must be above 0.")
            spb = med["strips_per_box"]
            need = qty * spb if mode == "box" else qty

            batches = conn.execute(
                """SELECT * FROM batches
                   WHERE medicine_id = ? AND strips > 0
                   ORDER BY expiry, id""",
                (med["id"],),
            ).fetchall()
            for b in batches:
                if need == 0:
                    break
                take = min(need, b["strips"])
                need -= take
                price = b["sale_box"] / spb
                cost = b["cost_box"] / spb
                conn.execute(
                    "UPDATE batches SET strips = strips - ? WHERE id = ?",
                    (take, b["id"]),
                )
                items.append((med["id"], b["id"], mode, take, price, cost))
                total += take * price
                profit += take * (price - cost)

            if need > 0:
                raise ValueError(
                    f"Not enough stock for {med['name']} {med['strength']}"
                )

        cur = conn.execute(
            "INSERT INTO sales (created, customer, total, profit) VALUES (?, ?, ?, ?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), customer,
             round(total, 2), round(profit, 2)),
        )
        sale_id = cur.lastrowid
        conn.executemany(
            """INSERT INTO sale_items
               (sale_id, medicine_id, batch_id, mode, strips, price_strip, cost_strip)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [(sale_id, *it) for it in items],
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify(error=str(e)), 400

    conn.close()
    return jsonify(ok=True, total=round(total, 2), bill_id=sale_id)


@bp.route("/bill/<int:sale_id>")
def bill(sale_id: int):
    conn = get_db()
    sale = conn.execute("SELECT * FROM sales WHERE id = ?", (sale_id,)).fetchone()
    if sale is None:
        conn.close()
        abort(404)
    items = conn.execute(
        """SELECT si.mode, si.strips, si.price_strip, m.name, m.strength
           FROM sale_items si
           JOIN medicines m ON m.id = si.medicine_id
           WHERE si.sale_id = ?""",
        (sale_id,),
    ).fetchall()
    conn.close()
    return render_template("bill.html", sale=dict(sale), items=rows_as_dicts(items))
