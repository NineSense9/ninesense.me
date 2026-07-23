import base64
import hashlib
import hmac
import secrets
import struct
from urllib.parse import quote, urlencode


def generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _decode_secret(secret: str) -> bytes:
    normalized = secret.strip().replace(" ", "").upper()
    padding = "=" * ((8 - len(normalized) % 8) % 8)
    return base64.b32decode(normalized + padding, casefold=True)


def totp_at(
    secret: str,
    unix_time: int | float,
    digits: int = 6,
    period: int = 30,
) -> str:
    if digits not in {6, 8} or period <= 0:
        raise ValueError("invalid TOTP parameters")
    counter = int(unix_time) // period
    digest = hmac.new(
        _decode_secret(secret),
        struct.pack(">Q", counter),
        hashlib.sha1,
    ).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % (10**digits)).zfill(digits)


def verify_totp(
    secret: str,
    code: str,
    unix_time: int | float,
    window: int = 1,
) -> bool:
    normalized = code.strip()
    if (
        len(normalized) != 6
        or not normalized.isascii()
        or not normalized.isdigit()
    ):
        return False
    return any(
        hmac.compare_digest(totp_at(secret, unix_time + step * 30), normalized)
        for step in range(-window, window + 1)
    )


def build_otpauth_uri(
    secret: str,
    username: str,
    issuer: str = "NineSense",
) -> str:
    label = quote(f"{issuer}:{username.strip()}", safe="")
    query = urlencode(
        {
            "secret": secret,
            "issuer": issuer,
            "algorithm": "SHA1",
            "digits": 6,
            "period": 30,
        }
    )
    return f"otpauth://totp/{label}?{query}"


def generate_recovery_codes(count: int = 10) -> list[str]:
    if count < 1 or count > 20:
        raise ValueError("invalid recovery code count")
    codes: list[str] = []
    while len(codes) < count:
        raw = secrets.token_hex(8).upper()
        code = "-".join(raw[index : index + 4] for index in range(0, 16, 4))
        if code not in codes:
            codes.append(code)
    return codes


def normalize_recovery_code(code: str) -> str:
    normalized = code.replace("-", "").replace(" ", "").upper()
    if len(normalized) != 16 or any(
        character not in "0123456789ABCDEF" for character in normalized
    ):
        raise ValueError("invalid recovery code")
    return normalized


def hash_recovery_code(code: str, pepper: str) -> str:
    return hmac.new(
        pepper.encode("utf-8"),
        normalize_recovery_code(code).encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
