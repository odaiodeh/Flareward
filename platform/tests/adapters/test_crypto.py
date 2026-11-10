"""The cipher adapter preserves the installed legacy format and translates SDK failures."""

import pytest
from cryptography.fernet import Fernet
from global_utils.utils.crypto import FieldCipher as LegacyCipher

from lumora.services.auth.adapters.crypto import FieldCipher
from lumora.services.auth.credentials.ports import CipherError


def test_field_cipher_is_compatible_with_existing_encrypted_values():
    key = Fernet.generate_key().decode()
    native, legacy = FieldCipher(key), LegacyCipher(key)
    assert native.decrypt(legacy.encrypt("private")) == "private"
    assert legacy.decrypt(native.encrypt("private")) == "private"
    assert native.decrypt("ordinary-plaintext") == "ordinary-plaintext"
    assert native.encrypt("") == "" and native.decrypt(None) is None


def test_wrong_key_produces_an_application_error_without_sdk_or_value_details():
    encrypted = FieldCipher(Fernet.generate_key().decode()).encrypt("private")
    with pytest.raises(CipherError) as raised:
        FieldCipher(Fernet.generate_key().decode()).decrypt(encrypted)
    assert "private" not in str(raised.value) and encrypted not in str(raised.value)
