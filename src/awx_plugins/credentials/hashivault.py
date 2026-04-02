# FIXME: the following violations must be addressed gradually and unignored
# mypy: disable-error-code="arg-type, no-untyped-call, no-untyped-def"

import contextlib as _ctx
import contextvars as _ctx_vars
import functools as _functools
import os
import pathlib
import time
import typing as _t
from collections import abc as _abc
from urllib.parse import urljoin

from awx_plugins.interfaces._temporary_private_django_api import (  # noqa: WPS436
    gettext_noop as _,
)

import requests

from . import _types
from .plugin import CertFiles, CredentialPlugin, raise_for_status


_AUTH_TOKEN: _ctx_vars.ContextVar[str] = _ctx_vars.ContextVar('_AUTH_TOKEN')
"""Authentication token for use in plugin handlers."""


class _EmptyKwargs(_t.TypedDict):
    """Schema for zero keyword arguments."""


# Base input fields
url_field: _types.FieldDict = {
    'id': 'url',
    'label': _('Server URL'),
    'type': 'string',
    'format': 'url',
    'help_text': _('The URL to the HashiCorp Vault'),
}

token_field: _types.FieldDict = {
    'id': 'token',
    'label': _('Token'),
    'type': 'string',
    'secret': True,
    'help_text': _(
        'The access token used to authenticate to the Vault server',
    ),
}

cacert_field: _types.FieldDict = {
    'id': 'cacert',
    'label': _('CA Certificate'),
    'type': 'string',
    'multiline': True,
    'help_text': _(
        'The CA certificate used to verify the SSL certificate of '
        'the Vault server',
    ),
}

role_id_field: _types.FieldDict = {
    'id': 'role_id',
    'label': _('AppRole role_id'),
    'type': 'string',
    'multiline': False,
    'help_text': _('The Role ID for AppRole Authentication'),
}

secret_id_field: _types.FieldDict = {
    'id': 'secret_id',
    'label': _('AppRole secret_id'),
    'type': 'string',
    'multiline': False,
    'secret': True,
    'help_text': _('The Secret ID for AppRole Authentication'),
}

client_cert_public_field: _types.FieldDict = {
    'id': 'client_cert_public',
    'label': _('Client Certificate'),
    'type': 'string',
    'multiline': True,
    'help_text': _(
        'The PEM-encoded client certificate used for TLS client '
        'authentication. This should include the certificate and any '
        'intermediate certificates.',
    ),
}

client_cert_private_field: _types.FieldDict = {
    'id': 'client_cert_private',
    'label': _('Client Certificate Key'),
    'type': 'string',
    'multiline': True,
    'secret': True,
    'help_text': _(
        'The certificate private key used for TLS client authentication.',
    ),
}

client_cert_role_field: _types.FieldDict = {
    'id': 'client_cert_role',
    'label': _('TLS Authentication Role'),
    'type': 'string',
    'multiline': False,
    'help_text': _(
        'The role configured in Hashicorp Vault for TLS client '
        'authentication. If not provided, Hashicorp Vault may assign '
        'roles based on the certificate used.',
    ),
}

namespace_field: _types.FieldDict = {
    'id': 'namespace',
    'label': _('Namespace name (Vault Enterprise only)'),
    'type': 'string',
    'multiline': False,
    'help_text': _(
        'Name of the namespace to use when authenticate and retrieve secrets',
    ),
}

kubernetes_role_field: _types.FieldDict = {
    'id': 'kubernetes_role',
    'label': _('Kubernetes role'),
    'type': 'string',
    'multiline': False,
    'help_text': _(
        'The Role for Kubernetes Authentication. This is the named '
        'role, configured in Vault server, for AWX pod auth policies. '
        'see https://www.vaultproject.io/docs/auth/kubernetes'
        '#configuration',
    ),
}

username_field: _types.FieldDict = {
    'id': 'username',
    'label': _('Username'),
    'type': 'string',
    'secret': False,
    'help_text': _('Username for user authentication.'),
}

password_field: _types.FieldDict = {
    'id': 'password',
    'label': _('Password'),
    'type': 'string',
    'secret': True,
    'help_text': _('Password for user authentication.'),
}

default_auth_path_field: _types.FieldDict = {
    'id': 'default_auth_path',
    'label': _('Path to Auth'),
    'type': 'string',
    'multiline': False,
    'default': 'approle',
    'help_text': _(
        "The Authentication path to use if one isn't provided in the "
        'metadata when linking to an input field. '
        "Defaults to 'approle'",
    ),
}

# OIDC-specific fields
jwt_auth_path_field: _types.FieldDict = {
    'id': 'default_auth_path',
    'label': _('Path to Auth'),
    'type': 'string',
    'multiline': False,
    'default': 'jwt',
    'help_text': _(
        'The path where the JWT authentication method is mounted. '
        "Defaults to 'jwt'.",
    ),
}

jwt_auth_path_metadata: _types.MetadataDict = {
    'id': 'default_auth_path',
    'label': _('Path to Auth'),
    'type': 'string',
    'multiline': False,
    'help_text': _(
        'The path where the JWT authentication method is mounted e.g, jwt',
    ),
}

jwt_role_field: _types.FieldDict = {
    'id': 'jwt_role',
    'label': _('JWT Role'),
    'type': 'string',
    'multiline': False,
    'help_text': _(
        'The name of the Vault role configured for JWT authentication. '
        'This role defines what policies and secrets the authenticated '
        'job can access. Example: controller-automation, aap-production-jobs. '
        'This must match a role created in Vault at auth/jwt/role/<role-name>.',
    ),
}

jwt_audience_field: _types.FieldDict = {
    'id': 'jwt_aud',
    'label': _('JWT Audience'),
    'type': 'string',
    'multiline': False,
    'help_text': _(
        'Identifies this Vault instance as the intended recipient of JWTs. '
        'This value must match the bound_audiences configuration in your '
        'Vault JWT auth method. Examples: hashicorp-vault-prod-01, '
        'https://vault.example.com, or vault-production.',
    ),
}

workload_identity_token_field: _types.FieldDict = {
    'id': 'workload_identity_token',
    'label': _('Workload Identity Token'),
    'type': 'string',
    'secret': True,
    'internal': True,
    'help_text': _(
        'JWT token for workload identity authentication. '
        'Automatically populated by the system.',
    ),
}

# Base metadata fields
secret_path_metadata: _types.MetadataDict = {
    'id': 'secret_path',
    'label': _('Path to Secret'),
    'type': 'string',
    'help_text': _(
        (
            'The path to the secret stored in the secret backend e.g, '
            '/some/secret/. It is recommended that you use the secret '
            'backend field to identify the storage backend and to use '
            'this field for locating a specific secret within that '
            'store. However, if you prefer to fully identify both the '
            'secret backend and one of its secrets using only this '
            'field, join their locations into a single path without '
            'any additional separators, '
            'e.g, /location/of/backend/some/secret.'
        ),
    ),
}

auth_path_metadata: _types.MetadataDict = {
    'id': 'auth_path',
    'label': _('Path to Auth'),
    'type': 'string',
    'multiline': False,
    'help_text': _(
        'The path where the Authentication method is mounted e.g, approle',
    ),
}

# KV-specific fields and metadata
api_version_field: _types.FieldDict = {
    'id': 'api_version',
    'label': _('API Version'),
    'type': 'string',
    'choices': ['v1', 'v2'],
    'help_text': _(
        'API v1 is for static key/value lookups.  API v2 is for versioned '
        'key/value lookups.',
    ),
    'default': 'v1',
}

secret_backend_metadata: _types.MetadataDict = {
    'id': 'secret_backend',
    'label': _('Name of Secret Backend'),
    'type': 'string',
    'help_text': _(
        'The name of the kv secret backend (if left empty, the first '
        'segment of the secret path will be used).',
    ),
}

secret_key_metadata: _types.MetadataDict = {
    'id': 'secret_key',
    'label': _('Key Name'),
    'type': 'string',
    'help_text': _('The name of the key to look up in the secret.'),
}

secret_version_metadata: _types.MetadataDict = {
    'id': 'secret_version',
    'label': _('Secret Version (v2 only)'),
    'type': 'string',
    'help_text': _(
        'Used to specify a specific secret version (if left empty, '
        'the latest version will be used).',
    ),
}

# SSH-specific metadata
public_key_metadata: _types.MetadataDict = {
    'id': 'public_key',
    'label': _('Unsigned Public Key'),
    'type': 'string',
    'multiline': True,
}

role_metadata: _types.MetadataDict = {
    'id': 'role',
    'label': _('Role Name'),
    'type': 'string',
    'help_text': _('The name of the role used to sign.'),
}

valid_principals_metadata: _types.MetadataDict = {
    'id': 'valid_principals',
    'label': _('Valid Principals'),
    'type': 'string',
    'help_text': _(
        'Valid principals (either usernames or hostnames) that the '
        'certificate should be signed for.',
    ),
}


hashi_kv_inputs: _types.PluginInputs = {
    'fields': [
        url_field,
        token_field,
        cacert_field,
        role_id_field,
        secret_id_field,
        client_cert_public_field,
        client_cert_private_field,
        client_cert_role_field,
        namespace_field,
        kubernetes_role_field,
        username_field,
        password_field,
        default_auth_path_field,
        api_version_field,
    ],
    'metadata': [
        secret_backend_metadata,
        secret_path_metadata,
        auth_path_metadata,
        secret_key_metadata,
        secret_version_metadata,
    ],
    'required': [
        url_field['id'],
        secret_path_metadata['id'],
        api_version_field['id'],
        secret_key_metadata['id'],
    ],
}

hashi_kv_oidc_inputs: _types.PluginInputs = {
    'fields': [
        url_field,
        api_version_field,
        cacert_field,
        jwt_auth_path_field,
        jwt_role_field,
        jwt_audience_field,
        namespace_field,
        workload_identity_token_field,
    ],
    'metadata': [
        secret_backend_metadata,
        secret_path_metadata,
        jwt_auth_path_metadata,
        secret_key_metadata,
        secret_version_metadata,
    ],
    'required': [
        url_field['id'],
        api_version_field['id'],
        jwt_auth_path_field['id'],
        jwt_role_field['id'],
        jwt_audience_field['id'],
        secret_path_metadata['id'],
        secret_key_metadata['id'],
    ],
}

hashi_ssh_inputs: _types.PluginInputs = {
    'fields': [
        url_field,
        token_field,
        cacert_field,
        role_id_field,
        secret_id_field,
        client_cert_public_field,
        client_cert_private_field,
        client_cert_role_field,
        namespace_field,
        kubernetes_role_field,
        username_field,
        password_field,
        default_auth_path_field,
    ],
    'metadata': [
        public_key_metadata,
        secret_path_metadata,
        auth_path_metadata,
        role_metadata,
        valid_principals_metadata,
    ],
    'required': [
        url_field['id'],
        secret_path_metadata['id'],
        public_key_metadata['id'],
        role_metadata['id'],
    ],
}

hashi_ssh_oidc_inputs: _types.PluginInputs = {
    'fields': [
        url_field,
        cacert_field,
        jwt_auth_path_field,
        jwt_role_field,
        jwt_audience_field,
        namespace_field,
        workload_identity_token_field,
    ],
    'metadata': [
        public_key_metadata,
        secret_path_metadata,
        jwt_auth_path_metadata,
        role_metadata,
        valid_principals_metadata,
    ],
    'required': [
        url_field['id'],
        jwt_auth_path_field['id'],
        jwt_role_field['id'],
        jwt_audience_field['id'],
        secret_path_metadata['id'],
        public_key_metadata['id'],
        role_metadata['id'],
    ],
}


def handle_auth(**kwargs):
    token = None
    if kwargs.get('token'):
        token = kwargs['token']
    elif kwargs.get('username') and kwargs.get('password'):
        token = method_auth(**kwargs, auth_param=userpass_auth(**kwargs))
    elif kwargs.get('role_id') and kwargs.get('secret_id'):
        token = method_auth(**kwargs, auth_param=approle_auth(**kwargs))
    elif kwargs.get('kubernetes_role'):
        token = method_auth(**kwargs, auth_param=kubernetes_auth(**kwargs))
    elif kwargs.get('client_cert_public') and kwargs.get(
        'client_cert_private',
    ):
        token = method_auth(**kwargs, auth_param=client_cert_auth(**kwargs))
    elif kwargs.get('workload_identity_token'):
        token = method_auth(
            **kwargs,
            auth_param=workload_identity_auth(**kwargs),
        )
    else:
        raise Exception(
            'Token, Username/Password, AppRole, Kubernetes, or TLS authentication parameters must be set',
        )
    return token


def userpass_auth(**kwargs):
    return {'username': kwargs['username'], 'password': kwargs['password']}


def approle_auth(**kwargs):
    return {'role_id': kwargs['role_id'], 'secret_id': kwargs['secret_id']}


def kubernetes_auth(**kwargs):
    jwt_file = pathlib.Path(
        '/var/run/secrets/kubernetes.io/serviceaccount/token',
    )
    with jwt_file.open('r') as jwt_fo:
        jwt = jwt_fo.read().rstrip()
    return {'role': kwargs['kubernetes_role'], 'jwt': jwt}


def client_cert_auth(**kwargs):
    return {'name': kwargs.get('client_cert_role')}


def workload_identity_auth(**kwargs):
    """JWT representing a workload. Issued by an OIDC entity trusted by Vault."""
    workload_identity_token = kwargs.get('workload_identity_token')
    return {'role': kwargs.get('jwt_role'), 'jwt': workload_identity_token}


def _revoke_self_token(
    *,
    vault_token: str,
    url: str,
    namespace: str,
    cacert: str | None = None,
) -> None:
    """Revoke the passed-in Vault token."""
    url = urljoin(url, 'v1/auth/token/revoke-self')
    sess = requests.Session()
    sess.headers['X-Vault-Token'] = vault_token
    if namespace != '':
        sess.headers['X-Vault-Namespace'] = namespace
    with CertFiles(cacert) as cert:
        resp = sess.post(url, verify=cert, timeout=30)
    resp.raise_for_status()


@_ctx.contextmanager
def _vault_token(**kwargs: str) -> _abc.Iterator[str]:
    """Context manager that yields a Vault token and revokes it on exit if obtained via workload identity."""
    is_oidc_context = 'workload_identity_token' in kwargs
    token = handle_auth(**kwargs)
    try:
        yield token
    finally:
        # Only revoke tokens obtained via OIDC authentication
        if is_oidc_context:
            _revoke_self_token(
                vault_token=token,
                url=kwargs['url'],
                namespace=kwargs.get('namespace', ''),
                cacert=kwargs.get('cacert'),
            )


@_ctx.contextmanager
def _token_in_context(token: str, /) -> _abc.Iterator[None]:
    """Set a token for the execution context lifetime."""
    var_ctx_token = _AUTH_TOKEN.set(token)
    try:
        yield
    finally:
        _AUTH_TOKEN.reset(var_ctx_token)


# Param Spec to represent decorated function parameters
_PT = _t.ParamSpec(  # FIXME: Use [_RT, **_PT] in the signature in Python 3.12
    '_PT',
)
# TypeVar to represent decorated function return type
_RT = _t.TypeVar('_RT')


def _inject_auth_token_with_revocation(
    decorated_function: _t.Callable[_PT, _RT],
    /,
) -> _t.Callable[_PT, _RT]:
    @_functools.wraps(decorated_function)
    def _decorate_the_function_with_revocation(  # noqa: WPS430 -- in-decorator
        *args: _PT.args,
        **kwargs: _PT.kwargs,
    ) -> _RT:
        with _vault_token(**kwargs) as token:
            with _token_in_context(token):
                return decorated_function(*args, **kwargs)

    return _decorate_the_function_with_revocation


def method_auth(**kwargs):
    # get auth method specific params
    request_kwargs = {'json': kwargs['auth_param'], 'timeout': 30}

    # we first try to use the 'auth_path' from the metadata
    # if not found we try to fetch the 'default_auth_path' from inputs
    auth_path = kwargs.get('auth_path') or kwargs['default_auth_path']

    url = urljoin(kwargs['url'], 'v1')
    cacert = kwargs.get('cacert')

    sess = requests.Session()
    sess.mount(url, requests.adapters.HTTPAdapter(max_retries=5))

    # Namespace support
    if kwargs.get('namespace'):
        sess.headers['X-Vault-Namespace'] = kwargs['namespace']
    request_url = '/'.join([url, 'auth', auth_path, 'login']).rstrip('/')
    if kwargs['auth_param'].get('username'):
        request_url = request_url + '/' + (kwargs['username'])
    with CertFiles(cacert) as cert:
        request_kwargs['verify'] = cert
        # TLS client certificate support
        if kwargs.get('client_cert_public') and kwargs.get(
            'client_cert_private',
        ):
            # Add client cert to requests Session before making call
            with CertFiles(
                kwargs['client_cert_public'],
                key=kwargs['client_cert_private'],
            ) as client_cert:
                sess.cert = client_cert
                resp = sess.post(request_url, **request_kwargs)
        else:
            # Make call without client certificate
            resp = sess.post(request_url, **request_kwargs)
    resp.raise_for_status()
    token = resp.json()['auth']['client_token']
    return token


@_inject_auth_token_with_revocation
# NOTE: The "too many args" rules of flake8 and pylint are disabled due to such
# NOTE: many arguments being a common public plugin API at the moment.
# pylint: disable-next=too-many-arguments
def kv_backend(  # noqa: WPS211 -- the same as too-many-arguments
    *,
    url: str,
    api_version: str,
    secret_path: str,
    secret_key: str | None = None,
    secret_backend: str | None = None,
    secret_version: str | None = None,
    cacert: str | None = None,
    namespace: str | None = None,
    **_discarded_kwargs: _t.Unpack[_EmptyKwargs],
) -> str:
    request_kwargs = {
        'timeout': 30,
        'allow_redirects': False,
    }

    sess = requests.Session()
    sess.mount(url, requests.adapters.HTTPAdapter(max_retries=5))
    sess.headers['Authorization'] = f'Bearer {_AUTH_TOKEN.get()}'
    # Compatibility header for older installs of Hashicorp Vault
    sess.headers['X-Vault-Token'] = _AUTH_TOKEN.get()
    if namespace:
        sess.headers['X-Vault-Namespace'] = namespace

    if api_version == 'v2':
        if secret_version:
            request_kwargs['params'] = {  # type: ignore[assignment]  # FIXME
                'version': secret_version,
            }
        if secret_backend:
            path_segments = [secret_backend, 'data', secret_path]
        else:
            try:
                mount_point, *path = pathlib.Path(
                    secret_path.lstrip(os.sep),
                ).parts
            except Exception:
                mount_point, path = secret_path, []
            # https://www.vaultproject.io/api/secret/kv/kv-v2.html#read-secret-version
            path_segments = [mount_point, 'data'] + path
    elif secret_backend:
        path_segments = [secret_backend, secret_path]
    else:
        path_segments = [secret_path]

    request_url = urljoin(url, '/'.join(['v1'] + path_segments)).rstrip('/')
    with CertFiles(cacert) as cert:
        request_kwargs['verify'] = cert
        request_retries = 0
        while request_retries < 5:
            response = sess.get(request_url, **request_kwargs)
            # https://developer.hashicorp.com/vault/docs/enterprise/consistency
            if response.status_code == 412:
                request_retries += 1
                time.sleep(1)
            else:
                break
    raise_for_status(response)

    json = response.json()
    if api_version == 'v2':
        json = json['data']

    if secret_key:
        try:
            if (
                (secret_key != 'data')
                and (  # noqa: S105; not a password
                    secret_key not in json['data']
                )
                and ('data' in json['data'])
            ):
                return str(json['data']['data'][secret_key])
            return str(json['data'][secret_key])
        except KeyError:
            raise RuntimeError(
                f'{secret_key} is not present at {secret_path}',
            )
    return str(json['data'])


@_inject_auth_token_with_revocation
# NOTE: The "too many args" rules of flake8 and pylint are disabled due to such
# NOTE: many arguments being a common public plugin API at the moment.
# pylint: disable-next=too-many-arguments
def ssh_backend(  # noqa: WPS211 -- the same as too-many-arguments
    *,
    url: str,
    secret_path: str,
    role: str,
    public_key: str,
    cacert: str | None = None,
    namespace: str | None = None,
    valid_principals: str | None = None,
    **_discarded_kwargs: _t.Unpack[_EmptyKwargs],
) -> str:
    url = urljoin(url, 'v1')

    request_kwargs = {
        'timeout': 30,
        'allow_redirects': False,
        'json': {
            'public_key': public_key,
        },
    }
    if valid_principals:
        request_kwargs['json'][  # type: ignore[index]  # FIXME
            'valid_principals'
        ] = valid_principals

    sess = requests.Session()
    sess.mount(url, requests.adapters.HTTPAdapter(max_retries=5))
    sess.headers['Authorization'] = f'Bearer {_AUTH_TOKEN.get()}'
    if namespace:
        sess.headers['X-Vault-Namespace'] = namespace
    # Compatibility header for older installs of Hashicorp Vault
    sess.headers['X-Vault-Token'] = _AUTH_TOKEN.get()
    # https://www.vaultproject.io/api/secret/ssh/index.html#sign-ssh-key
    request_url = '/'.join([url, secret_path, 'sign', role]).rstrip('/')

    with CertFiles(cacert) as cert:
        request_kwargs['verify'] = cert
        request_retries = 0
        while request_retries < 5:
            resp = sess.post(request_url, **request_kwargs)
            # https://developer.hashicorp.com/vault/docs/enterprise/consistency
            if resp.status_code == 412:
                request_retries += 1
                time.sleep(1)
            else:
                break
    raise_for_status(resp)
    return str(resp.json()['data']['signed_key'])


hashivault_kv_plugin = CredentialPlugin(
    'HashiCorp Vault Secret Lookup',
    inputs=hashi_kv_inputs,
    backend=kv_backend,
)

hashivault_ssh_plugin = CredentialPlugin(
    'HashiCorp Vault Signed SSH',
    inputs=hashi_ssh_inputs,
    backend=ssh_backend,
)

hashivault_kv_oidc_plugin = CredentialPlugin(
    'HashiCorp Vault Secret Lookup (OIDC)',
    inputs=hashi_kv_oidc_inputs,
    backend=kv_backend,
    plugin_description='Uses OIDC/JWT authentication for enhanced security with short-lived tokens',
)

hashivault_ssh_oidc_plugin = CredentialPlugin(
    'HashiCorp Vault Signed SSH (OIDC)',
    inputs=hashi_ssh_oidc_inputs,
    backend=ssh_backend,
    plugin_description='Uses OIDC/JWT authentication for enhanced security with short-lived tokens',
)
