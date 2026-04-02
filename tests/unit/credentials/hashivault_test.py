# pylint: disable=protected-access  # tests access private methods legitimately
"""Tests for HashiCorp Vault credential plugins."""

import typing as _t

# NOTE: The forbidden import here is only used for typing, which warrants
# NOTE: suppressing the respective pylint and ruff rules.
# pylint: disable-next=deprecated-module,preferred-module
from unittest import mock as _unittest_mock  # noqa: TID251 -- forbidden import

import pytest
from pytest_mock import MockerFixture

from awx_plugins.credentials import _types, hashivault
from awx_plugins.credentials.plugin import CredentialPlugin


def test_hashivault_approle_auth() -> None:
    """Test ``approle_auth()`` method returns known secret."""
    kwargs = {
        'role_id': 'the_role_id',
        'secret_id': 'the_secret_id',
    }
    expected_res = {
        'role_id': 'the_role_id',
        'secret_id': 'the_secret_id',
    }
    res = hashivault.approle_auth(**kwargs)  # type: ignore[no-untyped-call]
    assert res == expected_res


def test_hashivault_kubernetes_auth(mocker: MockerFixture) -> None:
    """Test ``kubernetes_auth()`` method returns known JWT."""
    kwargs = {
        'kubernetes_role': 'the_kubernetes_role',
    }
    expected_res = {
        'role': 'the_kubernetes_role',
        'jwt': 'the_jwt',
    }
    path_mock = mocker.patch('pathlib.Path')
    path_mock.return_value.open = mocker.mock_open(read_data='the_jwt')
    res = hashivault.kubernetes_auth(  # type: ignore[no-untyped-call]
        **kwargs,
    )
    path_mock.assert_called_with(
        '/var/run/secrets/kubernetes.io/serviceaccount/token',
    )
    assert res == expected_res


def test_hashivault_client_cert_auth_explicit_role() -> None:  # noqa: WPS118
    """Test ``client_cert_auth()`` with explicit role returns a certificate."""
    kwargs = {
        'client_cert_role': 'test-cert-1',
    }
    expected_res = {
        'name': 'test-cert-1',
    }
    res = hashivault.client_cert_auth(  # type: ignore[no-untyped-call]
        **kwargs,
    )
    assert res == expected_res


def test_hashivault_client_cert_auth_no_role() -> None:
    """Test ``client_cert_auth()`` with no role returns no name."""
    kwargs: dict[str, str] = {}
    expected_res = {
        'name': None,
    }
    res = hashivault.client_cert_auth(  # type: ignore[no-untyped-call]
        **kwargs,
    )
    assert res == expected_res


def test_hashivault_userpass_auth() -> None:
    """Test ``userpass_auth()`` returns the password."""
    kwargs = {'username': 'the_username', 'password': 'the_password'}
    expected_res = {'username': 'the_username', 'password': 'the_password'}
    res = hashivault.userpass_auth(**kwargs)  # type: ignore[no-untyped-call]
    assert res == expected_res


@pytest.mark.parametrize(
    'arbitrary_kwargs',
    ({}, {'utter': 'nonsense'}),
    ids=('no-additional-keyword-args', 'with-additional-keyword-arg'),
)
def test_hashivault_workload_identity_auth(
    arbitrary_kwargs: dict[str, str],
) -> None:
    """Test ``workload_identity_auth()`` returns the token."""
    sentinel_role_value = 'the_jwt_role'
    sentinel_jwt_value = 'the_jwt_token'
    expected_jwt_object = {
        'role': sentinel_role_value,
        'jwt': sentinel_jwt_value,
    }

    auth = hashivault.workload_identity_auth
    computed_jwt_object = auth(  # type: ignore[no-untyped-call]
        workload_identity_token=sentinel_jwt_value,
        jwt_role=sentinel_role_value,
        **arbitrary_kwargs,
    )

    assert computed_jwt_object == expected_jwt_object


def test_hashivault_handle_auth_token() -> None:
    """Test ``handle_auth()`` with token auth returns the token."""
    kwargs = {
        'token': 'the_token',
    }
    token = hashivault.handle_auth(**kwargs)  # type: ignore[no-untyped-call]
    assert token == kwargs['token']


def test_hashivault_handle_auth_approle(mocker: MockerFixture) -> None:
    """Test ``handle_auth()`` with approle auth returns the token."""
    kwargs = {
        'role_id': 'the_role_id',
        'secret_id': 'the_secret_id',
    }
    method_mock = mocker.patch.object(hashivault, 'method_auth')
    method_mock.return_value = 'the_token'
    token = hashivault.handle_auth(  # type: ignore[no-untyped-call]
        **kwargs,
    )
    method_mock.assert_called_with(**kwargs, auth_param=kwargs)
    assert token == 'the_token'


def test_hashivault_handle_auth_kubernetes(mocker: MockerFixture) -> None:
    """Test ``handle_auth()`` with k8s role and JWT auth returns a token."""
    kwargs = {
        'kubernetes_role': 'the_kubernetes_role',
    }
    method_mock = mocker.patch.object(hashivault, 'method_auth')
    path_mock = mocker.patch('pathlib.Path')
    path_mock.return_value.open = mocker.mock_open(read_data='the_jwt')
    method_mock.return_value = 'the_token'
    token = hashivault.handle_auth(  # type: ignore[no-untyped-call]
        **kwargs,
    )
    method_mock.assert_called_with(
        **kwargs,
        auth_param={
            'role': 'the_kubernetes_role',
            'jwt': 'the_jwt',
        },
    )
    assert token == 'the_token'


def test_hashivault_handle_auth_client_cert(mocker: MockerFixture) -> None:
    """Test ``handle_auth()`` with client certificate auth returns a token."""
    kwargs = {
        'client_cert_public': 'foo',
        'client_cert_private': 'bar',
        'client_cert_role': 'test-cert-1',
    }
    auth_params = {
        'name': 'test-cert-1',
    }
    method_mock = mocker.patch.object(hashivault, 'method_auth')
    method_mock.return_value = 'the_token'
    token = hashivault.handle_auth(  # type: ignore[no-untyped-call]
        **kwargs,
    )
    method_mock.assert_called_with(**kwargs, auth_param=auth_params)
    assert token == 'the_token'


def test_hashivault_handle_auth_workload_identity(
    mocker: MockerFixture,
) -> None:
    """Test handle auth with workload identity auth."""
    workload_id_kwargs = {
        'workload_identity_token': 'the_jwt_token',
        'jwt_role': 'the_jwt_role',
        'default_auth_path': 'jwt',
        'url': 'https://vault.example.com',
    }
    auth_params = {
        'role': 'the_jwt_role',
        'jwt': 'the_jwt_token',
    }
    method_mock = mocker.patch.object(
        hashivault,
        'method_auth',
        autospec=True,
        return_value='the_token',
    )
    token = hashivault.handle_auth(**workload_id_kwargs)  # type: ignore[no-untyped-call]
    method_mock.assert_called_with(
        **workload_id_kwargs,
        auth_param=auth_params,
    )
    assert token == 'the_token'


def test_hashivault_handle_auth_not_enough_args() -> None:
    """Test ``handle_auth()`` errors out on inssuficient arguments."""
    expected_error_msg = (
        r'^Token, Username/Password, AppRole, Kubernetes, or TLS '
        r'authentication parameters must be set$'
    )
    with pytest.raises(Exception, match=expected_error_msg):
        hashivault.handle_auth()  # type: ignore[no-untyped-call]


@pytest.mark.parametrize(
    ('plugin', 'field_type', 'expected_ids'),
    (
        pytest.param(
            hashivault.hashivault_kv_plugin,
            'fields',
            [
                'url',
                'token',
                'cacert',
                'role_id',
                'secret_id',
                'client_cert_public',
                'client_cert_private',
                'client_cert_role',
                'namespace',
                'kubernetes_role',
                'username',
                'password',
                'default_auth_path',
                'api_version',
            ],
            id='kv-fields',
        ),
        pytest.param(
            hashivault.hashivault_kv_plugin,
            'metadata',
            [
                'secret_backend',
                'secret_path',
                'auth_path',
                'secret_key',
                'secret_version',
            ],
            id='kv-metadata',
        ),
        pytest.param(
            hashivault.hashivault_ssh_plugin,
            'fields',
            [
                'url',
                'token',
                'cacert',
                'role_id',
                'secret_id',
                'client_cert_public',
                'client_cert_private',
                'client_cert_role',
                'namespace',
                'kubernetes_role',
                'username',
                'password',
                'default_auth_path',
            ],
            id='ssh-fields',
        ),
        pytest.param(
            hashivault.hashivault_ssh_plugin,
            'metadata',
            [
                'public_key',
                'secret_path',
                'auth_path',
                'role',
                'valid_principals',
            ],
            id='ssh-metadata',
        ),
        pytest.param(
            hashivault.hashivault_kv_oidc_plugin,
            'fields',
            [
                'url',
                'api_version',
                'cacert',
                'default_auth_path',
                'jwt_role',
                'jwt_aud',
                'namespace',
                'workload_identity_token',
            ],
            id='kv-oidc-fields',
        ),
        pytest.param(
            hashivault.hashivault_kv_oidc_plugin,
            'metadata',
            [
                'secret_backend',
                'secret_path',
                'default_auth_path',
                'secret_key',
                'secret_version',
            ],
            id='kv-oidc-metadata',
        ),
        pytest.param(
            hashivault.hashivault_ssh_oidc_plugin,
            'fields',
            [
                'url',
                'cacert',
                'default_auth_path',
                'jwt_role',
                'jwt_aud',
                'namespace',
                'workload_identity_token',
            ],
            id='ssh-oidc-fields',
        ),
        pytest.param(
            hashivault.hashivault_ssh_oidc_plugin,
            'metadata',
            [
                'public_key',
                'secret_path',
                'default_auth_path',
                'role',
                'valid_principals',
            ],
            id='ssh-oidc-metadata',
        ),
    ),
)
def test_plugin_input_ids(
    plugin: CredentialPlugin,
    field_type: _t.Literal['fields', 'metadata'],
    expected_ids: list[str],
) -> None:
    """Verify plugin input fields/metadata are present with expected IDs."""
    plugin_inputs = plugin.inputs
    actual_ids = [plugin['id'] for plugin in plugin_inputs[field_type]]
    assert actual_ids == expected_ids


def test_workload_identity_token_field_internal() -> None:
    """Verify the workload_identity_token field is marked internal."""
    field = hashivault.workload_identity_token_field
    assert field['id'] == 'workload_identity_token'
    assert field['internal'] is True
    assert field['secret'] is True


@pytest.mark.parametrize(
    'plugin_inputs',
    (hashivault.hashi_kv_oidc_inputs, hashivault.hashi_ssh_oidc_inputs),
    ids=('kv-oidc', 'ssh-oidc'),
)
def test_workload_identity_token_field_not_req(
    plugin_inputs: _types.PluginInputs,
) -> None:
    """Verify ``workload_identity_token`` is not in the required list for OIDC plugins."""
    assert 'workload_identity_token' not in plugin_inputs['required']


@pytest.mark.parametrize(
    'plugin',
    (
        pytest.param(hashivault.hashivault_kv_oidc_plugin, id='kv-oidc'),
        pytest.param(hashivault.hashivault_ssh_oidc_plugin, id='ssh-oidc'),
    ),
)
def test_oidc_plugin_has_one_internal_field(
    plugin: CredentialPlugin,
) -> None:
    """Verify OIDC plugins have exactly one internal field."""
    internal_fields = [
        field for field in plugin.inputs['fields'] if field.get('internal')
    ]
    assert len(internal_fields) == 1
    assert internal_fields[0]['id'] == 'workload_identity_token'


@pytest.mark.parametrize(
    'plugin',
    (
        pytest.param(hashivault.hashivault_kv_plugin, id='kv'),
        pytest.param(hashivault.hashivault_ssh_plugin, id='ssh'),
    ),
)
def test_non_oidc_plugins_have_no_internal_fields(
    plugin: CredentialPlugin,
) -> None:
    """Verify non-OIDC plugins have no internal fields."""
    internal_fields = [
        field for field in plugin.inputs['fields'] if field.get('internal')
    ]
    assert internal_fields == []


@pytest.fixture
def handle_auth_mock(mocker: MockerFixture) -> object:
    """Make a mocked ``handle_auth`` callable returning 'test_token'."""
    return mocker.patch.object(
        hashivault,
        'handle_auth',
        autospec=True,
        return_value='test_token',
    )


@pytest.fixture
def session_class_mock(mocker: MockerFixture) -> object:
    """Make a mocked ``requests.Session`` class dummy."""
    return mocker.patch.object(
        hashivault.requests,
        'Session',
        autospec=True,
    )


@pytest.fixture
def _cert_files_mock(mocker: MockerFixture) -> None:
    """Replace ``CertFiles`` class with a dummy."""
    mocker.patch.object(
        hashivault,
        'CertFiles',
        autospec=True,
    ).return_value.__enter__.return_value = 'cert_path'


@pytest.fixture
def _suppress_raise_for_status(mocker: MockerFixture) -> None:
    """Suppress ``requests``' HTTP return code checks."""
    mocker.patch.object(hashivault, 'raise_for_status', autospec=True)


def test_vault_token_no_workload_identity(
    handle_auth_mock: _unittest_mock.Mock,
    session_class_mock: _unittest_mock.Mock,
) -> None:
    """Test ``_vault_token`` context manager doesn't revoke token without workload_identity_token."""
    vault_token_kwargs = {
        'url': 'https://vault.example.com',
        'token': 'test_token',
    }

    with hashivault._vault_token(**vault_token_kwargs) as token:
        assert token == 'test_token'

    handle_auth_mock.assert_called_once_with(**vault_token_kwargs)
    session_class_mock.return_value.post.assert_not_called()


@pytest.mark.parametrize(
    ('extra_kwargs', 'expected_headers'),
    (
        pytest.param(
            {},
            {'X-Vault-Token': 'test_token'},
            id='without-namespace',
        ),
        pytest.param(
            {'namespace': 'test-namespace'},
            {
                'X-Vault-Token': 'test_token',
                'X-Vault-Namespace': 'test-namespace',
            },
            id='with-namespace',
        ),
    ),
)
@pytest.mark.usefixtures('_cert_files_mock')
def test_vault_token_revokes_oidc_token(
    handle_auth_mock: _unittest_mock.Mock,
    session_class_mock: _unittest_mock.Mock,
    extra_kwargs: dict[str, str],
    expected_headers: dict[str, str],
) -> None:
    """Test ``_vault_token`` context manager revokes token for workload identity auth."""
    mock_session = session_class_mock.return_value
    mock_session.headers = {}

    kwargs = {
        'url': 'https://vault.example.com',
        'workload_identity_token': 'jwt_token',
        'jwt_role': 'test_role',
        'default_auth_path': 'jwt',
        **extra_kwargs,
    }

    with hashivault._vault_token(**kwargs) as token:
        assert token == 'test_token'

    handle_auth_mock.assert_called_once_with(**kwargs)
    for header, header_contents in expected_headers.items():
        assert mock_session.headers[header] == header_contents
    mock_session.post.assert_called_once()
    assert 'auth/token/revoke-self' in mock_session.post.call_args[0][0]
    mock_session.post.return_value.raise_for_status.assert_called_once()


@pytest.mark.usefixtures('_cert_files_mock')
def test_vault_token_revoke_failure(
    handle_auth_mock: _unittest_mock.Mock,
    session_class_mock: _unittest_mock.Mock,
) -> None:
    """Test ``_vault_token`` context manager raises when token revocation fails."""
    mock_session = session_class_mock.return_value
    mock_session.headers = {}
    mock_session.post.return_value.raise_for_status.side_effect = (
        hashivault.requests.HTTPError(
            '403 Client Error: Forbidden for url: ...',
        )
    )

    kwargs = {
        'url': 'https://vault.example.com',
        'workload_identity_token': 'jwt_token',
        'jwt_role': 'test_role',
        'default_auth_path': 'jwt',
    }

    def _use_vault_token() -> None:
        with hashivault._vault_token(**kwargs) as token:
            assert token == 'test_token'

    with pytest.raises(
        hashivault.requests.HTTPError,
        match='403 Client Error',
    ):
        _use_vault_token()

    handle_auth_mock.assert_called_once_with(**kwargs)


@pytest.mark.parametrize(
    ('backend_func', 'extra_kwargs'),
    (
        pytest.param(
            hashivault.kv_backend,
            {
                'api_version': 'v1',
                'secret_key': 'password',
                'secret_path': '/secret/path',
            },
            id='kv-backend-v1',
        ),
        pytest.param(
            hashivault.kv_backend,
            {
                'api_version': 'v2',
                'secret_key': 'password',
                'secret_path': '/secret/path',
            },
            id='kv-backend-v2',
        ),
        pytest.param(
            hashivault.kv_backend,
            {
                'api_version': 'v2',
                'secret_key': 'password',
                'namespace': 'test-namespace',
                'secret_path': '/secret/path',
            },
            id='kv-backend-v2-with-namespace',
        ),
        pytest.param(
            hashivault.kv_backend,
            {
                'api_version': 'v2',
                'secret_key': 'password',
                'secret_version': '3',
                'secret_path': '/secret/path',
            },
            id='kv-backend-v2-with-secret-version',
        ),
        pytest.param(
            hashivault.kv_backend,
            {
                'api_version': 'v2',
                'secret_key': 'password',
                'secret_backend': 'kv',
                'secret_path': '/secret/path',
            },
            id='kv-backend-v2-with-secret-backend',
        ),
        pytest.param(
            hashivault.kv_backend,
            {
                'api_version': 'v2',
                'secret_key': 'password',
                'namespace': 'test-namespace',
                'secret_backend': 'kv',
                'secret_version': '5',
                'secret_path': '/secret/path',
            },
            id='kv-backend-v2-with-all-params',
        ),
        pytest.param(
            hashivault.ssh_backend,
            {
                'secret_path': '/ssh',
                'role': 'test_ssh_role',
                'public_key': 'ssh-rsa AAAAB...',
            },
            id='ssh-backend',
        ),
        pytest.param(
            hashivault.ssh_backend,
            {
                'namespace': 'test-namespace',
                'secret_path': '/ssh',
                'role': 'test_ssh_role',
                'public_key': 'ssh-rsa AAAAB...',
            },
            id='ssh-backend-with-namespace',
        ),
    ),
)
@pytest.mark.usefixtures('_cert_files_mock', '_suppress_raise_for_status')
def test_backend_revokes_oidc_token(
    handle_auth_mock: _unittest_mock.Mock,
    mocker: MockerFixture,
    session_class_mock: _unittest_mock.Mock,
    backend_func: _t.Callable[[dict[str, str]], str],
    extra_kwargs: dict[str, str],
) -> None:
    """Test backend functions revoke token via context manager for OIDC auth."""
    # Common base kwargs for all OIDC auth scenarios
    base_kwargs = {
        'url': 'https://vault.example.com',
        'workload_identity_token': 'jwt_token',
        'jwt_role': 'test_role',
        'default_auth_path': 'jwt',
    }

    backend_kwargs = {**base_kwargs, **extra_kwargs}

    mock_get_or_post_session = mocker.Mock()
    mock_get_or_post_session.headers = {}

    # Configure mock response for secret fetch based on backend type
    # and use it as a get or post method on the session mock
    mock_secret_response = mocker.Mock()
    mock_secret_response.status_code = 200

    # MyPy is unhappy due to incomplete typing of the `backend_func` param but
    # we don't care too much for now.
    if backend_func is hashivault.kv_backend:  # type: ignore[comparison-overlap]
        mock_get_or_post_session.get.return_value = mock_secret_response

        api_version = extra_kwargs.get('api_version', 'v1')
        # kv_backend v1 expects {'data': {secret_key: value}}
        mock_secret_response.json.return_value = {
            'data': {'password': 'test_value'},
        }
        if api_version == 'v2':
            # kv_backend v2 expects {'data': {'data': {secret_key: value}}}
            mock_secret_response.json.return_value = {
                'data': mock_secret_response.json.return_value,
            }
    else:  # ssh_backend
        mock_get_or_post_session.post.return_value = mock_secret_response

        # ssh_backend expects {'data': {'signed_key': value}}
        mock_secret_response.json.return_value = {
            'data': {'signed_key': 'test_signed_key'},
        }

    mock_revoke_session = mocker.Mock()
    mock_revoke_session.headers = {}

    # requests.Session is called twice: once for secret fetch, once for revoke
    session_class_mock.side_effect = [
        mock_get_or_post_session,
        mock_revoke_session,
    ]

    # Call the backend function to retrieve the secret
    # Adding ignore[call-arg] since adding the explicit args to the backend
    # functions makes the linter trigger the "too few arguments supplied"
    backend_func(**backend_kwargs)  # type: ignore[call-arg]

    handle_auth_mock.assert_called_once()
    # Verify revocation was attempted
    mock_revoke_session.post.assert_called_once()
    assert 'auth/token/revoke-self' in mock_revoke_session.post.call_args[0][0]
    mock_revoke_session.post.return_value.raise_for_status.assert_called_once()


@pytest.mark.parametrize(
    'plugin',
    (
        pytest.param(hashivault.hashivault_kv_oidc_plugin, id='kv-oidc'),
        pytest.param(hashivault.hashivault_ssh_oidc_plugin, id='ssh-oidc'),
    ),
)
def test_oidc_plugin_has_description(plugin: CredentialPlugin) -> None:
    """Verify OIDC plugins have a non-empty plugin_description."""
    assert plugin.plugin_description != ''


@pytest.mark.parametrize(
    'plugin',
    (
        pytest.param(hashivault.hashivault_kv_plugin, id='kv'),
        pytest.param(hashivault.hashivault_ssh_plugin, id='ssh'),
    ),
)
def test_non_oidc_plugin_has_empty_description(
    plugin: CredentialPlugin,
) -> None:
    """Verify non-OIDC plugins default to an empty plugin_description."""
    assert plugin.plugin_description == ''


def test_credential_plugin_description_default() -> None:
    """Verify CredentialPlugin defaults plugin_description to empty string."""
    plugin = CredentialPlugin(
        name='test',
        inputs={'fields': [], 'metadata': [], 'required': []},
        backend=None,
    )
    assert plugin.plugin_description == ''
