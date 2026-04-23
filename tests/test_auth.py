from datetime import datetime, timedelta, timezone
import sqlite3
import unittest

from mathcounts_platform.auth import (
    create_password_reset_token,
    create_session,
    hash_password,
    hash_token,
    verify_password,
)
from mathcounts_platform.db import (
    create_user,
    get_user_by_email,
    get_user_for_password_reset_token,
    get_user_for_session,
    mark_password_reset_token_used,
    migrate,
    update_user_password,
)


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

    def test_password_reset_token_roundtrip_and_password_update(self):
        user_id = create_user(self.conn, "student@example.com", hash_password("old-password"))
        token = create_password_reset_token(self.conn, user_id)

        reset_user = get_user_for_password_reset_token(self.conn, token)
        self.assertEqual(reset_user["id"], user_id)

        update_user_password(self.conn, user_id, hash_password("new-password"))
        mark_password_reset_token_used(self.conn, token)

        user = get_user_by_email(self.conn, "student@example.com")
        self.assertTrue(verify_password("new-password", user["password_hash"]))
        self.assertIsNone(get_user_for_password_reset_token(self.conn, token))

    def test_expired_password_reset_token_is_rejected(self):
        user_id = create_user(self.conn, "student@example.com", hash_password("old-password"))
        token = create_password_reset_token(
            self.conn,
            user_id,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )

        self.assertIsNone(get_user_for_password_reset_token(self.conn, token))
