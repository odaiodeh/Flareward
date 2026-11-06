"""Generate local test PKI without copying credentials or replacing a running stack's keys."""

import argparse
import ipaddress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def prepare(directory: Path) -> None:
    directory = directory.resolve() / "pki"
    files = (
        "ca.crt",
        "server.crt",
        "server.key",
        "client.crt",
        "client.key",
        "guest.crt",
        "guest.key",
        "signing.pem",
        "public.pem",
        "kid",
    )
    if any((directory / name).exists() for name in files):
        if not all((directory / name).is_file() for name in files):
            raise ValueError("Incomplete test PKI; choose a new state directory")
        certificate = x509.load_pem_x509_certificate((directory / "server.crt").read_bytes())
        if certificate.not_valid_after_utc <= datetime.now(UTC):
            raise ValueError("Expired test PKI; recreate its gateway with a new state directory")
        return
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    directory.chmod(0o700)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "UnifAI local test CA")])
    now = datetime.now(UTC)
    ca = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=7))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=None,
                decipher_only=None,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )
    values = {"ca.crt": ca.public_bytes(serialization.Encoding.PEM)}
    for name, usage in (
        ("server", ExtendedKeyUsageOID.SERVER_AUTH),
        ("client", ExtendedKeyUsageOID.CLIENT_AUTH),
        ("guest", ExtendedKeyUsageOID.CLIENT_AUTH),
    ):
        key = ec.generate_private_key(ec.SECP256R1())
        builder = (
            x509.CertificateBuilder()
            .subject_name(
                x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "unifai-e2e-" + name)])
            )
            .issuer_name(ca_name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(now + timedelta(days=7))
            .add_extension(x509.ExtendedKeyUsage([usage]), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False
            )
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
                critical=False,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=None,
                    decipher_only=None,
                ),
                critical=True,
            )
        )
        if name == "server":
            builder = builder.add_extension(
                x509.SubjectAlternativeName(
                    [
                        x509.DNSName("localhost"),
                        x509.DNSName("host.openshell.internal"),
                        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                    ]
                ),
                critical=False,
            )
        values[name + ".crt"] = builder.sign(ca_key, hashes.SHA256()).public_bytes(
            serialization.Encoding.PEM
        )
        values[name + ".key"] = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    signing = ed25519.Ed25519PrivateKey.generate()
    values["signing.pem"] = signing.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    values["public.pem"] = signing.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    values["kid"] = ("unifai-e2e-" + uuid4().hex).encode()
    for name, value in values.items():
        path = directory / name
        with path.open("xb") as output:
            path.chmod(0o600)
            output.write(value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    directory = parser.parse_args().state_dir.resolve()
    prepare(directory)
    template = Path(__file__).with_name("gateway.toml").read_text()
    (directory / "gateway.toml").write_text(template.replace("{{STATE_DIR}}", str(directory)))


if __name__ == "__main__":
    main()
