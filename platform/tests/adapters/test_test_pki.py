"""Test infrastructure PKI satisfies a real certificate verifier and preserves existing keys."""

from datetime import UTC, datetime

import pytest
from cryptography import x509
from cryptography.x509.verification import PolicyBuilder, Store
from infra.prepare import prepare


def test_generated_gateway_certificate_verifies_and_repeated_setup_keeps_its_identity(tmp_path):
    prepare(tmp_path)
    files = {path.name: path.read_bytes() for path in (tmp_path / "pki").iterdir()}
    ca = x509.load_pem_x509_certificate(files["ca.crt"])
    server = x509.load_pem_x509_certificate(files["server.crt"])
    verifier = (
        PolicyBuilder()
        .store(Store([ca]))
        .time(datetime.now(UTC))
        .build_server_verifier(x509.DNSName("localhost"))
    )
    assert verifier.verify(server, []) == [server, ca]
    prepare(tmp_path)
    assert files == {path.name: path.read_bytes() for path in (tmp_path / "pki").iterdir()}
    assert all(path.stat().st_mode & 0o077 == 0 for path in (tmp_path / "pki").iterdir())


def test_partial_test_pki_is_refused_without_replacing_existing_files(tmp_path):
    pki = tmp_path / "pki"
    pki.mkdir()
    existing = pki / "ca.crt"
    existing.write_bytes(b"existing certificate")
    with pytest.raises(ValueError, match="Incomplete"):
        prepare(tmp_path)
    assert existing.read_bytes() == b"existing certificate"
