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


class _StubbedResponse(_t.NamedTuple):
    """Parameters for a stubbed token-endpoint response.

    ``response_kwargs`` are unpacked into ``responses.post`` (for
    example ``{'json': ...}`` or ``{'body': ...}``) so the test body
    stays branch-free.
    """

    label: str
    status_code: int
    response_kwargs: dict[str, object]
    error_pattern: str

    def __str__(self: _t.Self) -> str:
        """Return the human-readable parametrize id."""
        return self.label


def _parse_form_body(raw_body: object) -> dict[str, list[str]]:
    """Parse a URL-encoded form body from a recorded request."""
    assert isinstance(raw_body, (str, bytes))
    body_text = raw_body if isinstance(raw_body, str) else raw_body.decode()
    return parse_qs(body_text)


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

    sent_body = _parse_form_body(responses.calls[0].request.body)
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

    sent_body = _parse_form_body(responses.calls[0].request.body)
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
        _StubbedResponse(
            label='invalid-credentials',
            status_code=http.HTTPStatus.UNAUTHORIZED,
            response_kwargs={
                'json': {
                    'error': 'invalid_client',
                    'error_description': 'Invalid client secret provided.',
                },
            },
            error_pattern=(
                r'Token request failed.*HTTP 401.*Invalid client secret'
            ),
        ),
        _StubbedResponse(
            label='bad-request',
            status_code=http.HTTPStatus.BAD_REQUEST,
            response_kwargs={
                'json': {
                    'error': 'invalid_request',
                    'error_description': 'Tenant not found.',
                },
            },
            error_pattern=r'Tenant not found',
        ),
        _StubbedResponse(
            label='non-json-error',
            status_code=http.HTTPStatus.SERVICE_UNAVAILABLE,
            response_kwargs={'body': 'Service Unavailable'},
            error_pattern=r'HTTP 503.*Service Unavailable',
        ),
        _StubbedResponse(
            label='non-dict-json-error',
            status_code=http.HTTPStatus.BAD_REQUEST,
            response_kwargs={'json': ['not', 'a', 'dict']},
            error_pattern=r'HTTP 400',
        ),
    ),
    ids=str,
)
def test_http_errors_raise_value_error(
    responses: _responses_mod.RequestsMock,
    call_backend: _BackendCaller,
    error_case: _StubbedResponse,
) -> None:
    """Test that HTTP errors are converted to ValueError."""
    responses.post(
        TOKEN_URL,
        status=error_case.status_code,
        **error_case.response_kwargs,
    )

    with pytest.raises(ValueError, match=error_case.error_pattern):
        call_backend()


@pytest.mark.parametrize(
    'response_case',
    (
        _StubbedResponse(
            label='missing-access-token-key',
            status_code=http.HTTPStatus.OK,
            response_kwargs={
                'json': {'token_type': 'Bearer', 'expires_in': 3600},
            },
            error_pattern=r'did not contain an access_token',
        ),
        _StubbedResponse(
            label='non-dict-json',
            status_code=http.HTTPStatus.OK,
            response_kwargs={'json': ['not', 'a', 'dict']},
            error_pattern=r'did not contain an access_token',
        ),
        _StubbedResponse(
            label='unparseable-json',
            status_code=http.HTTPStatus.OK,
            response_kwargs={'body': 'not json at all'},
            error_pattern=r'did not contain an access_token',
        ),
        _StubbedResponse(
            label='null-access-token',
            status_code=http.HTTPStatus.OK,
            response_kwargs={'json': {'access_token': None}},
            error_pattern=r'did not contain an access_token',
        ),
        _StubbedResponse(
            label='empty-access-token',
            status_code=http.HTTPStatus.OK,
            response_kwargs={'json': {'access_token': ''}},
            error_pattern=r'did not contain an access_token',
        ),
    ),
    ids=str,
)
def test_malformed_success_response(
    responses: _responses_mod.RequestsMock,
    call_backend: _BackendCaller,
    response_case: _StubbedResponse,
) -> None:
    """Test handling of 200 responses without a usable access_token."""
    responses.post(
        TOKEN_URL,
        status=response_case.status_code,
        **response_case.response_kwargs,
    )

    with pytest.raises(ValueError, match=response_case.error_pattern):
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


@pytest.mark.parametrize(
    ('exception', 'error_pattern'),
    (
        pytest.param(
            requests.exceptions.ConnectionError('Connection refused'),
            r'Could not connect to token endpoint',
            id='connection-error',
        ),
        pytest.param(
            requests.exceptions.Timeout('Read timed out'),
            r'Timed out requesting token',
            id='timeout',
        ),
        pytest.param(
            requests.exceptions.TooManyRedirects(
                'Exceeded 30 redirects',
            ),
            r'Failed requesting token from endpoint',
            id='too-many-redirects',
        ),
    ),
)
def test_transport_errors_raise_value_error(
    responses: _responses_mod.RequestsMock,
    call_backend: _BackendCaller,
    exception: Exception,
    error_pattern: str,
) -> None:
    """Test that transport failures are wrapped in ValueError."""
    responses.post(TOKEN_URL, body=exception)

    with pytest.raises(ValueError, match=error_pattern):
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
