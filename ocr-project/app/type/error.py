from http import HTTPStatus


class ErrorResponse:
    def __init__(self, code: HTTPStatus, message: str) -> None:
        self.code = code
        self.message = message
