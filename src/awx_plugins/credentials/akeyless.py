# FIXME: the following violations must be addressed gradually and unignored
# mypy: disable-error-code="import-not-found, import-untyped, no-untyped-def"

import json

from awx_plugins.interfaces._temporary_private_django_api import (  # noqa: WPS436
    gettext_noop as _,
)

from akeyless import Auth, ApiClient, Configuration, DescribeItem, GetSecretValue, V2Api
from akeyless.models.get_ssh_certificate import GetSSHCertificate
from akeyless.rest import ApiException

from .plugin import CertFiles, CredentialPlugin


SUPPORTED_ITEM_TYPES = {'STATIC_SECRET'}


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


def _setup_client(gateway_url, ca_cert_path):
    client_configuration = Configuration(host=gateway_url)
    if ca_cert_path:
        client_configuration.ssl_ca_cert = ca_cert_path
        client_configuration.verify_ssl = True
    api_client = ApiClient(client_configuration)
    api_client.user_agent = 'AWX'
    api_client.default_headers['akeylessclienttype'] = 'AWX'
    return V2Api(api_client)


def _authenticate(api_instance, access_id, access_key):
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


def _extract_secret_value(
    secret_response,
    secret_path,
    secret_key,
    static_secret_format,
    static_secret_sub_type,
):
    secret_data = secret_response[secret_path]
    if static_secret_format == 'text':
        if static_secret_sub_type == 'password':
            if secret_key:
                if secret_key not in ('username', 'password'):
                    raise NotImplementedError(
                        'Password secrets only support "username" or "password" '
                        'keys.',
                    )
                secret_dict = json.loads(secret_data)
                return secret_dict[secret_key]
            return secret_data
        if static_secret_sub_type == 'generic':
            return secret_data
        raise NotImplementedError(
            'Static secret sub type must be "password" or "generic".',
        )

    if static_secret_format in ('json', 'key-value'):
        if secret_key:
            secret_dict = json.loads(secret_data)
            if secret_key not in secret_dict:
                raise KeyError(
                    f'Key "{secret_key}" not found in secret at path: '
                    f'{secret_path}',
                )
            return secret_dict[secret_key]
        return str(secret_data)

    raise NotImplementedError(
        'Static secret format must be "text", "json", or "key-value".',
    )


def akeyless_backend(**kwargs):
    gateway_url = kwargs['gateway_url'].rstrip('/')
    access_id = kwargs['access_id']
    access_key = kwargs['access_key']
    ca_cert = kwargs.get('ca_cert') or None
    secret_path = kwargs['secret_path']
    secret_key = kwargs.get('secret_key')

    with CertFiles(ca_cert) as ca_cert_path:
        try:
            api_instance = _setup_client(gateway_url, ca_cert_path)
            token = _authenticate(api_instance, access_id, access_key)

            describe_item_request = DescribeItem(name=secret_path, token=token)
            describe_item_response = api_instance.describe_item(
                describe_item_request,
            )
            item_type = describe_item_response.item_type
            if item_type not in SUPPORTED_ITEM_TYPES:
                raise NotImplementedError(
                    f'Secret "{secret_path}" is of type "{item_type}". '
                    f'Supported types: {sorted(SUPPORTED_ITEM_TYPES)}.',
                )

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
        except ApiException as exc:
            raise RuntimeError(
                f'Akeyless API error: {exc.reason} (Status: {exc.status})',
            ) from exc


def _coerce_ttl(ttl_value):
    if ttl_value in (None, ''):
        return None
    try:
        return int(ttl_value)
    except (TypeError, ValueError) as exc:
        raise ValueError('TTL must be an integer number of seconds.') from exc


def akeyless_ssh_backend(**kwargs):
    gateway_url = kwargs['gateway_url'].rstrip('/')
    access_id = kwargs['access_id']
    access_key = kwargs['access_key']
    ca_cert = kwargs.get('ca_cert') or None
    cert_issue_name = kwargs['cert_issue_name']
    cert_username = kwargs['cert_username']
    public_key_data = kwargs['public_key_data']
    ttl = _coerce_ttl(kwargs.get('ttl'))

    with CertFiles(ca_cert) as ca_cert_path:
        try:
            api_instance = _setup_client(gateway_url, ca_cert_path)
            token = _authenticate(api_instance, access_id, access_key)

            response = api_instance.get_ssh_certificate(
                GetSSHCertificate(
                    token=token,
                    cert_issuer_name=cert_issue_name,
                    cert_username=cert_username,
                    ttl=ttl,
                    public_key_data=public_key_data,
                ),
            )
            if not response.data:
                raise RuntimeError(
                    'Failed to generate signed SSH certificate: no data returned.',
                )
            return response.data
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
