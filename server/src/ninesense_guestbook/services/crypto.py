import base64
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


CONTACT_AAD_V1 = b"ninesense-contact-v1"


@dataclass(frozen=True)
class EncryptedContact:
    nonce: bytes
    ciphertext: bytes
    key_version: int = 1


class ContactCipher:
    def __init__(self, key: bytes):
        if len(key) != 32:
            raise ValueError("contact encryption key must be 32 bytes")
        self._cipher = AESGCM(key)

    @classmethod
    def from_urlsafe_key(cls, value: str) -> "ContactCipher":
        try:
            key = base64.b64decode(value.encode("ascii"), altchars=b"-_", validate=True)
        except (ValueError, UnicodeEncodeError) as error:
            raise ValueError("contact encryption key must be URL-safe base64") from error
        return cls(key)

    def encrypt(self, value: str) -> EncryptedContact:
        nonce = os.urandom(12)
        ciphertext = self._cipher.encrypt(nonce, value.encode("utf-8"), CONTACT_AAD_V1)
        return EncryptedContact(nonce=nonce, ciphertext=ciphertext)

    def decrypt(self, value: EncryptedContact) -> str:
        if value.key_version != 1:
            raise ValueError(f"unsupported contact key version: {value.key_version}")
        plaintext = self._cipher.decrypt(
            value.nonce,
            value.ciphertext,
            CONTACT_AAD_V1,
        )
        return plaintext.decode("utf-8")

