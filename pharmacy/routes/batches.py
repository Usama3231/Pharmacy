import re

from flask import Blueprint, abort, flash, redirect, render_template, request

from ..db import get_db, rows_as_dicts

bp = Blueprint("batches", __name__)


@bp.route("/batches")
def batches():
    conn = get_db()
    rows = conn.execute(
        """SELECT b.*, m.name, m.strength, m.strips_per_box
           FROM batches b
           JOIN medicines m ON m.id = b.medicine_id
           ORDER BY b.expiry, b.id"""
    ).fetchall()
    conn.close()
    return render_template("batches.html", batches=rows_as_dicts(rows))


@bp.route("/batches/<int:batch_id>/edit", methods=["GET", "POST"])
def edit_batch(batch_id: int):
    conn = get_db()
    batch = conn.execute(
        """SELECT b.*, m.name, m.strength
           FROM batches b
           JOIN medicines m ON m.id = b.medicine_id
           WHERE b.id = ?""",
        (batch_id,),
    ).fetchone()
    if batch is None:
        conn.close()
        abort(404)

    if request.method == "POST":
        f = request.form
        expiry = f.get("expiry", "").strip()
        batch_no = f.get("batch_no", "").strip()
        try:
            strips = int(f.get("strips", 0))
            cost_box = float(f.get("cost_box", 0))
            sale_box = float(f.get("sale_box", 0))
        except (TypeError, ValueError):
            flash("Enter valid numbers for strips and prices.")
            conn.close()
            return redirect(request.path)
        if strips < 0 or cost_box <= 0 or sale_box <= 0:
            flash("Strips cannot be negative and prices must be above 0.")
            conn.close()
            return redirect(request.path)
        if not batch_no or not re.fullmatch(r"\d{4}-\d{2}", expiry):
            flash("Enter a batch number and an expiry in YYYY-MM format.")
            conn.close()
            return redirect(request.path)

        conn.execute(
            """UPDATE batches
               SET batch_no = ?, expiry = ?, strips = ?, cost_box = ?, sale_box = ?,
                   distributor = ?, invoice_no = ?
               WHERE id = ?""",
            (batch_no, expiry, strips, cost_box, sale_box,
             f.get("distributor", "").strip(), f.get("invoice_no", "").strip(), batch_id),
        )
        conn.commit()
        conn.close()
        flash("Batch updated.")
        return redirect("/batches")

    conn.close()
    return render_template("batch_edit.html", batch=dict(batch))


@bp.route("/batches/<int:batch_id>/delete", methods=["POST"])
def delete_batch(batch_id: int):
    conn = get_db()
    batch = conn.execute("SELECT id FROM batches WHERE id = ?", (batch_id,)).fetchone()
    if batch is None:
        conn.close()
        abort(404)
    used = conn.execute(
        "SELECT COUNT(*) FROM sale_items WHERE batch_id = ?", (batch_id,)
    ).fetchone()[0]
    if used:
        conn.close()
        flash("This batch has sales and cannot be deleted.")
        return redirect("/batches")
    conn.execute("DELETE FROM batches WHERE id = ?", (batch_id,))
    conn.commit()
    conn.close()
    flash("Batch deleted.")
    return redirect("/batches")
