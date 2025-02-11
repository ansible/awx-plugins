import pytest
from pytest_mock import MockerFixture

from github import Auth

from awx_plugins.credentials.github_app import github_app_backend


@pytest.mark.parametrize(
    ('github_app_backend_args', 'expected_error_msg'),
    (
        (
            {
                'github_api_url': '',
                'app_id': 'invalid',
                'private_rsa_key': '',
                'install_id': '666',
            },
            "^Expected GitHub App ID to be an integer but got 'invalid'$",
        ),
        (
            {
                'github_api_url': '',
                'app_id': '666',
                'private_rsa_key': '',
                'install_id': 'invalid',
            },
            '^Expected GitHub App Installation ID to be an integer '
            "but got 'invalid'$",
        ),
    ),
    ids=('gh-app-id', 'gh-app-install-id'),
)
def test_github_app_invalid_args(
    github_app_backend_args: dict[str, str],
    expected_error_msg: str,
) -> None:
    """Test that invalid arguments make ``github_app_backend`` bail early."""
    with pytest.raises(ValueError, match=expected_error_msg):
        github_app_backend(
            github_api_url='https://api.github.com',  # type: ignore[arg-type]
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

    token = github_app_backend(
        github_api_url='https://api.github.com',
        app_id='123',
        install_id='456',
        private_rsa_key='example-key',
    )
    assert token == 'example-token'
