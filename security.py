"""DataSecurity class (class diagram): encryption, password hashing, access control, audit."""
import base64
import hashlib
import hmac
import os
from datetime import datetime
from typing import List, Optional

from cryptography.fernet import Fernet, InvalidToken

from . import config


class DataSecurity:
    def __init__(self, repo=None, secret: str = config.ENCRYPTION_SECRET,
                 iterations: int = config.PBKDF2_ITERATIONS, now=datetime.now):
        self.repo = repo
        self.now = now
        self.iterations = iterations
        self.protocol = "Fernet (AES-128-CBC + HMAC-SHA256)"
        self.encryption_key: str = base64.urlsafe_b64encode(
            hashlib.sha256(secret.encode("utf-8")).digest()).decode("ascii")
        self.last_audit: Optional[datetime] = None
        self._fernet = Fernet(self.encryption_key.encode("ascii"))

    # ---- encryptData / decryptData
    def encrypt_data(self, data: str) -> str:
        return self._fernet.encrypt(data.encode("utf-8")).decode("ascii")

    def decrypt_data(self, data: str) -> str:
        try:
            return self._fernet.decrypt(data.encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError) as exc:
            raise ValueError("Data could not be decrypted (wrong key or corrupted data)") from exc

    # ---- passwords (never stored in plain text)
    def hash_password(self, password: str, salt: Optional[bytes] = None) -> str:
        salt = salt or os.urandom(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, self.iterations)
        return f"pbkdf2_sha256${self.iterations}${salt.hex()}${digest.hex()}"

    @staticmethod
    def verify_password(password: str, stored: str) -> bool:
        try:
            scheme, iterations, salt_hex, hash_hex = stored.split("$")
            if scheme != "pbkdf2_sha256":
                return False
            digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                         bytes.fromhex(salt_hex), int(iterations))
            return hmac.compare_digest(digest.hex(), hash_hex)
        except (ValueError, AttributeError):
            return False

    # ---- enforceAccessControl(userID)
    def enforce_access_control(self, user_id, required_level: int = config.ACCESS_ADMIN) -> bool:
        """True only if the user exists and has at least `required_level` (admin by default)."""
        user = self.repo.get_user(user_id) if self.repo is not None else None
        return user is not None and user.access_level >= required_level

    # ---- performAudit()
    def perform_audit(self) -> List[str]:
        """Check accounts for weak points. Returns a list of findings (empty = clean)."""
        findings: List[str] = []
        users = self.repo.get_users() if self.repo is not None else []
        for user in users:
            if not user.password_hash:
                findings.append(f"{user.username or user.name}: no password set")
            elif self.verify_password(config.DEFAULT_PASSWORD, user.password_hash):
                findings.append(f"{user.username}: still uses the default password")
        if users and not any(u.role == "admin" for u in users):
            findings.append("No administrator account exists")
        self.last_audit = self.now()
        return findings
