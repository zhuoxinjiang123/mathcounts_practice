import sqlite3
import unittest

from mathcounts_platform.auth import create_session, hash_password, hash_token, verify_password
from mathcounts_platform.db import create_user, get_user_for_session, migrate


class AuthTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        migrate(self.conn)

    def test_password_hash_roundtrip(self):
        hashed = hash_password("secret-pass")
        self.assertTrue(verify_password("secret-pass", hashed))
        self.assertFalse(verify_password("wrong-pass", hashed))

    def test_session_roundtrip(self):
        user_id = create_user(self.conn, "student@example.com", hash_password("secret-pass"))
        token = create_session(self.conn, user_id)
        self.assertNotEqual(token, hash_token(token))
        self.assertEqual(get_user_for_session(self.conn, token)["id"], user_id)
