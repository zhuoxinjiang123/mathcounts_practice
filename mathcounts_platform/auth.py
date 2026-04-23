import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone


PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 200_000
SESSION_DAYS = 30


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return "$".join(
        [
            PASSWORD_ALGORITHM,
            str(PASSWORD_ITERATIONS),
            salt.hex(),
            digest.hex(),
        ]
    )


def verify_password(password, stored_hash):
    try:
        algorithm, iterations_text, salt_hex, digest_hex = stored_hash.split("$", 3)
        if algorithm != PASSWORD_ALGORITHM:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations_text),
        )
    except (AttributeError, TypeError, ValueError):
        return False

    return hmac.compare_digest(digest.hex(), digest_hex)


def hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(conn, user_id):
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    conn.execute(
        """
        INSERT INTO sessions (user_id, token_hash, expires_at)
        VALUES (?, ?, ?)
        """,
        (int(user_id), hash_token(token), expires_at.isoformat(timespec="seconds")),
    )
    conn.commit()
    return token
