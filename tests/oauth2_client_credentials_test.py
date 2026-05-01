"""Tests for the OAuth2 Client Credentials Token credential plugin."""

import http

import pytest
from pytest_mock import MockerFixture

from awx_plugins.credentials import (
    oauth2_client_credentials as oauth2_mod,
)

TOKEN_URL = (
    'https://login.microsoftonline.com'
    '/00000000-0000-0000-0000-000000000000/oauth2/v2.0/token'
)
CLIENT_ID = '11111111-1111-1111-1111-111111111111'
CLIENT_SECRET = 'test-secret-value'  # noqa: S105
ADO_SCOPE = '499b84ac-1321-427f-aa17-267ca6975798/.default'
FAKE_TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.fake.token'  # noqa: S105


class _FakeResponse:
    """Minimal stand-in for ``requests.Response``."""

    def __init__(  # noqa: ANN101
        self,
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


def test_successful_token_fetch(mocker: MockerFixture) -> None:
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

    token = oauth2_mod.oauth2_client_credentials_backend(
        token_url=TOKEN_URL,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scope=ADO_SCOPE,
    )

    assert token == FAKE_TOKEN


def test_request_includes_grant_type(mocker: MockerFixture) -> None:
    """Verify the POST body includes grant_type=client_credentials."""
    mock_post = mocker.patch.object(
        oauth2_mod.requests,
        'post',
        return_value=_FakeResponse(
            status_code=http.HTTPStatus.OK,
            json_data={'access_token': FAKE_TOKEN},
        ),
    )

    oauth2_mod.oauth2_client_credentials_backend(
        token_url=TOKEN_URL,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scope=ADO_SCOPE,
    )

    call_kwargs = mock_post.call_args
    assert call_kwargs[1]['data']['grant_type'] == 'client_credentials'
    assert call_kwargs[1]['data']['client_id'] == CLIENT_ID
    assert call_kwargs[1]['data']['scope'] == ADO_SCOPE


@pytest.mark.parametrize(
    'scope_value',
    (
        pytest.param('', id='empty-string'),
        pytest.param(None, id='none-via-default'),
    ),
)
def test_no_scope_omits_scope_from_request(
    mocker: MockerFixture,
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

    kwargs: dict[str, str] = {
        'token_url': TOKEN_URL,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
    }
    if scope_value is not None:
        kwargs['scope'] = scope_value

    oauth2_mod.oauth2_client_credentials_backend(**kwargs)

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

    token = oauth2_mod.oauth2_client_credentials_backend(
        token_url=token_url,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
    )

    assert token == FAKE_TOKEN


@pytest.mark.parametrize(
    (
        'status_code',
        'response_body',
        'error_pattern',
    ),
    (
        pytest.param(
            http.HTTPStatus.UNAUTHORIZED,
            {
                'error': 'invalid_client',
                'error_description': 'Invalid client secret provided.',
            },
            r'Token request failed.*HTTP 401.*Invalid client secret',
            id='invalid-credentials',
        ),
        pytest.param(
            http.HTTPStatus.BAD_REQUEST,
            {
                'error': 'invalid_request',
                'error_description': 'Tenant not found.',
            },
            r'Tenant not found',
            id='bad-request',
        ),
    ),
)
def test_http_errors_raise_value_error(
    mocker: MockerFixture,
    status_code: int,
    response_body: dict[str, str],
    error_pattern: str,
) -> None:
    """Test that HTTP errors are converted to ValueError."""
    mocker.patch.object(
        oauth2_mod.requests,
        'post',
        return_value=_FakeResponse(
            status_code=status_code,
            json_data=response_body,
        ),
    )

    with pytest.raises(ValueError, match=error_pattern):
        oauth2_mod.oauth2_client_credentials_backend(
            token_url=TOKEN_URL,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
        )


def test_non_json_error_response(mocker: MockerFixture) -> None:
    """Test handling of non-JSON error responses."""
    mocker.patch.object(
        oauth2_mod.requests,
        'post',
        return_value=_FakeResponse(
            status_code=http.HTTPStatus.SERVICE_UNAVAILABLE,
            text='Service Unavailable',
        ),
    )

    with pytest.raises(
        ValueError,
        match=r'HTTP 503.*Service Unavailable',
    ):
        oauth2_mod.oauth2_client_credentials_backend(
            token_url=TOKEN_URL,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
        )


def test_missing_access_token_in_response(
    mocker: MockerFixture,
) -> None:
    """Test handling of responses without an access_token field."""
    mocker.patch.object(
        oauth2_mod.requests,
        'post',
        return_value=_FakeResponse(
            status_code=http.HTTPStatus.OK,
            json_data={
                'token_type': 'Bearer',
                'expires_in': 3600,
            },
        ),
    )

    with pytest.raises(
        ValueError,
        match=r'did not contain an access_token',
    ):
        oauth2_mod.oauth2_client_credentials_backend(
            token_url=TOKEN_URL,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
        )


def test_non_dict_json_success_response(
    mocker: MockerFixture,
) -> None:
    """Test handling of a 200 response whose JSON is not an object."""
    mocker.patch.object(
        oauth2_mod.requests,
        'post',
        return_value=_FakeResponse(
            status_code=http.HTTPStatus.OK,
            json_data=['not', 'a', 'dict'],
        ),
    )

    with pytest.raises(
        ValueError,
        match=r'did not contain an access_token',
    ):
        oauth2_mod.oauth2_client_credentials_backend(
            token_url=TOKEN_URL,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
        )


def test_non_dict_json_error_response(
    mocker: MockerFixture,
) -> None:
    """Test handling of an error response whose JSON is not an object."""
    mocker.patch.object(
        oauth2_mod.requests,
        'post',
        return_value=_FakeResponse(
            status_code=http.HTTPStatus.BAD_REQUEST,
            json_data=['not', 'a', 'dict'],
            text='Bad Request',
        ),
    )

    with pytest.raises(
        ValueError,
        match=r'HTTP 400.*Bad Request',
    ):
        oauth2_mod.oauth2_client_credentials_backend(
            token_url=TOKEN_URL,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
        )


def test_connection_error(mocker: MockerFixture) -> None:
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
        oauth2_mod.oauth2_client_credentials_backend(
            token_url=TOKEN_URL,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
        )


def test_timeout_error(mocker: MockerFixture) -> None:
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
        oauth2_mod.oauth2_client_credentials_backend(
            token_url=TOKEN_URL,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
        )


def test_discarded_kwargs_are_ignored(mocker: MockerFixture) -> None:
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
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        description='some metadata that may be passed',  # type: ignore[call-arg]
    )

    assert token == FAKE_TOKEN
