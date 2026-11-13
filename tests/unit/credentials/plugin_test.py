"""Tests for the shared credential plugin helpers."""

import pathlib

from awx_plugins.credentials.plugin import CertFiles


def test_cert_files_writes_cert_and_key() -> None:
    """The certificate and key should be on disk inside the context."""
    with CertFiles('CERT', 'KEY') as cert_path:
        written_pem = pathlib.Path(str(cert_path)).read_text(encoding='utf-8')

    assert written_pem == 'CERT\nKEY'


def test_cert_files_cleans_up_on_exit() -> None:
    """The temporary file should be closed and deleted on exit."""
    cert_files = CertFiles('CERT')

    with cert_files as cert_path:
        assert cert_path is not None

    assert cert_files.certfile is not None
    assert cert_files.certfile.closed
    assert not pathlib.Path(cert_path).exists()


def test_cert_files_without_cert() -> None:
    """No file should be written without a certificate."""
    with CertFiles(None) as cert_path:
        assert cert_path is None
