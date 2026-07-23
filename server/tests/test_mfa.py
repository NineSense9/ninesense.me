import base64

import pytest

from ninesense_guestbook.services.mfa import (
    build_otpauth_uri,
    generate_recovery_codes,
    generate_totp_secret,
    hash_recovery_code,
    normalize_recovery_code,
    totp_at,
    verify_totp,
)


def test_totp_matches_rfc6238_sha1_vector():
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"

    assert totp_at(secret, 59, digits=8) == "94287082"


def test_totp_accepts_one_step_clock_drift_only():
    secret = "JBSWY3DPEHPK3PXP"
    code = totp_at(secret, 1_800_000_000)

    assert verify_totp(secret, code, 1_800_000_030)
    assert not verify_totp(secret, code, 1_800_000_090)


def test_totp_rejects_non_numeric_or_wrong_length_codes():
    secret = "JBSWY3DPEHPK3PXP"

    assert not verify_totp(secret, "12345", 1_800_000_000)
    assert not verify_totp(secret, "ABC123", 1_800_000_000)


def test_generated_secret_is_valid_base32_with_160_bits():
    secret = generate_totp_secret()
    padding = "=" * ((8 - len(secret) % 8) % 8)

    assert len(base64.b32decode(secret + padding)) == 20


def test_otpauth_uri_contains_encoded_identity_and_parameters():
    uri = build_otpauth_uri("JBSWY3DPEHPK3PXP", "nine sense")

    assert uri.startswith("otpauth://totp/NineSense%3Anine%20sense?")
    assert "secret=JBSWY3DPEHPK3PXP" in uri
    assert "issuer=NineSense" in uri


def test_recovery_codes_are_unique_and_only_hashes_need_persisting():
    codes = generate_recovery_codes()

    assert len(codes) == len(set(codes)) == 10
    assert all(len(code.replace("-", "")) == 16 for code in codes)
    assert hash_recovery_code(codes[0], "pepper") != codes[0]
    assert hash_recovery_code(codes[0], "pepper") == hash_recovery_code(
        codes[0].lower().replace("-", " "), "pepper"
    )


@pytest.mark.parametrize("value", ["", "1234", "GGGG-0000-0000-0000", "0" * 17])
def test_recovery_code_normalization_rejects_invalid_values(value):
    with pytest.raises(ValueError, match="invalid recovery code"):
        normalize_recovery_code(value)
