from __future__ import annotations

import ipaddress
import os
import socket
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from app.core.config import settings


@dataclass(frozen=True)
class CertificateBundle:
    ca_key: Path
    ca_cert: Path
    server_key: Path
    server_cert: Path
    ip_addresses: tuple[str, ...]
    server_reissued: bool


def discover_private_ipv4_addresses() -> tuple[str, ...]:
    addresses: set[str] = set()
    try:
        for result in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addresses.add(result[4][0])
    except socket.gaierror:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 80))
            addresses.add(probe.getsockname()[0])
    except OSError:
        pass
    private = {
        address
        for address in addresses
        if ipaddress.ip_address(address).is_private
        and not ipaddress.ip_address(address).is_loopback
    }
    return tuple(sorted(private))


def _write_private_key(path: Path, key: rsa.RSAPrivateKey) -> None:
    path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _write_certificate(path: Path, certificate: x509.Certificate) -> None:
    path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))


def _create_ca(key_path: Path, cert_path: Path) -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AutoStock"),
            x509.NameAttribute(NameOID.COMMON_NAME, "AutoStock Local CA"),
        ]
    )
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_cert_sign=True,
                crl_sign=True,
                key_encipherment=False,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=None,
                decipher_only=None,
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    _write_private_key(key_path, key)
    _write_certificate(cert_path, certificate)
    return key, certificate


def _load_or_create_ca(
    key_path: Path, cert_path: Path
) -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    if key_path.is_file() and cert_path.is_file():
        try:
            key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
            certificate = x509.load_pem_x509_certificate(cert_path.read_bytes())
            if isinstance(key, rsa.RSAPrivateKey):
                return key, certificate
        except (ValueError, TypeError):
            pass
    return _create_ca(key_path, cert_path)


def _server_certificate_is_current(
    cert_path: Path,
    key_path: Path,
    ca_certificate: x509.Certificate,
    required_ips: set[str],
) -> bool:
    if not cert_path.is_file() or not key_path.is_file():
        return False
    try:
        certificate = x509.load_pem_x509_certificate(cert_path.read_bytes())
        sans = certificate.extensions.get_extension_for_class(
            x509.SubjectAlternativeName
        ).value
        certificate_ips = {str(value) for value in sans.get_values_for_type(x509.IPAddress)}
        certificate_dns = set(sans.get_values_for_type(x509.DNSName))
    except (ValueError, x509.ExtensionNotFound):
        return False
    expires_at = certificate.not_valid_after_utc
    return (
        certificate.issuer == ca_certificate.subject
        and required_ips.issubset(certificate_ips)
        and {"localhost", "autostock.local"}.issubset(certificate_dns)
        and expires_at > datetime.now(UTC) + timedelta(days=30)
    )


def _create_server_certificate(
    key_path: Path,
    cert_path: Path,
    ca_key: rsa.RSAPrivateKey,
    ca_certificate: x509.Certificate,
    ip_addresses: set[str],
) -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(UTC)
    san_values: list[x509.GeneralName] = [
        x509.DNSName("localhost"),
        x509.DNSName("autostock.local"),
    ]
    san_values.extend(
        x509.IPAddress(ipaddress.ip_address(address)) for address in sorted(ip_addresses)
    )
    certificate = (
        x509.CertificateBuilder()
        .subject_name(
            x509.Name(
                [
                    x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AutoStock"),
                    x509.NameAttribute(NameOID.COMMON_NAME, "AutoStock Local Server"),
                ]
            )
        )
        .issuer_name(ca_certificate.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1095))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectAlternativeName(san_values), critical=False)
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False
        )
        .sign(ca_key, hashes.SHA256())
    )
    _write_private_key(key_path, key)
    _write_certificate(cert_path, certificate)


def ensure_certificates(
    data_dir: Path | None = None,
    ip_addresses: tuple[str, ...] | None = None,
) -> CertificateBundle:
    root = (data_dir or settings.data_dir) / "certs"
    root.mkdir(parents=True, exist_ok=True)
    ca_key_path = root / "ca.key"
    ca_cert_path = root / "ca.crt"
    server_key_path = root / "server.key"
    server_cert_path = root / "server.crt"

    ca_key, ca_certificate = _load_or_create_ca(ca_key_path, ca_cert_path)
    detected = ip_addresses if ip_addresses is not None else discover_private_ipv4_addresses()
    required_ips = {"127.0.0.1", *detected}
    reissued = not _server_certificate_is_current(
        server_cert_path,
        server_key_path,
        ca_certificate,
        required_ips,
    )
    if reissued:
        _create_server_certificate(
            server_key_path,
            server_cert_path,
            ca_key,
            ca_certificate,
            required_ips,
        )
    return CertificateBundle(
        ca_key=ca_key_path,
        ca_cert=ca_cert_path,
        server_key=server_key_path,
        server_cert=server_cert_path,
        ip_addresses=tuple(sorted(required_ips)),
        server_reissued=reissued,
    )
