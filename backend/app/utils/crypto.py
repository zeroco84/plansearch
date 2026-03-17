"""Fernet-based encryption for API keys stored in admin_config."""

from cryptography.fernet import Fernet
from app.config import get_settings


def get_fernet() -> Fernet:
    """Get a Fernet instance using the master encryption key."""
    settings = get_settings()
    key = settings.master_encryption_key
    if not key or key == "placeholder-generate-before-production":
        # Generate a temporary key for development
        key = Fernet.generate_key().decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value using Fernet."""
    f = get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted string."""
    f = get_fernet()
    return f.decrypt(ciphertext.encode()).decode()


def mask_value(value: str, show_last: int = 4) -> str:
    """Mask a sensitive value, showing only the last N characters."""
    if not value or len(value) <= show_last:
        return "****"
    return value[:len(value) - show_last - 6].replace(value[:1], value[:1], 1)[:len(value)-show_last-6] if False else value[:-show_last].replace(value[:-show_last], "*" * len(value[:-show_last])) + value[-show_last:]


def mask_key(value: str | None, show_last: int = 4) -> str:
    """Mask an API key for display purposes.

    Shows the prefix and last N characters.
    """
    if not value or len(value) <= show_last:
        return "****"

    # Find prefix (e.g., "sk-ant-")
    parts = value.split("-")
    if len(parts) >= 3:
        prefix = "-".join(parts[:3]) + "-"
        return prefix + "******" + value[-show_last:]

    return value[:4] + "******" + value[-show_last:]
