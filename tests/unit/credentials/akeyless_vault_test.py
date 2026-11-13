"""Tests for the Akeyless credential plugins."""

import dataclasses
import pathlib
import types

import pytest
from pytest_mock import MockerFixture, MockType

from akeyless import ApiClient
from akeyless.rest import ApiException

from awx_plugins.credentials.akeyless_vault import _session, secret, ssh
from awx_plugins.credentials.plugin import CredentialPlugin


_SECRET_PATH = '/test/secret'
_ACCESS_ID = 'p-test123'
_ACCESS_KEY = 'test-key'
_AUTH_TOKEN = 'test-token'
_GATEWAY_URL = 'https://api.akeyless.io'
_WORKLOAD_JWT = 'eyJhbGciOiJSUzI1NiJ9.e30.c2ln'
_SECRET_VALUE = 'my-secret-value'
_SIGNED_CERT = 'ssh-rsa-SIGNED-CERT'
_CA_CERT_PEM = (
    '-----BEGIN CERTIFICATE-----\n'
    'ZmFrZS1jZXJ0aWZpY2F0ZQ==\n'
    '-----END CERTIFICATE-----\n'
)
_CREDENTIALS_JSON = '{"username": "myuser", "password": "mypass"}'

_HTTP_UNAUTHORIZED = 401
_HTTP_FORBIDDEN = 403
_HTTP_NOT_FOUND = 404
_ONE_HOUR_SEC = 3600
_TWO_HOURS_SEC = 7200

_API_KEY_INPUTS = types.MappingProxyType(
    {
        'gateway_url': _GATEWAY_URL,
        'access_id': _ACCESS_ID,
        'access_key': _ACCESS_KEY,
    },
)

# The inputs of the OIDC credential types, as the controller sends them:
_OIDC_INPUTS = types.MappingProxyType(
    {
        'url': _GATEWAY_URL,
        'access_id': _ACCESS_ID,
        'workload_identity_token': _WORKLOAD_JWT,
    },
)

_SSH_INPUTS = types.MappingProxyType(
    {
        'cert_issue_name': '/ssh/issuers/my-issuer',
        'cert_username': 'ubuntu',
        'public_key_data': 'ssh-rsa AAAAB3NzaC1yc2E...',
    },
)


@dataclasses.dataclass
class _FakeStaticSecretInfo:
    format: str = 'text'  # noqa: WPS125 -- the Akeyless SDK attribute name


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
    token: str | None = _AUTH_TOKEN


@dataclasses.dataclass
class _FakeSshCertResponse:
    data: str | None = _SIGNED_CERT  # noqa: WPS110 -- the SDK attribute name


@pytest.fixture
def api_class(mocker: MockerFixture) -> MockType:
    """Keep the plugins from contacting an Akeyless Gateway."""
    return mocker.patch.object(_session, 'V2Api')


@pytest.fixture
def mock_api(api_class: MockType) -> MockType:
    """Serve canned Akeyless API responses."""
    api: MockType = api_class.return_value
    api.auth.return_value = _FakeAuthResponse()
    api.describe_item.return_value = _FakeDescribeItemResponse()
    api.get_secret_value.return_value = {_SECRET_PATH: _SECRET_VALUE}
    api.get_ssh_certificate.return_value = _FakeSshCertResponse()
    return api


def _serve_secret(
    api: MockType,
    secret_data: str,
    *,
    sub_type: str = 'generic',
    value_format: str = 'text',
) -> None:
    api.describe_item.return_value = _FakeDescribeItemResponse(
        item_sub_type=sub_type,
        item_general_info=_FakeItemGeneralInfo(
            static_secret_info=_FakeStaticSecretInfo(format=value_format),
        ),
    )
    api.get_secret_value.return_value = {_SECRET_PATH: secret_data}


def _api_client_of(api_class_mock: MockType) -> ApiClient:
    """Get the API client that the plugin set up."""
    api_client: ApiClient = api_class_mock.call_args.args[0]
    return api_client


def _look_up_secret(secret_key: str | None = None) -> str:
    """Look up the test secret with the API key credential type."""
    return secret.akeyless_backend(
        **_API_KEY_INPUTS,
        secret_path=_SECRET_PATH,
        secret_key=secret_key,
    )


# ---------------------------------------------------------------------------
# akeyless_backend - secret store plugin
# ---------------------------------------------------------------------------


def test_backend_text_generic_secret(mock_api: MockType) -> None:
    """Retrieve a plain-text generic secret successfully."""
    fetched_secret = _look_up_secret()

    assert fetched_secret == _SECRET_VALUE
    describe_request = mock_api.describe_item.call_args.args[0]
    assert describe_request.name == _SECRET_PATH
    assert describe_request.token == _AUTH_TOKEN


@pytest.mark.parametrize(
    'value_format',
    (
        pytest.param('json', id='json'),
        pytest.param('key-value', id='key-value'),
    ),
)
def test_backend_structured_secret_with_key(
    value_format: str,
    mock_api: MockType,
) -> None:
    """Retrieve a specific key from a structured secret."""
    _serve_secret(
        mock_api,
        '{"db_password": "s3cr3t", "db_user": "admin"}',
        value_format=value_format,
    )

    fetched_secret = _look_up_secret(secret_key='db_password')

    assert fetched_secret == 's3cr3t'


@pytest.mark.parametrize(
    ('sub_type', 'value_format'),
    (
        pytest.param('password', 'text', id='password'),
        pytest.param('generic', 'json', id='json'),
        pytest.param('generic', 'key-value', id='key-value'),
    ),
)
def test_backend_secret_without_key(
    sub_type: str,
    value_format: str,
    mock_api: MockType,
) -> None:
    """Without a secret key, the whole payload is returned verbatim."""
    _serve_secret(
        mock_api,
        _CREDENTIALS_JSON,
        sub_type=sub_type,
        value_format=value_format,
    )

    fetched_secret = _look_up_secret()

    assert fetched_secret == _CREDENTIALS_JSON


@pytest.mark.parametrize(
    ('secret_key', 'expected'),
    (
        pytest.param('username', 'myuser', id='username'),
        pytest.param('password', 'mypass', id='password'),
    ),
)
def test_backend_password_secret_keys(
    secret_key: str,
    expected: str,
    mock_api: MockType,
) -> None:
    """Retrieve either field of a text/password sub-type secret."""
    _serve_secret(mock_api, _CREDENTIALS_JSON, sub_type='password')

    fetched_secret = _look_up_secret(secret_key=secret_key)

    assert fetched_secret == expected


def test_backend_pwd_secret_missing_key_raises(mock_api: MockType) -> None:
    """A password payload lacking the requested field is a clear failure."""
    _serve_secret(mock_api, '{"username": "myuser"}', sub_type='password')

    with pytest.raises(RuntimeError, match='not found in the password secret'):
        _look_up_secret(secret_key='password')


def test_backend_pwd_secret_bad_key_raises(mock_api: MockType) -> None:
    """Password secrets expose only their username and password fields."""
    _serve_secret(
        mock_api,
        '{"username": "myuser", "token": "nope"}',
        sub_type='password',
    )

    with pytest.raises(NotImplementedError, match='"username" or "password"'):
        _look_up_secret(secret_key='token')


def test_backend_unsupported_sub_type_raises(mock_api: MockType) -> None:
    """Text secrets must be of the password or generic sub type."""
    _serve_secret(mock_api, _SECRET_VALUE, sub_type='certificate')

    with pytest.raises(NotImplementedError, match='"password" or "generic"'):
        _look_up_secret()


def test_backend_unsupported_format_raises(mock_api: MockType) -> None:
    """Static secrets must be in the text, JSON or key-value format."""
    _serve_secret(mock_api, _SECRET_VALUE, value_format='yaml')

    with pytest.raises(NotImplementedError, match='"json", or "key-value"'):
        _look_up_secret()


@pytest.mark.parametrize(
    ('sub_type', 'value_format'),
    (
        pytest.param('password', 'text', id='password'),
        pytest.param('generic', 'json', id='json'),
    ),
)
def test_backend_invalid_json_raises(
    sub_type: str,
    value_format: str,
    mock_api: MockType,
) -> None:
    """A keyed lookup in malformed JSON data is a clear failure."""
    _serve_secret(
        mock_api,
        '"username": "invalid", "password": "json"}',
        sub_type=sub_type,
        value_format=value_format,
    )

    with pytest.raises(RuntimeError, match='Secret data not valid JSON'):
        _look_up_secret(secret_key='username')


@pytest.mark.parametrize(
    'secret_data',
    (
        pytest.param('null', id='null'),
        pytest.param('["s3cr3t"]', id='array'),
        pytest.param('42', id='number'),
        pytest.param('"s3cr3t"', id='string'),
    ),
)
def test_backend_non_object_json_raises(
    secret_data: str,
    mock_api: MockType,
) -> None:
    """Keyed lookups need a JSON object, not an array or a scalar."""
    _serve_secret(mock_api, secret_data, value_format='json')

    with pytest.raises(RuntimeError, match='Secret data not a JSON object'):
        _look_up_secret(secret_key='db_password')


def test_backend_missing_json_key_raises(mock_api: MockType) -> None:
    """A missing key in a structured secret should name the secret path."""
    _serve_secret(mock_api, '{"other_key": "value"}', value_format='json')

    with pytest.raises(RuntimeError, match=_SECRET_PATH):
        _look_up_secret(secret_key='missing_key')


def test_backend_unsupported_type_raises(mock_api: MockType) -> None:
    """Unsupported secret types (e.g. dynamic) should raise NotImplementedError."""
    mock_api.describe_item.return_value = _FakeDescribeItemResponse(
        item_type='DYNAMIC_SECRET',
    )

    with pytest.raises(NotImplementedError, match='DYNAMIC_SECRET'):
        _look_up_secret()


def test_backend_path_missing_in_response(mock_api: MockType) -> None:
    """A response that omits the requested path should name that path."""
    mock_api.get_secret_value.return_value = {'/other/secret': _SECRET_VALUE}

    with pytest.raises(RuntimeError, match=f'No secret data.*{_SECRET_PATH}'):
        _look_up_secret()


def test_backend_api_exc_wraps_runtime(mock_api: MockType) -> None:
    """An ApiException from get_secret_value surfaces as RuntimeError."""
    mock_api.get_secret_value.side_effect = ApiException(
        status=_HTTP_FORBIDDEN,
        reason='Forbidden',
    )

    with pytest.raises(
        RuntimeError,
        match=r'Akeyless API error: Forbidden \(Status: 403\)',
    ):
        _look_up_secret()


# ---------------------------------------------------------------------------
# akeyless_ssh_backend - SSH certificate plugin
# ---------------------------------------------------------------------------


def test_ssh_backend_success(mock_api: MockType) -> None:
    """Successfully generate a signed SSH certificate."""
    signed_cert = ssh.akeyless_ssh_backend(**_API_KEY_INPUTS, **_SSH_INPUTS)

    assert signed_cert == _SIGNED_CERT
    ssh_request = mock_api.get_ssh_certificate.call_args.args[0]
    assert ssh_request.token == _AUTH_TOKEN
    assert ssh_request.cert_issuer_name == _SSH_INPUTS['cert_issue_name']
    assert ssh_request.cert_username == _SSH_INPUTS['cert_username']
    assert ssh_request.public_key_data == _SSH_INPUTS['public_key_data']


@pytest.mark.parametrize(
    ('ttl', 'expected'),
    (
        pytest.param(None, None, id='none'),
        pytest.param('', None, id='empty-string'),
        pytest.param(_ONE_HOUR_SEC, _ONE_HOUR_SEC, id='int'),
        pytest.param(str(_TWO_HOURS_SEC), _TWO_HOURS_SEC, id='string-int'),
    ),
)
def test_ssh_backend_ttl(
    ttl: int | str | None,
    expected: int | None,
    mock_api: MockType,
) -> None:
    """Numeric-like TTLs are converted, and empty ones are left unset."""
    ssh.akeyless_ssh_backend(**_API_KEY_INPUTS, **_SSH_INPUTS, ttl=ttl)

    ssh_request = mock_api.get_ssh_certificate.call_args.args[0]
    assert ssh_request.ttl == expected


@pytest.mark.usefixtures('mock_api')
def test_ssh_backend_invalid_ttl_raises() -> None:
    """A non-numeric TTL is a clear failure."""
    with pytest.raises(RuntimeError, match='integer number of seconds'):
        ssh.akeyless_ssh_backend(
            **_API_KEY_INPUTS,
            **_SSH_INPUTS,
            ttl='not-a-number',
        )


def test_ssh_backend_no_cert_data_raises(mock_api: MockType) -> None:
    """An empty/None cert response should surface as RuntimeError."""
    mock_api.get_ssh_certificate.return_value = _FakeSshCertResponse(data=None)

    with pytest.raises(RuntimeError, match='no data returned'):
        ssh.akeyless_ssh_backend(**_API_KEY_INPUTS, **_SSH_INPUTS)


def test_ssh_api_exc_wraps_runtime(mock_api: MockType) -> None:
    """An ApiException from get_ssh_certificate surfaces as RuntimeError."""
    mock_api.get_ssh_certificate.side_effect = ApiException(
        status=_HTTP_NOT_FOUND,
        reason='Issuer not found',
    )

    with pytest.raises(
        RuntimeError,
        match=r'Akeyless API error: Issuer not found \(Status: 404\)',
    ):
        ssh.akeyless_ssh_backend(**_API_KEY_INPUTS, **_SSH_INPUTS)


# ---------------------------------------------------------------------------
# Akeyless client set up
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures('mock_api')
def test_client_configuration(api_class: MockType) -> None:
    """The client identifies itself as AWX to the configured gateway."""
    _look_up_secret()

    api_client = _api_client_of(api_class)
    assert api_client.user_agent == 'AWX'
    assert api_client.default_headers['akeylessclienttype'] == 'AWX'
    assert api_client.configuration.host == _GATEWAY_URL
    assert api_client.configuration.ssl_ca_cert is None


def test_ca_cert_reaches_client(
    api_class: MockType,
    mock_api: MockType,
) -> None:
    """A CA certificate should reach the client as a file on disk."""
    written_certs: list[str] = []

    def _capture_ca_cert(api_client: ApiClient) -> MockType:
        ca_cert_path = pathlib.Path(str(api_client.configuration.ssl_ca_cert))
        written_certs.append(ca_cert_path.read_text(encoding='utf-8'))
        return mock_api

    api_class.side_effect = _capture_ca_cert
    credential_inputs = {**_API_KEY_INPUTS, 'ca_cert': _CA_CERT_PEM}

    secret.akeyless_backend(**credential_inputs, secret_path=_SECRET_PATH)

    assert written_certs == [_CA_CERT_PEM]
    assert _api_client_of(api_class).configuration.verify_ssl is True


@pytest.mark.parametrize(
    ('gateway_inputs', 'expected'),
    (
        pytest.param(
            {'gateway_url': f'{_GATEWAY_URL}/'},
            _GATEWAY_URL,
            id='trailing-slash-stripped',
        ),
        pytest.param(
            {'gateway_url': 'https://my.gw/api/v2///'},
            'https://my.gw/api/v2',
            id='repeated-slashes-stripped',
        ),
        pytest.param(
            {'url': f'{_GATEWAY_URL}/', 'gateway_url': 'https://stale.gw'},
            _GATEWAY_URL,
            id='oidc-url-wins',
        ),
    ),
)
@pytest.mark.usefixtures('mock_api')
def test_gateway_url(
    gateway_inputs: dict[str, str],
    expected: str,
    api_class: MockType,
) -> None:
    """The client prefers `url` and drops trailing slashes."""
    credential_inputs = {**_API_KEY_INPUTS, **gateway_inputs}

    secret.akeyless_backend(**credential_inputs, secret_path=_SECRET_PATH)

    assert _api_client_of(api_class).configuration.host == expected


@pytest.mark.usefixtures('mock_api')
def test_missing_gateway_url_raises() -> None:
    """Neither `url` nor `gateway_url` should be a clear failure."""
    credential_inputs = _OIDC_INPUTS.copy()
    credential_inputs.pop('url')

    with pytest.raises(RuntimeError, match='Gateway URL must be set'):
        secret.akeyless_backend(**credential_inputs, secret_path=_SECRET_PATH)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


def test_backend_authenticates_with_access_key(mock_api: MockType) -> None:
    """The API key credential types authenticate with the access key."""
    _look_up_secret()

    auth_request = mock_api.auth.call_args.args[0]
    assert auth_request.access_id == _ACCESS_ID
    assert auth_request.access_key == _ACCESS_KEY
    assert auth_request.jwt is None


def test_backend_auth_failure_raises(mock_api: MockType) -> None:
    """A missing auth token should surface as RuntimeError."""
    mock_api.auth.return_value = _FakeAuthResponse(token=None)

    with pytest.raises(RuntimeError, match='no token received'):
        _look_up_secret()


def test_backend_auth_api_exc_raises(mock_api: MockType) -> None:
    """An ApiException from auth should surface as RuntimeError."""
    mock_api.auth.side_effect = ApiException(
        status=_HTTP_UNAUTHORIZED,
        reason='Unauthorized',
    )

    with pytest.raises(
        RuntimeError,
        match=r'Akeyless API error: Unauthorized \(Status: 401\)',
    ):
        _look_up_secret()


def test_oidc_backend_authenticates_with_jwt(mock_api: MockType) -> None:
    """A workload identity token should be exchanged via JWT auth."""
    secret.akeyless_backend(**_OIDC_INPUTS, secret_path=_SECRET_PATH)

    auth_request = mock_api.auth.call_args.args[0]
    assert auth_request.access_type == 'jwt'
    assert auth_request.jwt == _WORKLOAD_JWT
    assert auth_request.access_id == _ACCESS_ID
    assert auth_request.access_key is None


def test_oidc_ssh_backend_authenticates_with_jwt(mock_api: MockType) -> None:
    """SSH certificate issuance should also support workload identity."""
    ssh.akeyless_ssh_backend(**_OIDC_INPUTS, **_SSH_INPUTS)

    auth_request = mock_api.auth.call_args.args[0]
    assert auth_request.access_type == 'jwt'
    assert auth_request.jwt == _WORKLOAD_JWT


def test_workload_identity_token_takes_precedence(mock_api: MockType) -> None:
    """A workload identity token should win over a stale access key."""
    credential_inputs = {**_OIDC_INPUTS, 'access_key': _ACCESS_KEY}

    secret.akeyless_backend(**credential_inputs, secret_path=_SECRET_PATH)

    auth_request = mock_api.auth.call_args.args[0]
    assert auth_request.access_type == 'jwt'


@pytest.mark.usefixtures('mock_api')
def test_missing_auth_material_raises() -> None:
    """Neither an access key nor a token should be a clear failure."""
    credential_inputs = _OIDC_INPUTS.copy()
    credential_inputs.pop('workload_identity_token')

    with pytest.raises(
        RuntimeError,
        match='Access Key or a workload identity',
    ):
        secret.akeyless_backend(**credential_inputs, secret_path=_SECRET_PATH)


def test_missing_access_id_raises(mock_api: MockType) -> None:
    """A missing access ID should fail before contacting Akeyless."""
    credential_inputs = _API_KEY_INPUTS.copy()
    credential_inputs.pop('access_id')

    with pytest.raises(RuntimeError, match='Access ID must be set'):
        secret.akeyless_backend(**credential_inputs, secret_path=_SECRET_PATH)

    mock_api.auth.assert_not_called()


@pytest.mark.parametrize(
    'plugin',
    (
        pytest.param(secret.akeyless_oidc_plugin, id='secret'),
        pytest.param(ssh.akeyless_ssh_oidc_plugin, id='ssh'),
    ),
)
def test_oidc_plugins_workload_contract(plugin: CredentialPlugin) -> None:
    """The OIDC types must match what the controller looks for.

    It only injects a token into credential types exposing an internal
    ``workload_identity_token`` field, and it reads the audience of that
    token from the input named ``url``. A second URL input would make the
    audience ambiguous, so ``gateway_url`` must be absent.
    """
    fields = plugin.inputs['fields']
    declared_ids = {field['id'] for field in fields} | set(
        plugin.inputs['required'],
    )
    token_fields = [
        field for field in fields if field['id'] == 'workload_identity_token'
    ]

    assert [field['id'] for field in fields].count('url') == 1
    assert len(token_fields) == 1
    assert token_fields[0]['internal'] is True
    assert token_fields[0]['secret'] is True
    assert not declared_ids & {'access_key', 'gateway_url'}
