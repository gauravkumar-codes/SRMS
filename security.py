"""Password / security-answer hashing.

Uses scrypt (memory-hard, built into Python's hashlib) with a random salt per
secret. The stored format is self-describing so the cost parameters can be
raised later without breaking old hashes:

    scrypt$<N>$<r>$<p>$<salt b64>$<key b64>
"""
import base64
import hashlib
import hmac
import os

_SCHEME = "scrypt"
_N, _R, _P = 2 ** 14, 8, 1
_KEY_LEN = 32
_SALT_LEN = 16
_MAXMEM = 64 * 1024 * 1024

_dummy_hash = None


def _derive(secret: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(secret.encode("utf-8"), salt=salt, n=n, r=r, p=p,
                          dklen=_KEY_LEN, maxmem=_MAXMEM)


def hash_secret(secret: str) -> str:
    salt = os.urandom(_SALT_LEN)
    key = _derive(secret, salt, _N, _R, _P)
    return "$".join([_SCHEME, str(_N), str(_R), str(_P),
                     base64.b64encode(salt).decode(), base64.b64encode(key).decode()])


def is_hashed(stored) -> bool:
    return isinstance(stored, str) and stored.startswith(_SCHEME + "$") and stored.count("$") == 5


def verify_secret(secret: str, stored: str) -> bool:
    """Constant-time check of `secret` against a stored hash."""
    try:
        scheme, n, r, p, salt_b64, key_b64 = stored.split("$")
        if scheme != _SCHEME:
            return False
        expected = base64.b64decode(key_b64)
        actual = _derive(secret, base64.b64decode(salt_b64), int(n), int(r), int(p))
    except (ValueError, TypeError, AttributeError):
        return False
    return hmac.compare_digest(expected, actual)


def burn_time(secret: str) -> None:
    """Spend the same time as a real check.

    Called when the account does not exist, so a response that is fast for
    unknown emails and slow for known ones cannot be used to find valid emails.
    """
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_secret("not-a-real-secret")
    verify_secret(secret, _dummy_hash)


def normalize_answer(answer: str) -> str:
    """'  Delhi  ' and 'delhi' must count as the same security answer."""
    return " ".join((answer or "").strip().lower().split())
