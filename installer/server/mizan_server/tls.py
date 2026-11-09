"""HTTPS on the shop's network.

Browsers only allow the offline sale queue (service worker) on HTTPS, so a LAN
install serves HTTPS with its own small certificate authority: tills install
`mizan-ca.crt` once (the app links to it), then trust the server's certificate
for mizan.local, the computer's name and its network addresses.
"""
from __future__ import annotations

import datetime as dt
import ipaddress
import os
import socket
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

CA_NAME = "Mizan local network"


def lan_addresses() -> list[str]:
    """This computer's IPv4 addresses on local networks (best effort, no extra deps)."""
    found: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.add(info[4][0])
    except OSError:
        pass
    try:  # the address used to reach other networks
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            found.add(s.getsockname()[0])
    except OSError:
        pass
    return sorted(a for a in found if not a.startswith("127."))


def _write_key(path: Path, key) -> None:
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    if os.name != "nt":
        os.chmod(path, 0o600)


def ensure_certificates(tls_dir: Path, extra_names: list[str] | None = None) -> dict:
    """Create the CA once; (re)issue the server certificate for the current names."""
    tls_dir.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.UTC)
    ca_key_path, ca_crt_path = tls_dir / "ca.key", tls_dir / "mizan-ca.crt"
    if ca_key_path.exists() and ca_crt_path.exists():
        ca_key = serialization.load_pem_private_key(ca_key_path.read_bytes(), None)
        ca_cert = x509.load_pem_x509_certificate(ca_crt_path.read_bytes())
    else:
        ca_key = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, CA_NAME), x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Mizan")])
        ca_cert = (
            x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=True, crl_sign=True, content_commitment=False,
                                         key_encipherment=False, data_encipherment=False, key_agreement=False,
                                         encipher_only=False, decipher_only=False), critical=True)
            .sign(ca_key, hashes.SHA256())
        )
        _write_key(ca_key_path, ca_key)
        ca_crt_path.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))

    host = socket.gethostname()
    dns = sorted({"mizan.local", "localhost", host, f"{host}.local", *(extra_names or [])} - {""})
    ips = ["127.0.0.1", *lan_addresses()]
    san = [x509.DNSName(d) for d in dns] + [x509.IPAddress(ipaddress.ip_address(i)) for i in ips]
    key = ec.generate_private_key(ec.SECP256R1())
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "mizan.local")]))
        .issuer_name(ca_cert.subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
        # Browsers cap server certificates at about 13 months.
        .not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=397))
        .add_extension(x509.SubjectAlternativeName(san), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    _write_key(tls_dir / "server.key", key)
    (tls_dir / "server.crt").write_bytes(cert.public_bytes(serialization.Encoding.PEM) + ca_crt_path.read_bytes())
    return {"names": dns, "addresses": ips, "valid_until": cert.not_valid_after_utc.isoformat()}


def needs_renewal(tls_dir: Path, days: int = 30) -> bool:
    path = tls_dir / "server.crt"
    if not path.exists():
        return True
    cert = x509.load_pem_x509_certificate(path.read_bytes())
    return cert.not_valid_after_utc - dt.datetime.now(dt.UTC) < dt.timedelta(days=days)
