import os
import sqlite3
from datetime import date, datetime
from flask import Flask, render_template, request, redirect, flash, jsonify

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "pharmacy.db")

app = Flask(__name__)
app.secret_key = "change-this-later"

SCHEMA = """
CREATE TABLE IF NOT EXISTS medicines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    strength TEXT NOT NULL DEFAULT '',
    company TEXT,
    strips_per_box INTEGER NOT NULL DEFAULT 1,
    UNIQUE (name, strength)
);

CREATE TABLE IF NOT EXISTS batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    medicine_id INTEGER NOT NULL REFERENCES medicines(id),
    distributor TEXT,
    invoice_no TEXT,
    batch_no TEXT NOT NULL,
    expiry TEXT NOT NULL,
    strips INTEGER NOT NULL,
    cost_box REAL NOT NULL,
    sale_box REAL NOT NULL,
    received_on TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created TEXT NOT NULL,
    customer TEXT NOT NULL DEFAULT '',
    total REAL NOT NULL,
    profit REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS sale_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL REFERENCES sales(id),
    medicine_id INTEGER NOT NULL REFERENCES medicines(id),
    batch_id INTEGER NOT NULL REFERENCES batches(id),
    mode TEXT NOT NULL,
    strips INTEGER NOT NULL,
    price_strip REAL NOT NULL,
    cost_strip REAL NOT NULL
);
"""


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(sales)")]
    if "customer" not in cols:
        conn.execute("ALTER TABLE sales ADD COLUMN customer TEXT NOT NULL DEFAULT ''")
    conn.commit()
    conn.close()


@app.route("/")
def home():
    return redirect("/stock-in")


@app.route("/stock-in", methods=["GET", "POST"])
def stock_in():
    conn = get_db()

    if request.method == "POST":
        f = request.form
        name = f["name"].strip()
        strength = f["strength"].strip()
        qty = int(f["qty"])
        bonus = int(f["bonus"] or 0)
        cost_box = float(f["cost_box"])
        sale_box = float(f["sale_box"])

        if not name or qty <= 0:
            flash("Enter a medicine name and a quantity above 0.")
            conn.close()
            return redirect("/stock-in")

        med = conn.execute(
            """SELECT * FROM medicines
               WHERE name = ? COLLATE NOCASE AND strength = ? COLLATE NOCASE""",
            (name, strength),
        ).fetchone()

        if med is None:
            spb = int(f["strips_per_box"])
            cur = conn.execute(
                """INSERT INTO medicines (name, strength, company, strips_per_box)
                   VALUES (?, ?, ?, ?)""",
                (name, strength, f["company"].strip(), spb),
            )
            med_id = cur.lastrowid
        else:
            med_id = med["id"]
            spb = med["strips_per_box"]

        total_boxes = qty + bonus
        real_cost = cost_box * qty / total_boxes  # bonus boxes cost nothing

        conn.execute(
            """INSERT INTO batches
               (medicine_id, distributor, invoice_no, batch_no, expiry,
                strips, cost_box, sale_box, received_on)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (med_id, f["distributor"].strip(), f["invoice_no"].strip(),
             f["batch_no"].strip(), f["expiry"], total_boxes * spb,
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
    return render_template("stock_in.html", medicines=[dict(r) for r in rows])

@app.route("/stock")
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
    soon_limit = f"{y}-{m:02d}"  # expiring within about 3 months

    items = []
    expired = soon = 0
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
        items.append({
            "name": r["name"],
            "strength": r["strength"],
            "company": r["company"],
            "boxes": r["strips"] // spb,
            "loose": r["strips"] % spb,
            "expiry": r["expiry"],
            "status": status,
        })

    return render_template("stock.html", items=items, expired=expired, soon=soon)
@app.route("/sale")
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
    return render_template("sale.html", medicines=[dict(r) for r in rows])


@app.route("/sell", methods=["POST"])
def sell():
    data = request.get_json()
    lines = data.get("lines", [])
    customer = (data.get("customer") or "").strip()
    if not lines:
        return jsonify(error="The bill is empty."), 400

    conn = get_db()
    total = profit = 0.0
    items = []
    try:
        for ln in lines:
            med = conn.execute(
                "SELECT * FROM medicines WHERE id = ?", (ln["id"],)
            ).fetchone()
            qty = int(ln["qty"])
            if qty <= 0:
                raise ValueError("Quantity must be above 0.")
            spb = med["strips_per_box"]
            need = qty * spb if ln["mode"] == "box" else qty

            # sell the batch that expires first
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
                items.append((med["id"], b["id"], ln["mode"], take, price, cost))
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
    return jsonify(ok=True, total=round(total, 2))
@app.route("/report")
def report():
    conn = get_db()
    today = date.today().strftime("%Y-%m-%d")
    month = today[:7]

    def totals(prefix):
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
    return render_template("report.html", day=day, mon=mon, recent=recent)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)