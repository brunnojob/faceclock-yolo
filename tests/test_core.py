import tempfile
import unittest
from pathlib import Path
from app.core import AttendanceStore


class CoreTests(unittest.TestCase):
    def test_consent_review_integrity_and_revocation(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AttendanceStore(
                Path(directory) / "attendance.db", b"e" * 32, b"a" * 32
            )
            vector = [1.0] + [0.0] * 511
            with self.assertRaises(ValueError):
                store.enroll("employee", "Person", [vector] * 3, False)
            store.enroll("employee", "Person", [vector] * 3, True)
            result = store.propose(vector, "clock_in", "camera")
            self.assertEqual(result["decision"], "human_review")
            self.assertEqual(store.export()["events"], [])
            store.confirm(result["reviewId"], "operator", True)
            self.assertTrue(store.verify())
            with self.assertRaises(ValueError):
                store.confirm(result["reviewId"], "operator", True)
            store.revoke("employee")
            self.assertIsNone(store.propose(vector, "clock_out", "camera")["candidate"])
            store.db.execute("UPDATE attendance SET payload='{}'")
            self.assertFalse(store.verify())
            store.db.close()
