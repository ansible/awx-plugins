class GetSSHCertificate:
    token: str
    cert_issuer_name: str
    cert_username: str
    ttl: int | None
    public_key_data: str
    def __init__(
        self,
        *,
        token: str = ...,
        cert_issuer_name: str = ...,
        cert_username: str = ...,
        ttl: int | None = ...,
        public_key_data: str = ...,
    ) -> None: ...
