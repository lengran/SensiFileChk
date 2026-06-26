from abc import ABC, abstractmethod


class ParserError(Exception):
    pass


class BaseParser(ABC):
    @abstractmethod
    def parse(self, file_path: str) -> str:
        pass
