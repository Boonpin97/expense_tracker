import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.dashboard_auth import (
    hash_password,
    is_valid_username,
    normalize_username,
    session_doc_id,
    validate_password,
    verify_password,
)


class DashboardAuthTests(unittest.TestCase):
    def test_username_normalization_and_validation(self):
        self.assertEqual(normalize_username("  Alice.Admin "), "alice.admin")
        self.assertTrue(is_valid_username("alice.admin"))
        self.assertTrue(is_valid_username("alice_admin-1"))
        self.assertFalse(is_valid_username("ab"))
        self.assertFalse(is_valid_username("alice admin"))

    def test_password_hash_round_trip(self):
        password = "correct horse battery staple"
        hashed = hash_password(password)
        self.assertNotEqual(hashed, password)
        self.assertTrue(verify_password(password, hashed))
        self.assertFalse(verify_password("wrong password", hashed))

    def test_password_validation_and_session_doc_id(self):
        self.assertIsNotNone(validate_password("short"))
        self.assertIsNone(validate_password("long-enough-password"))
        self.assertEqual(session_doc_id("abc123"), session_doc_id("abc123"))
        self.assertNotEqual(session_doc_id("abc123"), session_doc_id("xyz789"))


if __name__ == "__main__":
    unittest.main()
