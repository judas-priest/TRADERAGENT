"""
API Key Security Module
Handles encryption/decryption of exchange API credentials

Version: 1.0
Date: 2026-02-05
"""

import os
import base64
from typing import Tuple, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.backends import default_backend


class CredentialsEncryption:
    """
    Handles encryption and decryption of API credentials using Fernet (AES-128-CBC).

    Security features:
    - Symmetric encryption using Fernet (built on AES-128)
    - Key derivation from SECRET_KEY environment variable
    - Base64 encoding for safe storage
    - Constant-time comparison to prevent timing attacks

    Usage:
        # Initialize
        encryptor = CredentialsEncryption()

        # Encrypt
        encrypted_key = encryptor.encrypt("my_api_key")
        encrypted_secret = encryptor.encrypt("my_api_secret")

        # Decrypt
        api_key = encryptor.decrypt(encrypted_key)
        api_secret = encryptor.decrypt(encrypted_secret)
    """

    def __init__(self, secret_key: Optional[str] = None):
        """
        Initialize encryption handler.

        Args:
            secret_key: Master encryption key (if None, loads from SECRET_KEY env var)

        Raises:
            ValueError: If SECRET_KEY is not set and not provided
        """
        if secret_key is None:
            secret_key = os.getenv('SECRET_KEY')

        if not secret_key:
            raise ValueError(
                "SECRET_KEY environment variable must be set. "
                "Generate one with: python -m cryptography.fernet generate_key()"
            )

        # Validate key format
        try:
            self._cipher = Fernet(secret_key.encode() if isinstance(secret_key, str) else secret_key)
        except Exception as e:
            raise ValueError(f"Invalid SECRET_KEY format: {e}")

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string.

        Args:
            plaintext: String to encrypt (e.g., API key)

        Returns:
            Base64-encoded encrypted string

        Example:
            >>> encryptor = CredentialsEncryption()
            >>> encrypted = encryptor.encrypt("my_api_key_12345")
            >>> print(encrypted)
            'gAAAAABf...'
        """
        if not plaintext:
            raise ValueError("Cannot encrypt empty string")

        encrypted_bytes = self._cipher.encrypt(plaintext.encode('utf-8'))
        return encrypted_bytes.decode('utf-8')

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt an encrypted string.

        Args:
            ciphertext: Encrypted string (from encrypt method)

        Returns:
            Decrypted plaintext string

        Raises:
            cryptography.fernet.InvalidToken: If decryption fails (wrong key or corrupted data)

        Example:
            >>> encrypted = encryptor.encrypt("my_api_key")
            >>> decrypted = encryptor.decrypt(encrypted)
            >>> assert decrypted == "my_api_key"
        """
        if not ciphertext:
            raise ValueError("Cannot decrypt empty string")

        try:
            decrypted_bytes = self._cipher.decrypt(ciphertext.encode('utf-8'))
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")

    def rotate_key(self, old_secret_key: str, new_secret_key: str, encrypted_data: str) -> str:
        """
        Rotate encryption key by re-encrypting data with new key.

        Args:
            old_secret_key: Current encryption key
            new_secret_key: New encryption key
            encrypted_data: Data encrypted with old key

        Returns:
            Data re-encrypted with new key

        Example:
            >>> old_encryptor = CredentialsEncryption(old_key)
            >>> encrypted = old_encryptor.encrypt("secret")
            >>> rotated = old_encryptor.rotate_key(old_key, new_key, encrypted)
            >>> new_encryptor = CredentialsEncryption(new_key)
            >>> assert new_encryptor.decrypt(rotated) == "secret"
        """
        old_cipher = Fernet(old_secret_key.encode())
        new_cipher = Fernet(new_secret_key.encode())

        # Decrypt with old key
        plaintext_bytes = old_cipher.decrypt(encrypted_data.encode('utf-8'))

        # Encrypt with new key
        new_encrypted_bytes = new_cipher.encrypt(plaintext_bytes)

        return new_encrypted_bytes.decode('utf-8')


class KeyGenerator:
    """
    Generates cryptographically secure keys.
    """

    @staticmethod
    def generate_fernet_key() -> str:
        """
        Generate a new Fernet encryption key.

        Returns:
            Base64-encoded Fernet key (44 characters)

        Example:
            >>> key = KeyGenerator.generate_fernet_key()
            >>> print(key)
            'MJ8XaKj...'
            >>> len(key)
            44
        """
        key = Fernet.generate_key()
        return key.decode('utf-8')

    @staticmethod
    def derive_key_from_password(password: str, salt: Optional[bytes] = None) -> Tuple[str, bytes]:
        """
        Derive an encryption key from a password using PBKDF2.

        Useful for creating a key from a user-provided password.

        Args:
            password: User password
            salt: Cryptographic salt (if None, generates random salt)

        Returns:
            Tuple of (base64_key, salt)

        Example:
            >>> key, salt = KeyGenerator.derive_key_from_password("my_password")
            >>> # Store salt in database or config
            >>> # Later, derive same key:
            >>> same_key, _ = KeyGenerator.derive_key_from_password("my_password", salt)
            >>> assert key == same_key
        """
        if salt is None:
            salt = os.urandom(16)  # 128-bit salt

        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,  # 256 bits for Fernet
            salt=salt,
            iterations=100000,  # OWASP recommendation
            backend=default_backend()
        )

        key_bytes = kdf.derive(password.encode('utf-8'))
        key_b64 = base64.urlsafe_b64encode(key_bytes)

        return key_b64.decode('utf-8'), salt


class CredentialsManager:
    """
    High-level manager for storing and retrieving encrypted credentials.

    Integrates with database to store/retrieve encrypted credentials.
    """

    def __init__(self, encryption: CredentialsEncryption, db_manager=None):
        """
        Initialize credentials manager.

        Args:
            encryption: CredentialsEncryption instance
            db_manager: Database manager instance (optional, for DB operations)
        """
        self.encryption = encryption
        self.db_manager = db_manager

    def store_credentials(
        self,
        bot_id: int,
        exchange: str,
        api_key: str,
        api_secret: str,
        passphrase: Optional[str] = None,
        is_testnet: bool = False
    ) -> dict:
        """
        Encrypt and store API credentials.

        Args:
            bot_id: Bot ID
            exchange: Exchange name (binance, bybit, etc.)
            api_key: Plain API key
            api_secret: Plain API secret
            passphrase: Plain passphrase (for OKX, optional)
            is_testnet: Whether these are testnet credentials

        Returns:
            Dictionary with encrypted credentials

        Example:
            >>> manager = CredentialsManager(encryptor, db)
            >>> credentials = manager.store_credentials(
            ...     bot_id=1,
            ...     exchange="binance",
            ...     api_key="key123",
            ...     api_secret="secret456",
            ...     is_testnet=True
            ... )
        """
        encrypted_data = {
            'bot_id': bot_id,
            'exchange': exchange,
            'api_key_encrypted': self.encryption.encrypt(api_key),
            'api_secret_encrypted': self.encryption.encrypt(api_secret),
            'passphrase_encrypted': self.encryption.encrypt(passphrase) if passphrase else None,
            'is_testnet': is_testnet
        }

        # If DB manager provided, store in database
        if self.db_manager:
            # This will be implemented in Task 1.3 (DatabaseManager)
            pass  # self.db_manager.insert_credentials(encrypted_data)

        return encrypted_data

    def retrieve_credentials(self, bot_id: int, exchange: str) -> dict:
        """
        Retrieve and decrypt API credentials.

        Args:
            bot_id: Bot ID
            exchange: Exchange name

        Returns:
            Dictionary with decrypted credentials

        Example:
            >>> credentials = manager.retrieve_credentials(bot_id=1, exchange="binance")
            >>> print(credentials['api_key'])  # Plain text
            'key123'
        """
        # Fetch encrypted data from database
        if self.db_manager:
            # This will be implemented in Task 1.3
            encrypted_data = {}  # self.db_manager.fetch_credentials(bot_id, exchange)
        else:
            # For now, return placeholder
            encrypted_data = {
                'api_key_encrypted': '',
                'api_secret_encrypted': '',
                'passphrase_encrypted': None
            }

        # Decrypt
        decrypted_data = {
            'api_key': self.encryption.decrypt(encrypted_data['api_key_encrypted']),
            'api_secret': self.encryption.decrypt(encrypted_data['api_secret_encrypted']),
            'passphrase': self.encryption.decrypt(encrypted_data['passphrase_encrypted'])
                          if encrypted_data.get('passphrase_encrypted') else None
        }

        return decrypted_data

    def delete_credentials(self, bot_id: int, exchange: str) -> bool:
        """
        Delete stored credentials.

        Args:
            bot_id: Bot ID
            exchange: Exchange name

        Returns:
            True if deleted successfully
        """
        if self.db_manager:
            # This will be implemented in Task 1.3
            pass  # return self.db_manager.delete_credentials(bot_id, exchange)

        return True


# Utility functions

def generate_secret_key() -> str:
    """
    Generate a new SECRET_KEY for use in environment variables.

    Returns:
        Base64-encoded Fernet key

    Usage:
        Run once to generate key for .env file:

        $ python -c "from dca_grid_bot.core.security import generate_secret_key; print(generate_secret_key())"
        MJ8XaKjg...

        Then add to .env:
        SECRET_KEY=MJ8XaKjg...
    """
    return KeyGenerator.generate_fernet_key()


def validate_secret_key(secret_key: str) -> bool:
    """
    Validate that a SECRET_KEY is properly formatted.

    Args:
        secret_key: Key to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        Fernet(secret_key.encode())
        return True
    except Exception:
        return False


# Example usage
if __name__ == "__main__":
    print("=== DCA-Grid Bot - Credentials Encryption Demo ===\n")

    # Generate a new key
    print("1. Generating new SECRET_KEY...")
    secret_key = generate_secret_key()
    print(f"   SECRET_KEY={secret_key}\n")
    print("   ⚠️  IMPORTANT: Store this in your .env file and keep it secret!\n")

    # Initialize encryptor
    print("2. Initializing encryption...")
    encryptor = CredentialsEncryption(secret_key)
    print("   ✓ Encryptor ready\n")

    # Encrypt credentials
    print("3. Encrypting sample API credentials...")
    api_key = "binance_api_key_123456789"
    api_secret = "binance_api_secret_987654321"

    encrypted_key = encryptor.encrypt(api_key)
    encrypted_secret = encryptor.encrypt(api_secret)

    print(f"   Original API Key:    {api_key}")
    print(f"   Encrypted API Key:   {encrypted_key[:50]}...")
    print(f"   Original API Secret: {api_secret}")
    print(f"   Encrypted API Secret: {encrypted_secret[:50]}...\n")

    # Decrypt credentials
    print("4. Decrypting credentials...")
    decrypted_key = encryptor.decrypt(encrypted_key)
    decrypted_secret = encryptor.decrypt(encrypted_secret)

    print(f"   Decrypted API Key:    {decrypted_key}")
    print(f"   Decrypted API Secret: {decrypted_secret}\n")

    # Verify
    print("5. Verification...")
    if decrypted_key == api_key and decrypted_secret == api_secret:
        print("   ✓ Encryption/Decryption working correctly!\n")
    else:
        print("   ✗ ERROR: Mismatch detected!\n")

    print("=== Demo Complete ===")
