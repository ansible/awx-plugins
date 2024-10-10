"""This module provides integration with AWS AssumeRole functionality."""

import hashlib
import typing
from datetime import datetime

from awx_plugins.interfaces._temporary_private_django_api import (  # noqa: WPS436
    gettext_noop as _,
)

import boto3
from botocore.exceptions import ClientError


if typing.TYPE_CHECKING:
    from mypy_boto3_sts.client import STSClient
    from mypy_boto3_sts.type_defs import (
        AssumeRoleResponseTypeDef,
        CredentialsTypeDef,
    )

from .plugin import CredentialPlugin


_aws_cred_cache: dict[
    str,
    'CredentialsTypeDef | dict[typing.Never, typing.Never]',
] | dict[typing.Never, typing.Never] = {}


assume_role_inputs = {
    'fields': [
        {
            'id': 'access_key',
            'label': _('AWS Access Key'),
            'type': 'string',
            'secret': True,
            'help_text': _(
                'The optional AWS access key for'
                'the user who will assume the role.',
            ),
        },
        {
            'id': 'secret_key',
            'label': 'AWS Secret Key',
            'type': 'string',
            'secret': True,
            'help_text': _(
                'The optional AWS secret key for the'
                'user who will assume the role.',
            ),
        },
        {
            'id': 'external_id',
            'label': 'External ID',
            'type': 'string',
            'help_text': _(
                'The optional External ID which will'
                'be provided to the assume role API.',
            ),
        },
    ],
    'metadata': [
        {
            'id': 'identifier',
            'label': 'Identifier',
            'type': 'string',
            'help_text': _(
                'The name of the key in the assumed AWS role'
                'to fetch [AccessKeyId | SecretAccessKey | SessionToken].',
            ),
        },
    ],
    'required': [
        'role_arn',
    ],
}


def aws_assumerole_getcreds(
        access_key: str | None,
        secret_key: str | None,
        role_arn: str,
        external_id: int,
) -> 'CredentialsTypeDef | dict[typing.Never, typing.Never]':
    """Return the credentials for use.

    :param access_key: The AWS access key ID.
    :type access_key: str
    :param secret_key: The AWS secret access key.
    :type secret_key: str
    :param role_arn: The ARN received from AWS.
    :type role_arn: str
    :param external_id: The external ID received from AWS.
    :type external_id: int
    :returns: The credentials received from AWS.
    :rtype: dict
    :raises ValueError: If the client response is bad.
    """
    connection: 'STSClient' = boto3.client(
        service_name='sts',
        # The following EE creds are read from the env if they are not passed:
        aws_access_key_id=access_key,  # defaults to `None` in the lib
        aws_secret_access_key=secret_key,  # defaults to `None` in the lib
    )
    try:
        response: 'AssumeRoleResponseTypeDef' = connection.assume_role(
            RoleArn=role_arn,
            RoleSessionName='AAP_AWS_Role_Session1',
            ExternalId=external_id,
        )
    except ClientError as client_err:
        raise ValueError(
            f'Got a bad client response from AWS: {client_err.message}.',
        ) from client_err

    return response.get('Credentials', {})


def aws_assumerole_backend(
        access_key: str | None,
        secret_key: str | None,
        role_arn: str,
        external_id: int,
        identifier: str,
) -> dict:
    """Contact AWS to assume a given role for the user.

    :param access_key: The AWS access key ID.
    :type access_key: str
    :param secret_key: The AWS secret access key.
    :type secret_key: str
    :param role_arn: The ARN received from AWS.
    :type role_arn: str
    :param external_id: The external ID received from AWS.
    :type external_id: int
    :param identifier: The identifier to fetch from the assumed role.
    :type identifier: str
    :raises ValueError: If the identifier is not found.
    :returns: The identifier fetched from the assumed role.
    :rtype: dict
    """
    # Generate a unique SHA256 hash for combo of user access key and ARN
    # This should allow two users requesting the same ARN role to have
    # separate credentials, and should allow the same user to request
    # multiple roles.
    credential_key_hash = hashlib.sha256(
        (str(access_key or '') + role_arn).encode('utf-8'),
    )
    credential_key = credential_key_hash.hexdigest()

    credentials = _aws_cred_cache.get(credential_key, None)

    # If there are no credentials for this user/ARN *or* the credentials
    # we have in the cache have expired, then we need to contact AWS again.
    creds_expired = (
        (creds_expire_at := credentials.get('Expiration')) and
        creds_expire_at < datetime.now(credentials['Expiration'].tzinfo)
    )
    if creds_expired:

        credentials = aws_assumerole_getcreds(
            access_key, secret_key, role_arn, external_id,
        )

        _aws_cred_cache[credential_key] = credentials

    credentials = _aws_cred_cache.get(credential_key, {})

    try:
        return credentials[identifier]
    except KeyError as key_err:
        raise ValueError(
            f'Could not find a value for {identifier}.',
        ) from key_err


aws_assumerole_plugin = CredentialPlugin(
    'AWS Assume Role Plugin',
    inputs=assume_role_inputs,
    backend=aws_assumerole_backend,
)
