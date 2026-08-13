"""Tests for Akeyless credential plugins."""
# mypy: disable-error-code="arg-type,explicit-any"

import dataclasses
from collections.abc import Callable

import pytest
from pytest_mock import MockerFixture

from akeyless.rest import ApiException  # pylint: disable=import-error

from awx_plugins.credentials import akeyless as akeyless_mod


_SECRET_PATH = '/test/secret'
_ACCESS_ID = 'p-test123'
_ACCESS_KEY = 'test-key'
_GATEWAY_URL = 'https://api.akeyless.io'
_WORKLOAD_JWT = 'eyJhbGciOiJSUzI1NiJ9.e30.c2ln'  # noqa: S105

_HTTP_UNAUTHORIZED = 401
_HTTP_FORBIDDEN = 403
_HTTP_NOT_FOUND = 404
_ONE_HOUR_SEC = 3600
_TWO_HOURS_SEC = 7200

_MockApiFactory = Callable[..., object]


@dataclasses.dataclass
class _FakeStaticSecretInfo:
    format: str = 'text'  # noqa: WPS125


@dataclasses.dataclass
class _FakeItemGeneralInfo:
    static_secret_info: _FakeStaticSecretInfo = dataclasses.field(
        default_factory=_FakeStaticSecretInfo,
    )


@dataclasses.dataclass
class _FakeDescribeItemResponse:
    item_type: str = 'STATIC_SECRET'
    item_sub_type: str = 'generic'
    item_general_info: _FakeItemGeneralInfo = dataclasses.field(
        default_factory=_FakeItemGeneralInfo,
    )


@dataclasses.dataclass
class _FakeAuthResponse:
    token: str | None = 'test-token'


@dataclasses.dataclass
class _FakeSshCertResponse:
    data: str | None = 'ssh-rsa-SIGNED-CERT'  # noqa: WPS110


def _make_mock_api(  # noqa: WPS211  # pylint: disable=too-many-arguments
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
    mock_api = mocker.Mock()
    mock_api.auth.return_value = _FakeAuthResponse(token=token)
    mock_api.describe_item.return_value = _FakeDescribeItemResponse(
        item_type=item_type,
        item_sub_type=item_sub_type,
        item_general_info=_FakeItemGeneralInfo(
            static_secret_info=_FakeStaticSecretInfo(format=secret_format),
        ),
    )
    mock_api.get_secret_value.return_value = {secret_path: secret_data}
    mock_api.get_ssh_certificate.return_value = _FakeSshCertResponse(
        data=ssh_cert_data,
    )
    return mock_api


@pytest.fixture
def patch_setup_client(
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
) -> _MockApiFactory:
    """Patch _setup_client, returning a factory that yields the configured mock."""

    def _factory(**kwargs: object) -> object:
        mock = _make_mock_api(mocker, **kwargs)
        monkeypatch.setattr(akeyless_mod, '_setup_client', lambda *_: mock)
        return mock

    return _factory


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


def _oidc_backend_kwargs() -> dict[str, object]:
    """Build kwargs as the controller sends them for the OIDC secret type."""
    return {
        'url': _GATEWAY_URL,
        'access_id': _ACCESS_ID,
        'workload_identity_token': _WORKLOAD_JWT,
        'secret_path': _SECRET_PATH,
    }


def _oidc_ssh_kwargs() -> dict[str, object]:
    """Build kwargs as the controller sends them for the OIDC SSH type."""
    return {
        'url': _GATEWAY_URL,
        'access_id': _ACCESS_ID,
        'workload_identity_token': _WORKLOAD_JWT,
        'cert_issue_name': '/ssh/issuers/my-issuer',
        'cert_username': 'ubuntu',
        'public_key_data': 'ssh-rsa AAAAB3NzaC1yc2E...',
    }


# ---------------------------------------------------------------------------
# akeyless_backend - secret store plugin
# ---------------------------------------------------------------------------


def test_akeyless_backend_text_generic_secret(
    patch_setup_client: _MockApiFactory,
) -> None:
    """Retrieve a plain-text generic secret successfully."""
    patch_setup_client(item_sub_type='generic', secret_format='text')

    fetched_secret = akeyless_mod.akeyless_backend(
        **_backend_kwargs(),
    )

    assert fetched_secret == 'my-secret-value'


def test_akeyless_backend_json_secret_with_key(
    patch_setup_client: _MockApiFactory,
) -> None:
    """Retrieve a specific key from a JSON-format structured secret."""
    patch_setup_client(
        secret_format='json',
        secret_data='{"db_password": "s3cr3t", "db_user": "admin"}',
    )

    fetched_secret = akeyless_mod.akeyless_backend(
        **_backend_kwargs(secret_key='db_password'),
    )

    assert fetched_secret == 's3cr3t'


def test_backend_password_secret_username_key(
    patch_setup_client: _MockApiFactory,
) -> None:
    """Retrieve the 'username' field from a text/password sub-type secret."""
    payload = '{"username": "myuser", "password": "mypass"}'
    patch_setup_client(
        item_sub_type='password',
        secret_format='text',
        secret_data=payload,
    )

    fetched_secret = akeyless_mod.akeyless_backend(
        **_backend_kwargs(secret_key='username'),
    )

    assert fetched_secret == 'myuser'


def test_backend_pwd_secret_invalid_json_raises(
    patch_setup_client: _MockApiFactory,
) -> None:
    """Invalid json returned for password-type secret."""
    payload = '"username": "invalid", "password": "json"}'
    patch_setup_client(
        item_sub_type='password',
        secret_format='text',
        secret_data=payload,
    )

    with pytest.raises(RuntimeError, match='Secret data not valid JSON'):
        akeyless_mod.akeyless_backend(**_backend_kwargs(secret_key='username'))


def test_backend_unsupported_type_raises(
    patch_setup_client: _MockApiFactory,
) -> None:
    """Unsupported secret types (e.g. dynamic) should raise NotImplementedError."""
    patch_setup_client(item_type='DYNAMIC_SECRET')

    with pytest.raises(NotImplementedError, match='DYNAMIC_SECRET'):
        akeyless_mod.akeyless_backend(**_backend_kwargs())


def test_backend_api_exc_wraps_runtime(
    patch_setup_client: _MockApiFactory,
) -> None:
    """An ApiException from get_secret_value surfaces as RuntimeError."""
    mock_api = patch_setup_client()
    mock_api.get_secret_value.side_effect = ApiException(
        status=_HTTP_FORBIDDEN,
        reason='Forbidden',
    )

    with pytest.raises(
        RuntimeError,
        match=r'Akeyless API error: Forbidden \(Status: 403\)',
    ):
        akeyless_mod.akeyless_backend(**_backend_kwargs())


def test_backend_auth_failure_raises(
    patch_setup_client: _MockApiFactory,
) -> None:
    """A missing auth token should surface as RuntimeError to the plugin caller."""
    patch_setup_client(token=None)

    with pytest.raises(RuntimeError, match='no token received'):
        akeyless_mod.akeyless_backend(**_backend_kwargs())


def test_backend_auth_api_exc_raises(
    patch_setup_client: _MockApiFactory,
) -> None:
    """An ApiException from auth should surface as RuntimeError."""
    mock_api = patch_setup_client()
    mock_api.auth.side_effect = ApiException(
        status=_HTTP_UNAUTHORIZED,
        reason='Unauthorized',
    )

    with pytest.raises(
        RuntimeError,
        match=r'Akeyless API error: Unauthorized \(Status: 401\)',
    ):
        akeyless_mod.akeyless_backend(**_backend_kwargs())


def test_backend_missing_json_key_raises(
    patch_setup_client: _MockApiFactory,
) -> None:
    """A missing key in a structured secret should name the secret path."""
    patch_setup_client(
        secret_format='json',
        secret_data='{"other_key": "value"}',
    )

    with pytest.raises(RuntimeError, match=_SECRET_PATH):
        akeyless_mod.akeyless_backend(
            **_backend_kwargs(secret_key='missing_key'),
        )


# ---------------------------------------------------------------------------
# akeyless_ssh_backend - SSH certificate plugin
# ---------------------------------------------------------------------------


def test_akeyless_ssh_backend_success(
    patch_setup_client: _MockApiFactory,
) -> None:
    """Successfully generate a signed SSH certificate."""
    patch_setup_client(ssh_cert_data='ssh-rsa-cert-AAAAAA')

    signed_cert = akeyless_mod.akeyless_ssh_backend(**_ssh_kwargs())

    assert signed_cert == 'ssh-rsa-cert-AAAAAA'


def test_akeyless_ssh_backend_with_ttl(
    patch_setup_client: _MockApiFactory,
) -> None:
    """SSH certificate request with an explicit TTL should succeed."""
    mock_api = patch_setup_client(ssh_cert_data='signed-cert')

    signed_cert = akeyless_mod.akeyless_ssh_backend(
        **_ssh_kwargs(ttl=_ONE_HOUR_SEC),
    )

    assert signed_cert == 'signed-cert'
    ssh_request = mock_api.get_ssh_certificate.call_args.args[0]
    assert ssh_request.ttl == _ONE_HOUR_SEC


def test_ssh_backend_no_cert_data_raises(
    patch_setup_client: _MockApiFactory,
) -> None:
    """An empty/None cert response should surface as RuntimeError."""
    patch_setup_client(ssh_cert_data=None)

    with pytest.raises(RuntimeError, match='no data returned'):
        akeyless_mod.akeyless_ssh_backend(**_ssh_kwargs())


def test_ssh_api_exc_wraps_runtime(
    patch_setup_client: _MockApiFactory,
) -> None:
    """An ApiException from get_ssh_certificate surfaces as RuntimeError."""
    mock_api = patch_setup_client()
    mock_api.get_ssh_certificate.side_effect = ApiException(
        status=_HTTP_NOT_FOUND,
        reason='Issuer not found',
    )

    with pytest.raises(
        RuntimeError,
        match=r'Akeyless API error: Issuer not found \(Status: 404\)',
    ):
        akeyless_mod.akeyless_ssh_backend(**_ssh_kwargs())


# ---------------------------------------------------------------------------
# _coerce_ttl helper
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ('ttl_input', 'expected'),
    (
        pytest.param(None, None, id='none'),
        pytest.param('', None, id='empty-string'),
        pytest.param(_ONE_HOUR_SEC, _ONE_HOUR_SEC, id='int'),
        pytest.param('7200', _TWO_HOURS_SEC, id='string-int'),
    ),
)
def test_coerce_ttl_valid_inputs(
    ttl_input: int | str | None,
    expected: int | None,
) -> None:
    """_coerce_ttl should convert numeric-like values and pass None/'' through."""
    # WPS437: _coerce_ttl is private but is tested directly here intentionally
    # pylint: disable-next=protected-access
    assert akeyless_mod._coerce_ttl(ttl_input) == expected  # noqa: WPS437


def test_coerce_ttl_invalid_raises() -> None:
    """_coerce_ttl should raise ValueError for non-numeric strings."""
    with pytest.raises(ValueError, match='integer number of seconds'):
        # WPS437: _coerce_ttl is private but is tested directly here intentionally
        # pylint: disable-next=protected-access
        akeyless_mod._coerce_ttl('not-a-number')  # noqa: WPS437


# ---------------------------------------------------------------------------
# OIDC / workload identity authentication
# ---------------------------------------------------------------------------


def test_oidc_backend_authenticates_with_jwt(
    patch_setup_client: _MockApiFactory,
) -> None:
    """A workload identity token should be exchanged via JWT auth."""
    mock_api = patch_setup_client(secret_data='oidc-secret')

    secret_value = akeyless_mod.akeyless_backend(**_oidc_backend_kwargs())

    assert secret_value == 'oidc-secret'
    auth_request = mock_api.auth.call_args.args[0]
    assert auth_request.access_type == 'jwt'
    assert auth_request.jwt == _WORKLOAD_JWT
    assert auth_request.access_id == _ACCESS_ID
    assert auth_request.access_key is None


def test_oidc_ssh_backend_authenticates_with_jwt(
    patch_setup_client: _MockApiFactory,
) -> None:
    """SSH certificate issuance should also support workload identity."""
    mock_api = patch_setup_client(ssh_cert_data='oidc-signed-cert')

    signed_cert = akeyless_mod.akeyless_ssh_backend(**_oidc_ssh_kwargs())

    assert signed_cert == 'oidc-signed-cert'
    auth_request = mock_api.auth.call_args.args[0]
    assert auth_request.access_type == 'jwt'
    assert auth_request.jwt == _WORKLOAD_JWT


def test_workload_identity_token_takes_precedence(
    patch_setup_client: _MockApiFactory,
) -> None:
    """A workload identity token should win over a stale access key."""
    mock_api = patch_setup_client()

    akeyless_mod.akeyless_backend(
        **_oidc_backend_kwargs(),
        access_key=_ACCESS_KEY,
    )

    auth_request = mock_api.auth.call_args.args[0]
    assert auth_request.access_type == 'jwt'


def test_missing_auth_material_raises(
    patch_setup_client: _MockApiFactory,
) -> None:
    """Neither an access key nor a token should be a clear failure."""
    patch_setup_client()
    kwargs = _oidc_backend_kwargs()
    del kwargs['workload_identity_token']  # noqa: WPS420

    with pytest.raises(
        RuntimeError,
        match='Access Key or a workload identity',
    ):
        akeyless_mod.akeyless_backend(**kwargs)


def test_missing_gateway_url_raises(
    patch_setup_client: _MockApiFactory,
) -> None:
    """Neither `url` nor `gateway_url` should be a clear failure."""
    patch_setup_client()
    kwargs = _oidc_backend_kwargs()
    del kwargs['url']  # noqa: WPS420

    with pytest.raises(RuntimeError, match='Gateway URL must be set'):
        akeyless_mod.akeyless_backend(**kwargs)


@pytest.mark.parametrize(
    'plugin',
    (
        pytest.param(akeyless_mod.akeyless_oidc_plugin, id='secret'),
        pytest.param(akeyless_mod.akeyless_ssh_oidc_plugin, id='ssh'),
    ),
)
def test_oidc_plugins_workload_contract(
    plugin: object,
) -> None:
    """The OIDC types must match what the controller looks for.

    It only injects a token into credential types exposing an internal
    ``workload_identity_token`` field, and it reads the audience of that
    token from the input named ``url``.
    """
    fields = plugin.inputs['fields']
    token_fields = [
        field for field in fields if field['id'] == 'workload_identity_token'
    ]

    assert [field['id'] for field in fields].count('url') == 1
    assert len(token_fields) == 1
    assert token_fields[0]['internal'] is True
    assert token_fields[0]['secret'] is True
    assert 'access_key' not in {field['id'] for field in fields}
