"""Akeyless SSH certificate issuance credential plugins."""

import typing as _t

from awx_plugins.interfaces._temporary_private_django_api import (  # noqa: WPS436
    gettext_noop as _,
)

from akeyless.models.get_ssh_certificate import GetSSHCertificate

from .. import _types
from ..plugin import CredentialPlugin
from . import _inputs, _session


__all__ = (  # noqa: WPS410
    'akeyless_ssh_backend',
    'akeyless_ssh_oidc_plugin',
    'akeyless_ssh_plugin',
)


_ssh_metadata: list[_types.MetadataDict] = [
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
]


_ssh_required = ['cert_issue_name', 'cert_username', 'public_key_data']


_akeyless_ssh_inputs: _types.PluginInputs = {
    'fields': _inputs.api_key_auth_fields,
    'metadata': _ssh_metadata,
    'required': [*_inputs.api_key_auth_required, *_ssh_required],
}


_akeyless_ssh_oidc_inputs: _types.PluginInputs = {
    'fields': _inputs.oidc_auth_fields,
    'metadata': _ssh_metadata,
    'required': [*_inputs.oidc_auth_required, *_ssh_required],
}


def _coerce_ttl(ttl_value: int | str | None) -> int | None:
    if ttl_value is None or ttl_value == '':
        return None
    try:
        return int(ttl_value)
    except (TypeError, ValueError) as exc:
        raise ValueError('TTL must be an integer number of seconds.') from exc


@_session.inject_session
def akeyless_ssh_backend(
    *,
    cert_issue_name: str,
    cert_username: str,
    public_key_data: str,
    ttl: int | str | None = None,
    **_discarded_kwargs: _t.Unpack[_inputs.EmptyKwargs],
) -> str:
    """Generate a signed SSH certificate using Akeyless.

    :param cert_issue_name: The path to the SSH certificate issuer.
    :param cert_username: The comma-separated user names to sign.
    :param public_key_data: The SSH public key to sign.
    :param ttl: The certificate lifetime in seconds.
    :param _discarded_kwargs: The authentication inputs, which
        :func:`~._session.inject_session` consumes.
    :returns: The signed SSH certificate.
    :raises ValueError: If Akeyless returns no certificate.
    """
    api, token = _session.current_session()
    ssh_cert_response = api.get_ssh_certificate(
        GetSSHCertificate(
            token=token,
            cert_issuer_name=cert_issue_name,
            cert_username=cert_username,
            ttl=_coerce_ttl(ttl),
            public_key_data=public_key_data,
        ),
    )
    if not ssh_cert_response.data:
        raise ValueError(
            'Failed to generate signed SSH certificate: no data returned.',
        )
    return ssh_cert_response.data


akeyless_ssh_plugin = CredentialPlugin(
    'Akeyless SSH',
    inputs=_akeyless_ssh_inputs,
    backend=akeyless_ssh_backend,
)


akeyless_ssh_oidc_plugin = CredentialPlugin(
    'Akeyless SSH (OIDC)',
    inputs=_akeyless_ssh_oidc_inputs,
    backend=akeyless_ssh_backend,
    plugin_description=_inputs.OIDC_PLUGIN_DESCRIPTION,
)
