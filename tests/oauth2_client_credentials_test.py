"""Tests for the OAuth2 Client Credentials Token credential plugin."""

import http
from typing import NamedTuple, Protocol

import pytest
from pytest_mock import MockerFixture

from awx_plugins.credentials import (
    oauth2_client_credentials as oauth2_mod,
)


TOKEN_URL = (
    'https://login.microsoftonline.com'
    '/00000000-0000-0000-0000-000000000000/oauth2/v2.0/token'
)
ADO_SCOPE = '499b84ac-1321-427f-aa17-267ca6975798/.default'
FAKE_TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.fake.token'  # noqa: S105


class _BackendCaller(Protocol):
    """Typing protocol for the ``call_backend`` fixture."""

    def __call__(
        self,  # noqa: ANN101
        **overrides: str,
    ) -> str:
        """Call the backend with optional credential overrides."""


class _ErrorCase(NamedTuple):
    """Parameters for an HTTP error test case."""

    status_code: int
    json_data: object
    text: str
    error_pattern: str


class _FakeResponse:
    """Minimal stand-in for ``requests.Response``."""

    def __init__(
        self,  # noqa: ANN101
        status_code: int,
        json_data: object = None,
        text: str = '',
    ) -> None:
        self.status_code = status_code
        self._json_data = json_data
        self.text = text

    def json(self) -> object:  # noqa: ANN101
        """Return the stored JSON payload or raise."""
        if self._json_data is None:
            raise ValueError('No JSON')
        return self._json_data


@pytest.fixture
def call_backend() -> _BackendCaller:
    """Return a helper that calls the backend with default credentials."""

    def _invoke(**overrides: str) -> str:
        kwargs: dict[str, str] = {
            'token_url': TOKEN_URL,
            'client_id': '11111111-1111-1111-1111-111111111111',
            'client_secret': 'test-secret-value',  # noqa: S105
        }
        kwargs.update(overrides)
        return oauth2_mod.oauth2_client_credentials_backend(**kwargs)

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
    mocker: MockerFixture,
    call_backend: _BackendCaller,
) -> None:
    """Test a successful token retrieval."""
    mocker.patch.object(
        oauth2_mod.requests,
        'post',
        return_value=_FakeResponse(
            status_code=http.HTTPStatus.OK,
            json_data={
                'access_token': FAKE_TOKEN,
                'token_type': 'Bearer',
                'expires_in': 3600,
            },
        ),
    )

    assert call_backend(scope=ADO_SCOPE) == FAKE_TOKEN


def test_request_includes_grant_type(
    mocker: MockerFixture,
    call_backend: _BackendCaller,
) -> None:
    """Verify the POST body includes grant_type=client_credentials."""
    mock_post = mocker.patch.object(
        oauth2_mod.requests,
        'post',
        return_value=_FakeResponse(
            status_code=http.HTTPStatus.OK,
            json_data={'access_token': FAKE_TOKEN},
        ),
    )

    call_backend(scope=ADO_SCOPE)

    post_data = mock_post.call_args[1]['data']
    assert post_data['grant_type'] == 'client_credentials'
    assert post_data['scope'] == ADO_SCOPE


@pytest.mark.parametrize(
    'scope_value',
    (
        pytest.param('', id='empty-string'),
        pytest.param(None, id='none-via-default'),
    ),
)
def test_no_scope_omits_scope_from_request(
    mocker: MockerFixture,
    call_backend: _BackendCaller,
    scope_value: str | None,
) -> None:
    """Verify that an empty or missing scope is not sent."""
    mock_post = mocker.patch.object(
        oauth2_mod.requests,
        'post',
        return_value=_FakeResponse(
            status_code=http.HTTPStatus.OK,
            json_data={'access_token': FAKE_TOKEN},
        ),
    )

    if scope_value is None:
        call_backend()
    else:
        call_backend(scope=scope_value)

    post_data = mock_post.call_args[1]['data']
    assert 'scope' not in post_data


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
    mocker: MockerFixture,
    call_backend: _BackendCaller,
    token_url: str,
) -> None:
    """Verify the plugin works with different OAuth2 provider URLs."""
    mocker.patch.object(
        oauth2_mod.requests,
        'post',
        return_value=_FakeResponse(
            status_code=http.HTTPStatus.OK,
            json_data={'access_token': FAKE_TOKEN},
        ),
    )

    assert call_backend(token_url=token_url) == FAKE_TOKEN


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
                text='',
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
                text='',
                error_pattern=r'Tenant not found',
            ),
            id='bad-request',
        ),
        pytest.param(
            _ErrorCase(
                status_code=http.HTTPStatus.SERVICE_UNAVAILABLE,
                json_data=None,
                text='Service Unavailable',
                error_pattern=r'HTTP 503.*Service Unavailable',
            ),
            id='non-json-error',
        ),
        pytest.param(
            _ErrorCase(
                status_code=http.HTTPStatus.BAD_REQUEST,
                json_data=['not', 'a', 'dict'],
                text='Bad Request',
                error_pattern=r'HTTP 400.*Bad Request',
            ),
            id='non-dict-json-error',
        ),
    ),
)
def test_http_errors_raise_value_error(
    mocker: MockerFixture,
    call_backend: _BackendCaller,
    error_case: _ErrorCase,
) -> None:
    """Test that HTTP errors are converted to ValueError."""
    mocker.patch.object(
        oauth2_mod.requests,
        'post',
        return_value=_FakeResponse(
            status_code=error_case.status_code,
            json_data=error_case.json_data,
            text=error_case.text,
        ),
    )

    with pytest.raises(ValueError, match=error_case.error_pattern):
        call_backend()


@pytest.mark.parametrize(
    (
        'json_data',
        'text',
    ),
    (
        pytest.param(
            {'token_type': 'Bearer', 'expires_in': 3600},
            '',
            id='missing-access-token-key',
        ),
        pytest.param(
            ['not', 'a', 'dict'],
            '',
            id='non-dict-json',
        ),
        pytest.param(
            None,
            'not json at all',
            id='unparseable-json',
        ),
    ),
)
def test_malformed_success_response(
    mocker: MockerFixture,
    call_backend: _BackendCaller,
    json_data: object,
    text: str,
) -> None:
    """Test handling of 200 responses without a usable access_token."""
    mocker.patch.object(
        oauth2_mod.requests,
        'post',
        return_value=_FakeResponse(
            status_code=http.HTTPStatus.OK,
            json_data=json_data,
            text=text,
        ),
    )

    with pytest.raises(
        ValueError,
        match=r'did not contain an access_token',
    ):
        call_backend()


def test_connection_error(
    mocker: MockerFixture,
    call_backend: _BackendCaller,
) -> None:
    """Test that connection errors are wrapped in ValueError."""
    mocker.patch.object(
        oauth2_mod.requests,
        'post',
        side_effect=oauth2_mod.requests.exceptions.ConnectionError(
            'Connection refused',
        ),
    )

    with pytest.raises(
        ValueError,
        match=r'Could not connect to token endpoint',
    ):
        call_backend()


def test_timeout_error(
    mocker: MockerFixture,
    call_backend: _BackendCaller,
) -> None:
    """Test that timeout errors are wrapped in ValueError."""
    mocker.patch.object(
        oauth2_mod.requests,
        'post',
        side_effect=oauth2_mod.requests.exceptions.Timeout(
            'Read timed out',
        ),
    )

    with pytest.raises(
        ValueError,
        match=r'Timed out requesting token',
    ):
        call_backend()


def test_generic_request_exception(
    mocker: MockerFixture,
    call_backend: _BackendCaller,
) -> None:
    """Test that other RequestException subclasses are wrapped."""
    mocker.patch.object(
        oauth2_mod.requests,
        'post',
        side_effect=oauth2_mod.requests.exceptions.TooManyRedirects(
            'Exceeded 30 redirects',
        ),
    )

    with pytest.raises(
        ValueError,
        match=r'Failed requesting token from endpoint',
    ):
        call_backend()


def test_discarded_kwargs_are_ignored(
    mocker: MockerFixture,
) -> None:
    """Verify unexpected kwargs don't break the backend."""
    mocker.patch.object(
        oauth2_mod.requests,
        'post',
        return_value=_FakeResponse(
            status_code=http.HTTPStatus.OK,
            json_data={'access_token': FAKE_TOKEN},
        ),
    )

    token = oauth2_mod.oauth2_client_credentials_backend(
        token_url=TOKEN_URL,
        client_id='11111111-1111-1111-1111-111111111111',
        client_secret='test-secret-value',  # noqa: S105
        description='some metadata that may be passed',  # type: ignore[call-arg]
    )

    assert token == FAKE_TOKEN
