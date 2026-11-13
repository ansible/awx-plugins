class ApiException(Exception):  # noqa: N818 -- the Akeyless SDK class name
    status: int
    reason: str
    def __init__(
        self,
        status: int = ...,
        reason: str = ...,
        http_resp: object | None = ...,
    ) -> None: ...
