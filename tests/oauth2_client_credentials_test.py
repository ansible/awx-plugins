"""Tests for the OAuth2 Client Credentials Token credential plugin."""

import http
import secrets
import typing as _t
from urllib.parse import parse_qs

import pytest

import requests
import responses as _responses_mod

from awx_plugins.credentials import (
    oauth2_client_credentials as oauth2_mod,
)


TOKEN_URL = (
    'https://login.microsoftonline.com'
    '/00000000-0000-0000-0000-000000000000/oauth2/v2.0/token'
)
ADO_SCOPE = '499b84ac-1321-427f-aa17-267ca6975798/.default'
CLIENT_ID = '11111111-1111-1111-1111-111111111111'
_RANDOM_TOKEN_BYTES = 24


class _BackendCaller(_t.Protocol):
    """Typing protocol for the ``call_backend`` fixture."""

    def __call__(
        self: _t.Self,
        **overrides: str,
    ) -> str:
        """Call the backend with optional credential overrides."""


class _ErrorCase(_t.NamedTuple):
    """Parameters for an HTTP error test case."""

    status_code: int
    json_data: object
    body: str
    error_pattern: str


@pytest.fixture
def fake_token() -> str:
    """Generate a random token string for each test."""
    return secrets.token_urlsafe(_RANDOM_TOKEN_BYTES)


@pytest.fixture
def fake_secret() -> str:
    """Generate a random client secret for each test."""
    return secrets.token_urlsafe(_RANDOM_TOKEN_BYTES)


@pytest.fixture
def call_backend(fake_secret: str) -> _BackendCaller:
    """Return a helper that calls the backend with default credentials."""

    def _invoke(
        *,
        token_url: str = TOKEN_URL,
        client_id: str = CLIENT_ID,
        client_secret: str = fake_secret,
        **extra: str,
    ) -> str:
        return oauth2_mod.oauth2_client_credentials_backend(
            token_url=token_url,
            client_id=client_id,
            client_secret=client_secret,
            **extra,
        )

    return _invoke


def test_plugin_name() -> None:
    """Verify the plugin has the expected human-readable name."""
    expected = 'OAuth2 Client Credentials Token Lookup'
    assert oauth2_mod.oauth2_client_credentials_plugin.name == expected


def test_plugin_inputs_required_fields() -> None:
    """Verify that all three required input fields are declared."""
    field_ids = [
        field['id']
        for field in oauth2_mod.oauth2_client_credentials_inputs['fields']
    ]
    assert 'token_url' in field_ids
    assert 'client_id' in field_ids
    assert 'client_secret' in field_ids


def test_client_secret_is_marked_secret() -> None:
    """Ensure the client_secret field has the secret flag set."""
    secret_field = next(
        field
        for field in oauth2_mod.oauth2_client_credentials_inputs['fields']
        if field['id'] == 'client_secret'
    )
    assert secret_field['secret'] is True


def test_metadata_has_scope() -> None:
    """Verify scope is available as a metadata field."""
    metadata_ids = [
        meta['id']
        for meta in oauth2_mod.oauth2_client_credentials_inputs['metadata']
    ]
    assert 'scope' in metadata_ids


def test_plugin_backend_is_callable() -> None:
    """Ensure the backend function can be called."""
    assert callable(oauth2_mod.oauth2_client_credentials_plugin.backend)


def test_plugin_has_description() -> None:
    """Verify the plugin has a non-empty description."""
    desc = oauth2_mod.oauth2_client_credentials_plugin.plugin_description
    assert desc
    assert 'OAuth2' in desc


def test_successful_token_fetch(
    responses: _responses_mod.RequestsMock,
    call_backend: _BackendCaller,
    fake_token: str,
) -> None:
    """Test a successful token retrieval."""
    responses.post(
        TOKEN_URL,
        json={
            'access_token': fake_token,
            'token_type': 'Bearer',
            'expires_in': 3600,
        },
        status=http.HTTPStatus.OK,
    )

    assert call_backend(scope=ADO_SCOPE) == fake_token


def test_request_includes_grant_type(
    responses: _responses_mod.RequestsMock,
    call_backend: _BackendCaller,
    fake_token: str,
) -> None:
    """Verify the POST body includes grant_type=client_credentials."""
    responses.post(
        TOKEN_URL,
        json={'access_token': fake_token},
        status=http.HTTPStatus.OK,
    )

    call_backend(scope=ADO_SCOPE)

    sent_body = parse_qs(responses.calls[0].request.body)
    assert sent_body['grant_type'] == ['client_credentials']
    assert sent_body['scope'] == [ADO_SCOPE]


@pytest.mark.parametrize(
    'scope_value',
    (
        pytest.param('', id='empty-string'),
        pytest.param(None, id='none-via-default'),
    ),
)
def test_no_scope_omits_scope_from_request(
    responses: _responses_mod.RequestsMock,
    call_backend: _BackendCaller,
    fake_token: str,
    scope_value: str | None,
) -> None:
    """Verify that an empty or missing scope is not sent."""
    responses.post(
        TOKEN_URL,
        json={'access_token': fake_token},
        status=http.HTTPStatus.OK,
    )

    if scope_value is None:
        call_backend()
    else:
        call_backend(scope=scope_value)

    sent_body = parse_qs(responses.calls[0].request.body)
    assert 'scope' not in sent_body


@pytest.mark.parametrize(
    'token_url',
    (
        pytest.param(
            'https://login.microsoftonline.com'
            '/00000000-0000-0000-0000-000000000000/oauth2/v2.0/token',
            id='entra-id',
        ),
        pytest.param(
            'https://keycloak.example.com'
            '/realms/myrealm/protocol/openid-connect/token',
            id='keycloak',
        ),
        pytest.param(
            'https://dev-12345.okta.com/oauth2/default/v1/token',
            id='okta',
        ),
    ),
)
def test_works_with_various_providers(
    responses: _responses_mod.RequestsMock,
    call_backend: _BackendCaller,
    fake_token: str,
    token_url: str,
) -> None:
    """Verify the plugin works with different OAuth2 provider URLs."""
    responses.post(
        token_url,
        json={'access_token': fake_token},
        status=http.HTTPStatus.OK,
    )

    assert call_backend(token_url=token_url) == fake_token
    assert responses.calls[0].request.url == token_url


@pytest.mark.parametrize(
    'error_case',
    (
        pytest.param(
            _ErrorCase(
                status_code=http.HTTPStatus.UNAUTHORIZED,
                json_data={
                    'error': 'invalid_client',
                    'error_description': 'Invalid client secret provided.',
                },
                body='',
                error_pattern=(
                    r'Token request failed.*HTTP 401.*Invalid client secret'
                ),
            ),
            id='invalid-credentials',
        ),
        pytest.param(
            _ErrorCase(
                status_code=http.HTTPStatus.BAD_REQUEST,
                json_data={
                    'error': 'invalid_request',
                    'error_description': 'Tenant not found.',
                },
                body='',
                error_pattern=r'Tenant not found',
            ),
            id='bad-request',
        ),
        pytest.param(
            _ErrorCase(
                status_code=http.HTTPStatus.SERVICE_UNAVAILABLE,
                json_data=None,
                body='Service Unavailable',
                error_pattern=r'HTTP 503.*Service Unavailable',
            ),
            id='non-json-error',
        ),
        pytest.param(
            _ErrorCase(
                status_code=http.HTTPStatus.BAD_REQUEST,
                json_data=['not', 'a', 'dict'],
                body='',
                error_pattern=r'HTTP 400',
            ),
            id='non-dict-json-error',
        ),
    ),
)
def test_http_errors_raise_value_error(
    responses: _responses_mod.RequestsMock,
    call_backend: _BackendCaller,
    error_case: _ErrorCase,
) -> None:
    """Test that HTTP errors are converted to ValueError."""
    if error_case.json_data is not None:
        responses.post(
            TOKEN_URL,
            json=error_case.json_data,
            status=error_case.status_code,
        )
    else:
        responses.post(
            TOKEN_URL,
            body=error_case.body,
            status=error_case.status_code,
        )

    with pytest.raises(ValueError, match=error_case.error_pattern):
        call_backend()


@pytest.mark.parametrize(
    ('json_data', 'body'),
    (
        pytest.param(
            {'token_type': 'Bearer', 'expires_in': 3600},
            None,
            id='missing-access-token-key',
        ),
        pytest.param(
            ['not', 'a', 'dict'],
            None,
            id='non-dict-json',
        ),
        pytest.param(
            None,
            'not json at all',
            id='unparseable-json',
        ),
        pytest.param(
            {'access_token': None},
            None,
            id='null-access-token',
        ),
        pytest.param(
            {'access_token': ''},
            None,
            id='empty-access-token',
        ),
    ),
)
def test_malformed_success_response(
    responses: _responses_mod.RequestsMock,
    call_backend: _BackendCaller,
    json_data: object,
    body: str | None,
) -> None:
    """Test handling of 200 responses without a usable access_token."""
    if json_data is not None:
        responses.post(
            TOKEN_URL,
            json=json_data,
            status=http.HTTPStatus.OK,
        )
    else:
        responses.post(
            TOKEN_URL,
            body=body or '',
            status=http.HTTPStatus.OK,
        )

    with pytest.raises(
        ValueError,
        match=r'did not contain an access_token',
    ):
        call_backend()


def test_rejects_non_https_token_url(
    responses: _responses_mod.RequestsMock,
    call_backend: _BackendCaller,
) -> None:
    """Verify non-https token endpoints are rejected before posting."""
    with pytest.raises(ValueError, match=r'must use https'):
        call_backend(
            token_url=(
                'http://login.microsoftonline.com'
                '/00000000-0000-0000-0000-000000000000/oauth2/v2.0/token'
            ),
        )

    assert not responses.calls


def test_redirect_is_rejected(
    responses: _responses_mod.RequestsMock,
    call_backend: _BackendCaller,
) -> None:
    """Verify a 3xx redirect response raises ValueError."""
    responses.post(
        TOKEN_URL,
        body='Redirecting',
        status=http.HTTPStatus.TEMPORARY_REDIRECT,
    )

    with pytest.raises(
        ValueError,
        match=r'Token request failed.*HTTP 307',
    ):
        call_backend()


def test_connection_error(
    responses: _responses_mod.RequestsMock,
    call_backend: _BackendCaller,
) -> None:
    """Test that connection errors are wrapped in ValueError."""
    responses.post(
        TOKEN_URL,
        body=requests.exceptions.ConnectionError('Connection refused'),
    )

    with pytest.raises(
        ValueError,
        match=r'Could not connect to token endpoint',
    ):
        call_backend()


def test_timeout_error(
    responses: _responses_mod.RequestsMock,
    call_backend: _BackendCaller,
) -> None:
    """Test that timeout errors are wrapped in ValueError."""
    responses.post(
        TOKEN_URL,
        body=requests.exceptions.Timeout('Read timed out'),
    )

    with pytest.raises(
        ValueError,
        match=r'Timed out requesting token',
    ):
        call_backend()


def test_generic_request_exception(
    responses: _responses_mod.RequestsMock,
    call_backend: _BackendCaller,
) -> None:
    """Test that other RequestException subclasses are wrapped."""
    responses.post(
        TOKEN_URL,
        body=requests.exceptions.TooManyRedirects(
            'Exceeded 30 redirects',
        ),
    )

    with pytest.raises(
        ValueError,
        match=r'Failed requesting token from endpoint',
    ):
        call_backend()


def test_discarded_kwargs_are_ignored(
    responses: _responses_mod.RequestsMock,
    fake_token: str,
    fake_secret: str,
) -> None:
    """Verify unexpected kwargs don't break the backend."""
    responses.post(
        TOKEN_URL,
        json={'access_token': fake_token},
        status=http.HTTPStatus.OK,
    )

    token = oauth2_mod.oauth2_client_credentials_backend(
        token_url=TOKEN_URL,
        client_id=CLIENT_ID,
        client_secret=fake_secret,
        description='some metadata that may be passed',  # type: ignore[call-arg]
    )

    assert token == fake_token
