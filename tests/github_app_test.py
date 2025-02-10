import pytest
from pytest_mock import MockerFixture

from github import Auth

from awx_plugins.credentials.github_app import github_app_backend


@pytest.mark.parametrize(
    ('github_app_backend_args', 'missing_args_regex'),
    (
        (
            {},
            '.*',
        ),
        (
            {'app_id': '123', 'install_id': '456', 'private_rsa_key': 'key'},
            "'GitHub URL'",
        ),
    ),
    ids=('no-args', 'no-gh-url'),
)
def test_github_app_insufficient_args(
    github_app_backend_args: dict[str, str],
    missing_args_regex: str,
) -> None:
    """Test that missing parameters raise an exception."""
    with pytest.raises(ValueError, match=fr'Missing Parameter: \[{missing_args_regex}\]'):
        github_app_backend(**github_app_backend_args)


@pytest.mark.parametrize(
    ('github_app_backend_args', 'expected_error_msg'),
    (
        (
            {'app_id': 'invalid', 'install_id': 'invalid'},
            r'App ID and Installation ID must be integers .*invalid literal for int\(\) with base 10: .*',
        ),
    ),
    ids=('app-n-install-ids',),
)
def test_github_app_invalid_args(
    github_app_backend_args: dict[str, str],
    expected_error_msg: str,
) -> None:
    """Test that invalid arguments make ``github_app_backend`` bail early."""
    with pytest.raises(ValueError, match=expected_error_msg):
        github_app_backend(
            github_url='https://api.github.com',  # type: ignore[arg-type]
            private_rsa_key='key',  # type: ignore[arg-type]
            **github_app_backend_args,
        )


def test_github_app_github_authentication(mocker: MockerFixture) -> None:
    """Test successful GitHub authentication."""

    # Mock the AppInstallationAuth to be returned
    mock_auth_instance = mocker.MagicMock(spec=Auth.AppInstallationAuth)
    mock_auth_instance.token = 'example-token'

    # Mock AppAuth and get_installation_auth() to return our mock instance
    mock_app_auth = mocker.MagicMock(spec=Auth.AppAuth)
    mock_app_auth.get_installation_auth.return_value = mock_auth_instance

    mocker.patch.object(Auth, 'AppAuth', return_value=mock_app_auth)

    args = {
        'github_url': 'https://api.github.com',
        'app_id': '123',
        'install_id': '456',
        'private_rsa_key': 'example-key',
    }

    token = github_app_backend(**args)  # type: ignore[arg-type]
    assert token == 'example-token'
