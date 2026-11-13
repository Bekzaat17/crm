class ApiError(Exception):
    """Ожидаемая ошибка бизнес-операции с HTTP-статусом для ответа API."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message, self.status = message, status
