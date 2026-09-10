"""Tests for the AWS Secrets Manager lookup plugin."""

# FIXME: the following violations must be addressed gradually and unignored
# mypy: disable-error-code="no-untyped-call"

import pytest
from pytest_mock import MockerFixture

from awx_plugins.credentials import aws_secretsmanager as asm_plugin_mod


TEST_REGION = 'us-west-2'
TEST_SECRET_NAME = 'some/secret'
TEST_ACCESS_KEY = 'AKIAIOSFODNN7EXAMPLE'
TEST_SECRET_KEY = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'
TEST_SECRET_STRING = 'sentinel'
TEST_SECRET_BINARY = b'sentinel-bytes'


def test_explicit_keys_are_passed_through(mocker: MockerFixture) -> None:
    """Check that supplied keys reach the client unchanged.

    :param mocker: The mocker fixture.
    """
    session = mocker.patch.object(asm_plugin_mod.boto3.session, 'Session')
    client = session.return_value.client
    client.return_value.get_secret_value.return_value = {
        'SecretString': TEST_SECRET_STRING,
    }

    secret = asm_plugin_mod.aws_secretsmanager_backend(
        region_name=TEST_REGION,
        secret_name=TEST_SECRET_NAME,
        aws_access_key=TEST_ACCESS_KEY,
        aws_secret_key=TEST_SECRET_KEY,
    )

    assert secret == TEST_SECRET_STRING
    assert client.call_args.kwargs['aws_access_key_id'] == TEST_ACCESS_KEY
    assert client.call_args.kwargs['aws_secret_access_key'] == TEST_SECRET_KEY


@pytest.mark.parametrize(
    'supplied',
    (
        pytest.param({}, id='absent'),
        pytest.param(
            {'aws_access_key': '', 'aws_secret_key': ''},
            id='empty',
        ),
    ),
)
def test_missing_keys_defer_to_the_chain(
    mocker: MockerFixture,
    supplied: dict[str, str],
) -> None:
    """Check that absent or empty keys are passed as ``None``.

    ``None`` makes botocore fall back to its default credential chain, which is
    what allows IRSA and instance roles to work. An empty string would instead
    be treated as a supplied credential and fail when signing.

    :param mocker: The mocker fixture.
    :param supplied: Credential fields as the plugin receives them.
    """
    session = mocker.patch.object(asm_plugin_mod.boto3.session, 'Session')
    client = session.return_value.client
    client.return_value.get_secret_value.return_value = {
        'SecretString': TEST_SECRET_STRING,
    }

    secret = asm_plugin_mod.aws_secretsmanager_backend(
        region_name=TEST_REGION,
        secret_name=TEST_SECRET_NAME,
        **supplied,
    )

    assert secret == TEST_SECRET_STRING
    assert client.call_args.kwargs['aws_access_key_id'] is None
    assert client.call_args.kwargs['aws_secret_access_key'] is None


def test_credential_fields_are_not_required() -> None:
    """Check that the key fields are optional in the input schema."""
    required = asm_plugin_mod.secrets_manager_inputs['required']

    assert 'aws_access_key' not in required
    assert 'aws_secret_key' not in required
    assert 'region_name' in required
    assert 'secret_name' in required


def test_binary_secrets_are_returned(mocker: MockerFixture) -> None:
    """Check that a binary secret is returned when no string is present.

    :param mocker: The mocker fixture.
    """
    session = mocker.patch.object(asm_plugin_mod.boto3.session, 'Session')
    client = session.return_value.client
    client.return_value.get_secret_value.return_value = {
        'SecretBinary': TEST_SECRET_BINARY,
    }

    secret = asm_plugin_mod.aws_secretsmanager_backend(
        region_name=TEST_REGION,
        secret_name=TEST_SECRET_NAME,
    )

    assert secret == TEST_SECRET_BINARY
