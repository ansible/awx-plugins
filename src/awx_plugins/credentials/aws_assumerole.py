import datetime
import hashlib

import boto3

from .plugin import CredentialPlugin, translate_function as _


try:
    from botocore.exceptions import ClientError
except ImportError:
    """Caught by AnsibleAWSModule."""

_aws_cred_cache = {}


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
        role_arn: str | None,
        external_id: int,
) -> dict:
    explicit_credentials_empty = not access_key and not secret_key
    credential_kwargs = {} if explicit_credentials_empty else {
        # EE creds are read from the env
        'aws_access_key_id': access_key,
        'aws_secret_access_key': secret_key,
    }
    connection = boto3.client(service_name='sts', **credential_kwargs)
    try:
        response = connection.assume_role(
            RoleArn=role_arn,
            RoleSessionName='AAP_AWS_Role_Session1',
            ExternalId=external_id,
        )
    except ClientError as ce:
        raise ValueError(f'Got a bad client response from AWS: {ce.msg}.')

    credentials = response.get('Credentials', {})

    return credentials


def aws_assumerole_backend(**kwargs) -> dict:
    """This backend function actually contacts AWS to assume a given role for
    the specified user."""
    access_key = kwargs.get('access_key')
    secret_key = kwargs.get('secret_key')
    role_arn = kwargs.get('role_arn')
    external_id = kwargs.get('external_id')
    identifier = kwargs.get('identifier')

    # Generate a unique SHA256 hash for combo of user access key and ARN
    # This should allow two users requesting the same ARN role to have
    # separate credentials, and should allow the same user to request
    # multiple roles.
    #
    credential_key_hash = hashlib.sha256(
        (str(access_key or '') + role_arn).encode('utf-8'),
    )
    credential_key = credential_key_hash.hexdigest()

    credentials = _aws_cred_cache.get(credential_key, None)

    # If there are no credentials for this user/ARN *or* the credentials
    # we have in the cache have expired, then we need to contact AWS again.
    #
    if (credentials is None) or (
        credentials['Expiration'] < datetime.datetime.now(
            credentials['Expiration'].tzinfo,
        )
    ):

        credentials = aws_assumerole_getcreds(
            access_key, secret_key, role_arn, external_id,
        )

        _aws_cred_cache[credential_key] = credentials

    credentials = _aws_cred_cache.get(credential_key, None)

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
