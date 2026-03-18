"""Akeyless credential plugins for AWX."""
# WPS202 is expected: implementing two credential plugins requires Protocol
# types, TypedDicts, and multiple helper functions per plugin, which exceeds
# the default module-member threshold.

import json as _json
import typing as _t
from collections.abc import Mapping as _Mapping

from awx_plugins.interfaces._temporary_private_django_api import (  # noqa: WPS436
    gettext_noop as _,
)

# The akeyless SDK does not ship type stubs; pylint cannot resolve its imports.
# When not installed, pylint misidentifies `from akeyless import` as a
# self-import because this file is named akeyless.py (import-self).
# pylint: disable=import-error,import-self,no-name-in-module
from akeyless import (
    ApiClient as _ApiClient,
    Auth as _Auth,
    Configuration as _Configuration,
    DescribeItem as _DescribeItem,
    GetSecretValue as _GetSecretValue,
    V2Api as _V2Api,
)
from akeyless.models.get_ssh_certificate import (
    GetSSHCertificate as _GetSSHCertificate,
)
from akeyless.rest import ApiException as _ApiException

# pylint: enable=import-error,import-self,no-name-in-module
from . import plugin as _plugin


__all__ = (  # noqa: WPS410
    'akeyless_backend',
    'akeyless_plugin',
    'akeyless_ssh_backend',
    'akeyless_ssh_plugin',
)


_SUPPORTED_ITEM_TYPES = frozenset(('STATIC_SECRET',))

_STRUCTURED_SECRET_FORMATS = frozenset(('json', 'key-value'))

_PASSWORD_KEYS = frozenset(('username', 'password'))


class _AkeylessCommonKwargs(_t.TypedDict):
    gateway_url: str
    access_id: str
    access_key: str
    ca_cert: _t.NotRequired[str | None]


class _AkeylessBackendKwargs(_AkeylessCommonKwargs):
    secret_path: str
    secret_key: _t.NotRequired[str | None]


class _AkeylessSshBackendKwargs(_AkeylessCommonKwargs):
    cert_issue_name: str
    cert_username: str
    public_key_data: str
    ttl: _t.NotRequired[int | str | None]


class _AuthResponse(_t.Protocol):
    token: str | None


class _StaticSecretInfo(_t.Protocol):
    format: str


class _ItemGeneralInfo(_t.Protocol):
    static_secret_info: _StaticSecretInfo


class _DescribeItemResponse(_t.Protocol):
    item_type: str
    item_sub_type: str
    item_general_info: _ItemGeneralInfo


class _SshCertResponse(_t.Protocol):
    data: str | None  # noqa: WPS110  # must match the akeyless SDK response attribute name


class _AkeylessApi(_t.Protocol):
    def auth(self: _t.Self, auth: _Auth) -> _AuthResponse: ...

    def describe_item(
        self: _t.Self,
        req: _DescribeItem,
    ) -> _DescribeItemResponse: ...

    def get_secret_value(
        self: _t.Self,
        req: _GetSecretValue,
    ) -> _Mapping[str, str]: ...

    def get_ssh_certificate(
        self: _t.Self,
        req: _GetSSHCertificate,
    ) -> _SshCertResponse: ...


_common_plugin_inputs = [
    {
        'id': 'gateway_url',
        'label': _('Gateway URL'),
        'type': 'string',
        'help_text': _(
            'The URL of your Akeyless Gateway (e.g., https://api.akeyless.io, '
            'https://my.akeyless.gw/api/v2)',
        ),
        'default': 'https://api.akeyless.io',
    },
    {
        'id': 'access_id',
        'label': _('Access ID'),
        'type': 'string',
        'help_text': _('Your Akeyless API Access ID'),
    },
    {
        'id': 'access_key',
        'label': _('Access Key'),
        'type': 'string',
        'help_text': _('Your Akeyless API Access Key'),
        'secret': True,
    },
    {
        'id': 'ca_cert',
        'label': _('CA Certificate'),
        'type': 'string',
        'multiline': True,
        'help_text': _(
            'CA certificate (PEM format) used to verify the gateway TLS '
            'certificate.',
        ),
    },
]


_akeyless_inputs = {
    'fields': _common_plugin_inputs,
    'metadata': [
        {
            'id': 'secret_path',
            'label': _('Secret Path'),
            'type': 'string',
            'help_text': _(
                'The path to the secret in Akeyless (e.g., '
                '/myapp/database/password).',
            ),
        },
        {
            'id': 'secret_key',
            'label': _('Secret Key'),
            'type': 'string',
            'help_text': _(
                'Optional key within the secret to retrieve (for JSON or '
                'key-value secrets).',
            ),
        },
    ],
    'required': [
        'gateway_url',
        'access_id',
        'access_key',
        'secret_path',
    ],
}


_akeyless_ssh_inputs = {
    'fields': _common_plugin_inputs,
    'metadata': [
        {
            'id': 'cert_issue_name',
            'label': _('Certificate Issuer Name'),
            'type': 'string',
            'help_text': _(
                'The full path to the certificate issuer in Akeyless (e.g., '
                '/remote/ssh/certificate/issuer).',
            ),
        },
        {
            'id': 'cert_username',
            'label': _('Certificate Username'),
            'type': 'string',
            'help_text': _(
                'The username(s) to sign into the SSH certificate in a '
                'comma-separated list, e.g., "ubuntu,nobody,nonroot".',
            ),
        },
        {
            'id': 'public_key_data',
            'label': _('Public Key Data'),
            'type': 'string',
            'help_text': _(
                'The public key data to sign (e.g. "ssh-rsa AAAAB3NzaC1yc2E...").',
            ),
        },
        {
            'id': 'ttl',
            'label': _('TTL'),
            'type': 'number',
            'help_text': _(
                'Time to live in seconds for the SSH certificate. If not '
                'defined, the default issuer TTL is used.',
            ),
        },
    ],
    'required': [
        'gateway_url',
        'access_id',
        'access_key',
        'cert_issue_name',
        'cert_username',
        'public_key_data',
    ],
}


def _setup_client(gateway_url: str, ca_cert_path: str | None) -> _AkeylessApi:
    client_configuration = _Configuration(host=gateway_url)
    if ca_cert_path:
        client_configuration.ssl_ca_cert = ca_cert_path
        client_configuration.verify_ssl = True
    api_client = _ApiClient(client_configuration)
    api_client.user_agent = 'AWX'
    api_client.default_headers['akeylessclienttype'] = 'AWX'
    return _V2Api(api_client)


def _authenticate(
    api_instance: _AkeylessApi,
    access_id: str,
    access_key: str,
) -> str:
    auth_response = api_instance.auth(
        _Auth(
            access_id=access_id,
            access_key=access_key,
        ),
    )
    if not auth_response.token:
        raise ValueError(
            'Failed to authenticate with Akeyless: no token received.',
        )
    return auth_response.token


def _extract_password_secret(secret_data: str, secret_key: str | None) -> str:
    if not secret_key:
        return secret_data
    if secret_key not in _PASSWORD_KEYS:
        raise NotImplementedError(
            'Password secrets only support "username" or "password" keys.',
        )
    secret_dict = _t.cast('dict[str, str]', _json.loads(secret_data))
    return secret_dict[secret_key]


def _extract_text_secret(
    secret_data: str,
    secret_key: str | None,
    static_secret_sub_type: str,
) -> str:
    if static_secret_sub_type == 'password':
        return _extract_password_secret(secret_data, secret_key)
    if static_secret_sub_type == 'generic':
        return secret_data
    raise NotImplementedError(
        'Static secret sub type must be "password" or "generic".',
    )


def _extract_structured_secret(
    secret_data: str,
    secret_key: str | None,
    secret_path: str,
) -> str:
    if not secret_key:
        return str(secret_data)
    secret_dict = _t.cast('dict[str, str]', _json.loads(secret_data))
    try:
        return secret_dict[secret_key]
    except KeyError as exc:
        raise KeyError(
            f'Key "{secret_key}" not found in secret at path: {secret_path}',
        ) from exc


def _extract_secret_value(
    secret_response: _Mapping[str, str],
    secret_path: str,
    secret_key: str | None,
    static_secret_format: str,
    static_secret_sub_type: str,
) -> str:
    secret_data = secret_response[secret_path]
    if static_secret_format == 'text':
        return _extract_text_secret(
            secret_data,
            secret_key,
            static_secret_sub_type,
        )
    if static_secret_format in _STRUCTURED_SECRET_FORMATS:
        return _extract_structured_secret(
            secret_data,
            secret_key,
            secret_path,
        )
    raise NotImplementedError(
        'Static secret format must be "text", "json", or "key-value".',
    )


def _ensure_supported_item_type(secret_path: str, item_type: str) -> None:
    if item_type not in _SUPPORTED_ITEM_TYPES:
        raise NotImplementedError(
            f'Secret "{secret_path}" is of type "{item_type}". '
            f'Supported types: {sorted(_SUPPORTED_ITEM_TYPES)}.',
        )


def _fetch_secret_value(
    api_instance: _AkeylessApi,
    token: str,
    secret_path: str,
    secret_key: str | None,
) -> str:
    describe_item_request = _DescribeItem(name=secret_path, token=token)
    describe_item_response = api_instance.describe_item(describe_item_request)
    _ensure_supported_item_type(secret_path, describe_item_response.item_type)

    static_secret_format = (
        describe_item_response.item_general_info.static_secret_info.format
    )
    static_secret_sub_type = describe_item_response.item_sub_type

    secret_response = api_instance.get_secret_value(
        _GetSecretValue(
            names=[secret_path],
            token=token,
        ),
    )

    return _extract_secret_value(
        secret_response,
        secret_path,
        secret_key,
        static_secret_format,
        static_secret_sub_type,
    )


def akeyless_backend(**kwargs: _t.Unpack[_AkeylessBackendKwargs]) -> str:
    """Retrieve a secret value from Akeyless."""
    with _plugin.CertFiles(kwargs.get('ca_cert')) as ca_cert_path:
        api_instance = _setup_client(
            kwargs['gateway_url'].rstrip('/'),
            ca_cert_path,
        )
        try:
            token = _authenticate(
                api_instance,
                kwargs['access_id'],
                kwargs['access_key'],
            )
        except ValueError as val_err:
            raise RuntimeError(str(val_err)) from val_err
        try:
            return _fetch_secret_value(
                api_instance,
                token,
                kwargs['secret_path'],
                kwargs.get('secret_key'),
            )
        except _ApiException as api_exc:
            raise RuntimeError(
                f'Akeyless API error: {api_exc.reason}'
                f' (Status: {api_exc.status})',
            ) from api_exc


def _coerce_ttl(ttl_value: int | str | None) -> int | None:
    if ttl_value is None or ttl_value == '':
        return None
    try:
        return int(ttl_value)
    except (TypeError, ValueError) as exc:
        raise ValueError('TTL must be an integer number of seconds.') from exc


def _fetch_ssh_certificate(
    api_instance: _AkeylessApi,
    token: str,
    ssh_inputs: _AkeylessSshBackendKwargs,
) -> str:
    response = api_instance.get_ssh_certificate(
        _GetSSHCertificate(
            token=token,
            cert_issuer_name=ssh_inputs['cert_issue_name'],
            cert_username=ssh_inputs['cert_username'],
            ttl=_coerce_ttl(ssh_inputs.get('ttl')),
            public_key_data=ssh_inputs['public_key_data'],
        ),
    )
    if not response.data:
        raise ValueError(
            'Failed to generate signed SSH certificate: no data returned.',
        )
    return response.data


def akeyless_ssh_backend(
    **kwargs: _t.Unpack[_AkeylessSshBackendKwargs],
) -> str:
    """Generate a signed SSH certificate using Akeyless."""
    with _plugin.CertFiles(kwargs.get('ca_cert')) as ca_cert_path:
        api_instance = _setup_client(
            kwargs['gateway_url'].rstrip('/'),
            ca_cert_path,
        )
        try:
            token = _authenticate(
                api_instance,
                kwargs['access_id'],
                kwargs['access_key'],
            )
        except ValueError as val_err:
            raise RuntimeError(str(val_err)) from val_err
        try:
            return _fetch_ssh_certificate(
                api_instance,
                token,
                kwargs,
            )
        except _ApiException as api_exc:
            raise RuntimeError(
                f'Akeyless API error: {api_exc.reason}'
                f' (Status: {api_exc.status})',
            ) from api_exc
        except ValueError as val_err:
            raise RuntimeError(str(val_err)) from val_err


akeyless_plugin = _plugin.CredentialPlugin(
    'Akeyless',
    inputs=_akeyless_inputs,  # type: ignore[arg-type]
    backend=akeyless_backend,
)


akeyless_ssh_plugin = _plugin.CredentialPlugin(
    'Akeyless SSH',
    inputs=_akeyless_ssh_inputs,  # type: ignore[arg-type]
    backend=akeyless_ssh_backend,
)
