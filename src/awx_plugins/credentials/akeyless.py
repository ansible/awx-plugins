"""Akeyless credential plugins for AWX."""  # noqa: WPS202
# pylint: disable=import-error, import-self, no-name-in-module
# FIXME: the following violations must be addressed gradually and unignored
# mypy: disable-error-code="import-not-found, import-untyped, no-untyped-def"

import json
from collections.abc import Mapping
from typing import NotRequired, TypedDict, Unpack, cast

from awx_plugins.interfaces._temporary_private_django_api import (  # noqa: WPS436
    gettext_noop as _,
)

from akeyless import (
    ApiClient,
    Auth,
    Configuration,
    DescribeItem,
    GetSecretValue,
    V2Api,
)
from akeyless.models.get_ssh_certificate import GetSSHCertificate
from akeyless.rest import ApiException

from .plugin import CertFiles, CredentialPlugin


SUPPORTED_ITEM_TYPES = frozenset(('STATIC_SECRET',))

STRUCTURED_SECRET_FORMATS = frozenset(('json', 'key-value'))
PASSWORD_KEYS = frozenset(('username', 'password'))


class _AkeylessCommonKwargs(TypedDict):
    gateway_url: str
    access_id: str
    access_key: str
    ca_cert: NotRequired[str | None]


class _AkeylessBackendKwargs(_AkeylessCommonKwargs):
    secret_path: str
    secret_key: NotRequired[str | None]


class _AkeylessSshBackendKwargs(_AkeylessCommonKwargs):
    cert_issue_name: str
    cert_username: str
    public_key_data: str
    ttl: NotRequired[int | str | None]


common_plugin_inputs = [
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


akeyless_inputs = {
    'fields': common_plugin_inputs,
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


akeyless_ssh_inputs = {
    'fields': common_plugin_inputs,
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


def _setup_client(gateway_url: str, ca_cert_path: str | None) -> V2Api:
    client_configuration = Configuration(host=gateway_url)
    if ca_cert_path:
        client_configuration.ssl_ca_cert = ca_cert_path
        client_configuration.verify_ssl = True
    api_client = ApiClient(client_configuration)
    api_client.user_agent = 'AWX'
    api_client.default_headers['akeylessclienttype'] = 'AWX'
    return V2Api(api_client)


def _authenticate(api_instance: V2Api, access_id: str, access_key: str) -> str:
    auth_response = api_instance.auth(
        Auth(
            access_id=access_id,
            access_key=access_key,
        ),
    )
    if not auth_response.token:
        raise RuntimeError(
            'Failed to authenticate with Akeyless: no token received.',
        )
    return auth_response.token


def _extract_password_secret(secret_data: str, secret_key: str | None) -> str:
    if not secret_key:
        return secret_data
    if secret_key not in PASSWORD_KEYS:
        raise NotImplementedError(
            'Password secrets only support "username" or "password" keys.',
        )
    secret_dict = cast('dict[str, str]', json.loads(secret_data))
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
    secret_dict = cast('dict[str, str]', json.loads(secret_data))
    try:
        return secret_dict[secret_key]
    except KeyError as exc:
        raise KeyError(
            f'Key "{secret_key}" not found in secret at path: {secret_path}',
        ) from exc


def _extract_secret_value(
    secret_response: Mapping[str, str],
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
    if static_secret_format in STRUCTURED_SECRET_FORMATS:
        return _extract_structured_secret(
            secret_data,
            secret_key,
            secret_path,
        )
    raise NotImplementedError(
        'Static secret format must be "text", "json", or "key-value".',
    )


def _ensure_supported_item_type(secret_path: str, item_type: str) -> None:
    if item_type not in SUPPORTED_ITEM_TYPES:
        raise NotImplementedError(
            f'Secret "{secret_path}" is of type "{item_type}". '
            f'Supported types: {sorted(SUPPORTED_ITEM_TYPES)}.',
        )


def _fetch_secret_value(
    api_instance: V2Api,
    token: str,
    secret_path: str,
    secret_key: str | None,
) -> str:
    describe_item_request = DescribeItem(name=secret_path, token=token)
    describe_item_response = api_instance.describe_item(describe_item_request)
    _ensure_supported_item_type(secret_path, describe_item_response.item_type)

    static_secret_format = (
        describe_item_response.item_general_info.static_secret_info.format
    )
    static_secret_sub_type = describe_item_response.item_sub_type

    secret_response = api_instance.get_secret_value(
        GetSecretValue(
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


def akeyless_backend(**kwargs: Unpack[_AkeylessBackendKwargs]) -> str:
    """Retrieve a secret value from Akeyless."""
    with CertFiles(kwargs.get('ca_cert') or None) as ca_cert_path:
        api_instance = _setup_client(
            kwargs['gateway_url'].rstrip('/'),
            ca_cert_path,
        )
        token = _authenticate(
            api_instance,
            kwargs['access_id'],
            kwargs['access_key'],
        )
        try:
            return _fetch_secret_value(
                api_instance,
                token,
                kwargs['secret_path'],
                kwargs.get('secret_key'),
            )
        except ApiException as exc:
            raise RuntimeError(
                f'Akeyless API error: {exc.reason} (Status: {exc.status})',
            ) from exc


def _coerce_ttl(ttl_value: int | str | None) -> int | None:
    if ttl_value is None or ttl_value == '':
        return None
    try:
        return int(ttl_value)
    except (TypeError, ValueError) as exc:
        raise ValueError('TTL must be an integer number of seconds.') from exc


def _fetch_ssh_certificate(
    api_instance: V2Api,
    token: str,
    ssh_inputs: _AkeylessSshBackendKwargs,
) -> str:
    response = api_instance.get_ssh_certificate(
        GetSSHCertificate(
            token=token,
            cert_issuer_name=ssh_inputs['cert_issue_name'],
            cert_username=ssh_inputs['cert_username'],
            ttl=_coerce_ttl(ssh_inputs.get('ttl')),
            public_key_data=ssh_inputs['public_key_data'],
        ),
    )
    if not response.data:
        raise RuntimeError(
            'Failed to generate signed SSH certificate: no data returned.',
        )
    return response.data


def akeyless_ssh_backend(**kwargs: Unpack[_AkeylessSshBackendKwargs]) -> str:
    """Generate a signed SSH certificate using Akeyless."""
    with CertFiles(kwargs.get('ca_cert') or None) as ca_cert_path:
        api_instance = _setup_client(
            kwargs['gateway_url'].rstrip('/'),
            ca_cert_path,
        )
        token = _authenticate(
            api_instance,
            kwargs['access_id'],
            kwargs['access_key'],
        )
        try:
            return _fetch_ssh_certificate(
                api_instance,
                token,
                kwargs,
            )
        except ApiException as exc:
            raise RuntimeError(
                f'Akeyless API error: {exc.reason} (Status: {exc.status})',
            ) from exc


akeyless_plugin = CredentialPlugin(
    'Akeyless',
    inputs=akeyless_inputs,
    backend=akeyless_backend,
)


akeyless_ssh_plugin = CredentialPlugin(
    'Akeyless SSH',
    inputs=akeyless_ssh_inputs,
    backend=akeyless_ssh_backend,
)
