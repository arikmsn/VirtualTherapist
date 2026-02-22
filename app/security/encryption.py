"""
Data encryption module
CRITICAL: All patient data must be encrypted at rest!
"""

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64

from app.core.config import settings
from loguru import logger


class EncryptionService:
    """
    Encryption service for sensitive data.
    Uses AES-256 encryption via Fernet.
    """

    def __init__(self) -> None:
        # Derive encryption key from settings
        self.key = self._derive_key(settings.ENCRYPTION_KEY)
        self.cipher = Fernet(self.key)

    def _derive_key(self, password: str) -> bytes:
        """Derive a secure encryption key from password."""

        # Use PBKDF2HMAC to derive a key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"therapy_companion_salt",  # In production, use unique salt per installation
            iterations=100000,
            backend=default_backend(),
        )

        key = base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))
        return key

    def encrypt(self, data: str) -> str:
        """
        Encrypt sensitive data.

        Args:
            data: Plain text data to encrypt.

        Returns:
            Encrypted data as string.
        """
        if not data:
            return ""

        try:
            encrypted = self.cipher.encrypt(data.encode("utf-8"))
            return encrypted.decode("utf-8")
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            raise

    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt sensitive data.

        Args:
            encrypted_data: Encrypted data.

        Returns:
            Decrypted plain text.
        """
        if not encrypted_data:
            return ""

        try:
            decrypted = self.cipher.decrypt(encrypted_data.encode("utf-8"))
            return decrypted.decode("utf-8")
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            raise


# Global encryption service instance
encryption_service = EncryptionService()


# Convenience functions
def encrypt_data(data: str) -> str:
    """Encrypt data using global encryption service."""
    return encryption_service.encrypt(data)


def decrypt_data(encrypted_data: str) -> str:
    """Decrypt data using global encryption service."""
    return encryption_service.decrypt(encrypted_data)
