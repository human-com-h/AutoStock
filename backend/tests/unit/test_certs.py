from cryptography import x509

from app.core.certs import ensure_certificates


def test_certificates_generate_and_reissue_without_replacing_ca(tmp_path):
    first = ensure_certificates(tmp_path, ("192.168.1.180",))
    ca_bytes = first.ca_cert.read_bytes()
    first_server_bytes = first.server_cert.read_bytes()
    assert first.server_reissued is True
    assert all(
        path.is_file()
        for path in (first.ca_key, first.ca_cert, first.server_key, first.server_cert)
    )

    second = ensure_certificates(tmp_path, ("192.168.1.180",))
    assert second.server_reissued is False
    assert second.ca_cert.read_bytes() == ca_bytes
    assert second.server_cert.read_bytes() == first_server_bytes

    third = ensure_certificates(tmp_path, ("192.168.1.181",))
    assert third.server_reissued is True
    assert third.ca_cert.read_bytes() == ca_bytes
    certificate = x509.load_pem_x509_certificate(third.server_cert.read_bytes())
    sans = certificate.extensions.get_extension_for_class(
        x509.SubjectAlternativeName
    ).value
    assert {"127.0.0.1", "192.168.1.181"} <= {
        str(value) for value in sans.get_values_for_type(x509.IPAddress)
    }
    assert {"localhost", "autostock.local"} <= set(
        sans.get_values_for_type(x509.DNSName)
    )
