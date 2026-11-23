import os
import tempfile
import unittest

from config import Config, TestConfig
from pharmacy import create_app
from pharmacy.db import get_db, init_db


class PharmacyTests(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(self.db_path)
        self.app = create_app(TestConfig)
        self.app.config["DATABASE"] = self.db_path
        self.app_context = self.app.app_context()
        self.app_context.push()
        init_db()
        self.client = self.app.test_client()

    def tearDown(self):
        self.app_context.pop()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def add_stock(self, **overrides):
        data = {
            "name": "Paracetamol",
            "strength": "500mg",
            "company": "TestCo",
            "strips_per_box": "10",
            "batch_no": "B1",
            "expiry": "2030-12",
            "qty": "2",
            "bonus": "0",
            "cost_box": "100",
            "sale_box": "120",
            "distributor": "Dist",
            "invoice_no": "INV1",
        }
        data.update(overrides)
        return self.client.post("/stock-in", data=data, follow_redirects=True)

    def medicine_id(self):
        conn = get_db()
        row = conn.execute("SELECT id FROM medicines").fetchone()
        conn.close()
        return row["id"]

    def batch_id(self):
        conn = get_db()
        row = conn.execute("SELECT id FROM batches").fetchone()
        conn.close()
        return row["id"]

    def test_home_redirects(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/stock-in", response.headers["Location"])

    def test_pages_render(self):
        for path in ("/stock-in", "/stock", "/sale", "/batches", "/report"):
            self.assertEqual(self.client.get(path).status_code, 200, path)

    def test_stock_in_adds_medicine_and_batch(self):
        response = self.add_stock()
        self.assertEqual(response.status_code, 200)
        conn = get_db()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM medicines").fetchone()[0], 1)
        batch = conn.execute("SELECT strips, cost_box, sale_box FROM batches").fetchone()
        self.assertEqual(batch["strips"], 20)
        self.assertAlmostEqual(batch["cost_box"], 100.0)
        self.assertAlmostEqual(batch["sale_box"], 120.0)
        conn.close()

    def test_stock_in_rejects_bad_numbers(self):
        response = self.client.post("/stock-in", data={
            "name": "Bad", "qty": "abc", "expiry": "2030-12", "batch_no": "B1",
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        conn = get_db()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM medicines").fetchone()[0], 0)
        conn.close()

    def test_stock_in_averages_bonus_cost(self):
        self.add_stock(qty="2", bonus="1", cost_box="90")
        conn = get_db()
        batch = conn.execute("SELECT strips, cost_box FROM batches").fetchone()
        self.assertEqual(batch["strips"], 30)
        self.assertAlmostEqual(batch["cost_box"], 60.0)
        conn.close()

    def test_sale_calculates_total_and_profit(self):
        self.add_stock()
        response = self.client.post("/sell", json={
            "lines": [{"id": self.medicine_id(), "mode": "box", "qty": 1}],
            "customer": "Ali",
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["ok"])
        self.assertAlmostEqual(data["total"], 120.0)
        conn = get_db()
        sale = conn.execute("SELECT total, profit, customer FROM sales").fetchone()
        self.assertAlmostEqual(sale["total"], 120.0)
        self.assertAlmostEqual(sale["profit"], 20.0)
        self.assertEqual(sale["customer"], "Ali")
        self.assertEqual(conn.execute("SELECT SUM(strips) FROM batches").fetchone()[0], 10)
        conn.close()

    def test_sale_rejects_unknown_medicine(self):
        response = self.client.post("/sell", json={
            "lines": [{"id": 999, "mode": "box", "qty": 1}],
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_sale_rejects_insufficient_stock(self):
        self.add_stock(qty="1")
        response = self.client.post("/sell", json={
            "lines": [{"id": self.medicine_id(), "mode": "box", "qty": 2}],
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("Not enough stock", response.get_json()["error"])

    def test_report_and_bill(self):
        self.add_stock()
        sale = self.client.post("/sell", json={
            "lines": [{"id": self.medicine_id(), "mode": "strip", "qty": 2}],
            "customer": "Sara",
        }).get_json()
        report = self.client.get("/report")
        self.assertEqual(report.status_code, 200)
        self.assertIn(b"Latest bills", report.data)
        bill = self.client.get(f"/bill/{sale['bill_id']}")
        self.assertEqual(bill.status_code, 200)
        self.assertIn(b"Sara", bill.data)

    def test_low_stock_badge(self):
        self.add_stock(qty="1")
        response = self.client.get("/stock")
        self.assertIn(b"badge low", response.data)

    def test_expired_badge(self):
        self.add_stock(expiry="2020-01")
        response = self.client.get("/stock")
        self.assertIn(b"badge expired", response.data)

    def test_batch_edit_and_delete(self):
        self.add_stock()
        batch_id = self.batch_id()
        response = self.client.post(f"/batches/{batch_id}/edit", data={
            "batch_no": "B2", "expiry": "2031-01", "strips": "15",
            "cost_box": "110", "sale_box": "130", "distributor": "NewDist",
            "invoice_no": "INV2",
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        conn = get_db()
        batch = conn.execute("SELECT batch_no, strips FROM batches WHERE id = ?", (batch_id,)).fetchone()
        self.assertEqual(batch["batch_no"], "B2")
        self.assertEqual(batch["strips"], 15)
        conn.close()
        response = self.client.post(f"/batches/{batch_id}/delete", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        conn = get_db()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM batches").fetchone()[0], 0)
        conn.close()

    def test_csrf_blocks_post_without_token(self):
        app = create_app(Config)
        app.config["DATABASE"] = self.db_path
        app.config["CSRF_ENABLED"] = True
        client = app.test_client()
        response = client.post("/stock-in", data={"name": "X"})
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Invalid CSRF token", response.data)

    def test_csrf_accepts_token(self):
        app = create_app(Config)
        app.config["DATABASE"] = self.db_path
        app.config["CSRF_ENABLED"] = True
        client = app.test_client()
        with client.session_transaction() as session:
            session["csrf_token"] = "test-token"
        response = client.post("/stock-in", data={
            "csrf_token": "test-token", "name": "X", "qty": "1", "batch_no": "B1",
            "expiry": "2030-12", "cost_box": "10", "sale_box": "12", "strips_per_box": "10",
        })
        self.assertEqual(response.status_code, 302)

    def test_unknown_page_returns_404(self):
        response = self.client.get("/does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertIn(b"Page not found", response.data)


if __name__ == "__main__":
    unittest.main()
