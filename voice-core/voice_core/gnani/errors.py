class GnaniError(Exception):
    """A non-200 answer from a Gnani REST endpoint."""

    def __init__(self, status: int, body: str):
        super().__init__(f"Gnani API {status}: {body}")
        self.status = status
        self.body = body

    @property
    def retryable(self) -> bool:
        return self.status in (429, 500, 502, 503, 504)
