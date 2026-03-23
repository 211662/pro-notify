"""
Encryption Module
Encrypts/decrypts .env file using Fernet (AES-128-CBC + HMAC).
The master password is used to derive the encryption key via PBKDF2.
"""

import os
import base64
import getpass
import logging

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

SALT_FILE = ".salt"
ENCRYPTED_ENV_FILE = ".env.encrypted"
ENV_FILE = ".env"


def _get_project_root() -> str:
    """Get the project root directory."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive an encryption key from password using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key


def encrypt_env(password: str | None = None) -> str:
    """
    Encrypt .env file → .env.encrypted
    Returns path to encrypted file.
    """
    root = _get_project_root()
    env_path = os.path.join(root, ENV_FILE)
    encrypted_path = os.path.join(root, ENCRYPTED_ENV_FILE)
    salt_path = os.path.join(root, SALT_FILE)

    if not os.path.exists(env_path):
        raise FileNotFoundError(f"{ENV_FILE} not found at {root}")

    # Get password
    if password is None:
        password = getpass.getpass("🔑 Enter master password to encrypt: ")
        password_confirm = getpass.getpass("🔑 Confirm password: ")
        if password != password_confirm:
            raise ValueError("Passwords do not match!")

    # Generate salt
    salt = os.urandom(16)
    with open(salt_path, "wb") as f:
        f.write(salt)

    # Derive key and encrypt
    key = _derive_key(password, salt)
    fernet = Fernet(key)

    with open(env_path, "rb") as f:
        env_data = f.read()

    encrypted_data = fernet.encrypt(env_data)

    with open(encrypted_path, "wb") as f:
        f.write(encrypted_data)

    logger.info("✅ Encrypted %s → %s", ENV_FILE, ENCRYPTED_ENV_FILE)
    return encrypted_path


def decrypt_env(password: str | None = None) -> dict[str, str]:
    """
    Decrypt .env.encrypted → returns dict of env vars.
    Does NOT write .env file (keeps secrets in memory only).
    """
    root = _get_project_root()
    encrypted_path = os.path.join(root, ENCRYPTED_ENV_FILE)
    salt_path = os.path.join(root, SALT_FILE)

    if not os.path.exists(encrypted_path):
        raise FileNotFoundError(f"{ENCRYPTED_ENV_FILE} not found at {root}")
    if not os.path.exists(salt_path):
        raise FileNotFoundError(f"{SALT_FILE} not found at {root}")

    # Get password
    if password is None:
        password = getpass.getpass("🔑 Enter master password to decrypt: ")

    # Read salt
    with open(salt_path, "rb") as f:
        salt = f.read()

    # Derive key and decrypt
    key = _derive_key(password, salt)
    fernet = Fernet(key)

    with open(encrypted_path, "rb") as f:
        encrypted_data = f.read()

    try:
        decrypted_data = fernet.decrypt(encrypted_data)
    except InvalidToken:
        raise ValueError("❌ Wrong password! Cannot decrypt.")

    # Parse env vars
    env_vars = {}
    for line in decrypted_data.decode("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key_name, value = line.split("=", 1)
            env_vars[key_name.strip()] = value.strip()

    logger.info("✅ Decrypted %s successfully (loaded %d vars in memory).", ENCRYPTED_ENV_FILE, len(env_vars))
    return env_vars


def has_encrypted_env() -> bool:
    """Check if encrypted env file exists."""
    root = _get_project_root()
    return os.path.exists(os.path.join(root, ENCRYPTED_ENV_FILE))


# ── CLI ──────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m src.encryption encrypt   # Encrypt .env → .env.encrypted")
        print("  python -m src.encryption decrypt   # Test decrypt .env.encrypted")
        sys.exit(1)

    action = sys.argv[1].lower()

    if action == "encrypt":
        encrypt_env()
        print(f"\n✅ Done! File '{ENCRYPTED_ENV_FILE}' created.")
        print(f"   You can now safely DELETE '{ENV_FILE}' and commit '{ENCRYPTED_ENV_FILE}' + '{SALT_FILE}'.")
        print(f"   ⚠️  Remember your master password — it cannot be recovered!")

    elif action == "decrypt":
        env_vars = decrypt_env()
        print(f"\n✅ Decrypted {len(env_vars)} variables:")
        for k, v in env_vars.items():
            masked = v[:4] + "****" if len(v) > 4 else "****"
            print(f"   {k} = {masked}")

    else:
        print(f"Unknown action: {action}")
        sys.exit(1)
