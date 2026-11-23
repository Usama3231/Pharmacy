import os
import tempfile
import unittest

import app as pharmacy


class PharmacyTests(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(self.db_path)
        pharmacy.DB_PATH = self.db_path
        pharmacy.app.config["TESTING"] = True
        pharmacy.init_db()
        self.client = pharmacy.app.test_client()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def add_stock(self):
        return self.client.post("/stock-in", data={
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
        }, follow_redirects=True)

    def medicine_id(self):
        conn = pharmacy.get_db()
        row = conn.execute("SELECT id FROM medicines").fetchone()
        conn.close()
        return row["id"]

    def test_home_redirects(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/stock-in", response.headers["Location"])

    def test_pages_render(self):
        for path in ("/stock-in", "/stock", "/sale", "/report"):
            self.assertEqual(self.client.get(path).status_code, 200, path)

    def test_stock_in_adds_medicine_and_batch(self):
        response = self.add_stock()
        self.assertEqual(response.status_code, 200)
        conn = pharmacy.get_db()
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
        conn = pharmacy.get_db()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM medicines").fetchone()[0], 0)
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
        conn = pharmacy.get_db()
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

    def test_report_shows_totals(self):
        self.add_stock()
        self.client.post("/sell", json={
            "lines": [{"id": self.medicine_id(), "mode": "strip", "qty": 2}],
        })
        response = self.client.get("/report")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Latest bills", response.data)


if __name__ == "__main__":
    unittest.main()
