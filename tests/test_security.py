"""Tests for security features"""

import pytest
from app.security.encryption import encrypt_data, decrypt_data
from app.security.auth import get_password_hash, verify_password, create_access_token, decode_access_token


def test_encryption_decryption():
    """Test data encryption and decryption"""
    original_text = "Sensitive patient data"

    # Encrypt
    encrypted = encrypt_data(original_text)
    assert encrypted != original_text
    assert len(encrypted) > 0

    # Decrypt
    decrypted = decrypt_data(encrypted)
    assert decrypted == original_text


def test_encryption_empty_string():
    """Test encryption of empty string"""
    encrypted = encrypt_data("")
    assert encrypted == ""

    decrypted = decrypt_data("")
    assert decrypted == ""


def test_password_hashing():
    """Test password hashing and verification"""
    password = "secure_password_123"

    # Hash password
    hashed = get_password_hash(password)
    assert hashed != password
    assert len(hashed) > 0

    # Verify correct password
    assert verify_password(password, hashed) is True

    # Verify incorrect password
    assert verify_password("wrong_password", hashed) is False


def test_jwt_token_creation_and_decoding():
    """Test JWT token creation and decoding"""
    data = {"sub": 123, "email": "test@example.com"}

    # Create token
    token = create_access_token(data)
    assert token is not None
    assert len(token) > 0

    # Decode token
    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == 123
    assert decoded["email"] == "test@example.com"
    assert "exp" in decoded


def test_jwt_invalid_token():
    """Test decoding invalid JWT token"""
    invalid_token = "invalid.jwt.token"

    decoded = decode_access_token(invalid_token)
    assert decoded is None


def test_password_hash_is_different_each_time():
    """Test that password hashing produces different hashes each time"""
    password = "same_password"

    hash1 = get_password_hash(password)
    hash2 = get_password_hash(password)

    # Hashes should be different due to salt
    assert hash1 != hash2

    # But both should verify correctly
    assert verify_password(password, hash1) is True
    assert verify_password(password, hash2) is True
