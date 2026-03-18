"""Tests for Akeyless credential plugins."""

import pytest
from pytest_mock import MockerFixture

from akeyless.rest import ApiException  # pylint: disable=import-error

from awx_plugins.credentials import akeyless as akeyless_mod


_SECRET_PATH = '/test/secret'
_ACCESS_ID = 'p-test123'
_ACCESS_KEY = 'test-key'
_GATEWAY_URL = 'https://api.akeyless.io'


def _make_mock_api(
    mocker: MockerFixture,
    *,
    token: str | None = 'test-token',
    item_type: str = 'STATIC_SECRET',
    item_sub_type: str = 'generic',
    secret_format: str = 'text',
    secret_path: str = _SECRET_PATH,
    secret_data: str = 'my-secret-value',
    ssh_cert_data: str | None = 'ssh-rsa-SIGNED-CERT',
) -> object:
    """Create a mock Akeyless API instance with configurable responses."""
    mock_static_info = mocker.MagicMock()
    mock_static_info.format = secret_format

    mock_general_info = mocker.MagicMock()
    mock_general_info.static_secret_info = mock_static_info

    mock_describe = mocker.MagicMock()
    mock_describe.item_type = item_type
    mock_describe.item_sub_type = item_sub_type
    mock_describe.item_general_info = mock_general_info

    mock_api = mocker.MagicMock()
    mock_api.auth.return_value.token = token
    mock_api.describe_item.return_value = mock_describe
    mock_api.get_secret_value.return_value = {secret_path: secret_data}
    mock_api.get_ssh_certificate.return_value.data = ssh_cert_data
    return mock_api


def _backend_kwargs(
    *,
    secret_path: str = _SECRET_PATH,
    secret_key: str | None = None,
    ca_cert: str | None = None,
) -> dict[str, object]:
    """Build a minimal set of kwargs for akeyless_backend."""
    kwargs: dict[str, object] = {
        'gateway_url': _GATEWAY_URL,
        'access_id': _ACCESS_ID,
        'access_key': _ACCESS_KEY,
        'secret_path': secret_path,
    }
    if secret_key is not None:
        kwargs['secret_key'] = secret_key
    if ca_cert is not None:
        kwargs['ca_cert'] = ca_cert
    return kwargs


def _ssh_kwargs(
    *,
    ttl: int | str | None = None,
    ca_cert: str | None = None,
) -> dict[str, object]:
    """Build a minimal set of kwargs for akeyless_ssh_backend."""
    kwargs: dict[str, object] = {
        'gateway_url': _GATEWAY_URL,
        'access_id': _ACCESS_ID,
        'access_key': _ACCESS_KEY,
        'cert_issue_name': '/ssh/issuers/my-issuer',
        'cert_username': 'ubuntu',
        'public_key_data': 'ssh-rsa AAAAB3NzaC1yc2E...',
    }
    if ttl is not None:
        kwargs['ttl'] = ttl
    if ca_cert is not None:
        kwargs['ca_cert'] = ca_cert
    return kwargs


# ---------------------------------------------------------------------------
# akeyless_backend – secret store plugin
# ---------------------------------------------------------------------------


def test_akeyless_backend_text_generic_secret(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retrieve a plain-text generic secret successfully."""
    mock_api = _make_mock_api(mocker, item_sub_type='generic', secret_format='text')
    monkeypatch.setattr(akeyless_mod, '_setup_client', lambda *_: mock_api)

    result = akeyless_mod.akeyless_backend(**_backend_kwargs())  # type: ignore[arg-type]

    assert result == 'my-secret-value'


def test_akeyless_backend_json_secret_with_key(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retrieve a specific key from a JSON-format structured secret."""
    mock_api = _make_mock_api(
        mocker,
        secret_format='json',
        secret_data='{"db_password": "s3cr3t", "db_user": "admin"}',
    )
    monkeypatch.setattr(akeyless_mod, '_setup_client', lambda *_: mock_api)

    result = akeyless_mod.akeyless_backend(  # type: ignore[arg-type]
        **_backend_kwargs(secret_key='db_password'),
    )

    assert result == 's3cr3t'


def test_akeyless_backend_password_secret_username_key(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retrieve the 'username' field from a text/password sub-type secret."""
    payload = '{"username": "myuser", "password": "mypass"}'
    mock_api = _make_mock_api(
        mocker,
        item_sub_type='password',
        secret_format='text',
        secret_data=payload,
    )
    monkeypatch.setattr(akeyless_mod, '_setup_client', lambda *_: mock_api)

    result = akeyless_mod.akeyless_backend(  # type: ignore[arg-type]
        **_backend_kwargs(secret_key='username'),
    )

    assert result == 'myuser'


def test_akeyless_backend_unsupported_item_type_raises(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unsupported secret types (e.g. dynamic) should raise NotImplementedError."""
    mock_api = _make_mock_api(mocker, item_type='DYNAMIC_SECRET')
    monkeypatch.setattr(akeyless_mod, '_setup_client', lambda *_: mock_api)

    with pytest.raises(NotImplementedError, match='DYNAMIC_SECRET'):
        akeyless_mod.akeyless_backend(**_backend_kwargs())  # type: ignore[arg-type]


def test_akeyless_backend_api_exception_wraps_to_runtime_error(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ApiException from the SDK should be re-raised as RuntimeError."""
    mock_api = _make_mock_api(mocker)
    mock_api.get_secret_value.side_effect = ApiException(
        status=403,
        reason='Forbidden',
    )
    monkeypatch.setattr(akeyless_mod, '_setup_client', lambda *_: mock_api)

    with pytest.raises(RuntimeError, match=r'Akeyless API error: Forbidden \(Status: 403\)'):
        akeyless_mod.akeyless_backend(**_backend_kwargs())  # type: ignore[arg-type]


def test_akeyless_backend_auth_failure_raises_runtime_error(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing auth token should surface as RuntimeError to the plugin caller."""
    mock_api = _make_mock_api(mocker, token=None)
    monkeypatch.setattr(akeyless_mod, '_setup_client', lambda *_: mock_api)

    with pytest.raises(RuntimeError, match='no token received'):
        akeyless_mod.akeyless_backend(**_backend_kwargs())  # type: ignore[arg-type]


def test_akeyless_backend_missing_json_key_raises(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing key in a structured secret should raise KeyError with the path."""
    mock_api = _make_mock_api(
        mocker,
        secret_format='json',
        secret_data='{"other_key": "value"}',
    )
    monkeypatch.setattr(akeyless_mod, '_setup_client', lambda *_: mock_api)

    with pytest.raises(KeyError, match=_SECRET_PATH):
        akeyless_mod.akeyless_backend(  # type: ignore[arg-type]
            **_backend_kwargs(secret_key='missing_key'),
        )


# ---------------------------------------------------------------------------
# akeyless_ssh_backend – SSH certificate plugin
# ---------------------------------------------------------------------------


def test_akeyless_ssh_backend_success(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Successfully generate a signed SSH certificate."""
    mock_api = _make_mock_api(mocker, ssh_cert_data='ssh-rsa-cert-AAAAAA')
    monkeypatch.setattr(akeyless_mod, '_setup_client', lambda *_: mock_api)

    result = akeyless_mod.akeyless_ssh_backend(**_ssh_kwargs())  # type: ignore[arg-type]

    assert result == 'ssh-rsa-cert-AAAAAA'


def test_akeyless_ssh_backend_with_ttl(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SSH certificate request with an explicit TTL should succeed."""
    mock_api = _make_mock_api(mocker, ssh_cert_data='signed-cert')
    monkeypatch.setattr(akeyless_mod, '_setup_client', lambda *_: mock_api)

    result = akeyless_mod.akeyless_ssh_backend(  # type: ignore[arg-type]
        **_ssh_kwargs(ttl=3600),
    )

    assert result == 'signed-cert'
    _, call_kwargs = mock_api.get_ssh_certificate.call_args
    assert call_kwargs['body'].ttl == 3600


def test_akeyless_ssh_backend_no_cert_data_raises(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty/None cert response should surface as RuntimeError."""
    mock_api = _make_mock_api(mocker, ssh_cert_data=None)
    monkeypatch.setattr(akeyless_mod, '_setup_client', lambda *_: mock_api)

    with pytest.raises(RuntimeError, match='no data returned'):
        akeyless_mod.akeyless_ssh_backend(**_ssh_kwargs())  # type: ignore[arg-type]


def test_akeyless_ssh_backend_api_exception_wraps_to_runtime_error(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ApiException from the SSH cert call should be re-raised as RuntimeError."""
    mock_api = _make_mock_api(mocker)
    mock_api.get_ssh_certificate.side_effect = ApiException(
        status=404,
        reason='Issuer not found',
    )
    monkeypatch.setattr(akeyless_mod, '_setup_client', lambda *_: mock_api)

    with pytest.raises(
        RuntimeError,
        match=r'Akeyless API error: Issuer not found \(Status: 404\)',
    ):
        akeyless_mod.akeyless_ssh_backend(**_ssh_kwargs())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _coerce_ttl helper
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ('ttl_input', 'expected'),
    (
        pytest.param(None, None, id='none'),
        pytest.param('', None, id='empty-string'),
        pytest.param(3600, 3600, id='int'),
        pytest.param('7200', 7200, id='string-int'),
    ),
)
def test_coerce_ttl_valid_inputs(
    ttl_input: int | str | None,
    expected: int | None,
) -> None:
    """_coerce_ttl should convert numeric-like values and pass None/'' through."""
    assert akeyless_mod._coerce_ttl(ttl_input) == expected  # noqa: WPS437


def test_coerce_ttl_invalid_raises() -> None:
    """_coerce_ttl should raise ValueError for non-numeric strings."""
    with pytest.raises(ValueError, match='integer number of seconds'):
        akeyless_mod._coerce_ttl('not-a-number')  # noqa: WPS437
