class ApiException(Exception):  # noqa: N818
    status: int
    reason: str
    def __init__(
        self,
        status: int = ...,
        reason: str = ...,
        http_resp: object | None = ...,
    ) -> None: ...
