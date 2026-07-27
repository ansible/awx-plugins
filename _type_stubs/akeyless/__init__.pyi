from collections.abc import Mapping

class Configuration:
    host: str
    ssl_ca_cert: str | None
    verify_ssl: bool
    def __init__(self, host: str = ...) -> None: ...

class ApiClient:
    user_agent: str
    default_headers: dict[str, str]
    def __init__(self, configuration: Configuration | None = ...) -> None: ...

class Auth:
    access_id: str
    access_key: str
    def __init__(
        self,
        *,
        access_id: str = ...,
        access_key: str = ...,
    ) -> None: ...

class AuthOutput:
    token: str | None

class StaticSecretInfo:
    format: str

class ItemGeneralInfo:
    static_secret_info: StaticSecretInfo

class DescribeItemOutput:
    item_type: str
    item_sub_type: str
    item_general_info: ItemGeneralInfo

class DescribeItem:
    name: str
    token: str
    def __init__(
        self,
        *,
        name: str = ...,
        token: str = ...,
    ) -> None: ...

class GetSecretValue:
    names: list[str]
    token: str
    def __init__(
        self,
        *,
        names: list[str] = ...,
        token: str = ...,
    ) -> None: ...

class GetSSHCertificateOutput:
    data: str | None

class V2Api:
    def __init__(self, api_client: ApiClient | None = ...) -> None: ...
    def auth(self, auth: Auth) -> AuthOutput: ...
    def describe_item(self, req: DescribeItem) -> DescribeItemOutput: ...
    def get_secret_value(
        self,
        req: GetSecretValue,
    ) -> Mapping[str, str]: ...
    def get_ssh_certificate(
        self,
        req: object,
    ) -> GetSSHCertificateOutput: ...
