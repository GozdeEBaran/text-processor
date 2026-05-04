from abc import ABC, abstractmethod


class AIServiceError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code


class AISchemaError(AIServiceError):
    pass


class BaseProvider(ABC):
    @abstractmethod
    def analyze(self, text: str) -> dict: ...
