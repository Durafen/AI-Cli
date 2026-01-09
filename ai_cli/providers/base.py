"""Base provider protocol and shared utilities."""

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable


@runtime_checkable
class Provider(Protocol):
    """Protocol defining the interface all providers must implement."""

    name: str

    def call(
        self,
        model: str,
        prompt: str,
        json_output: bool = False,
        yolo: bool = False,
    ) -> str:
        """Execute a prompt against the model and return the response."""
        ...

    def is_available(self) -> bool:
        """Check if this provider is available (CLI installed, API key set, etc.)."""
        ...


class BaseProvider(ABC):
    """Abstract base class for providers with common functionality."""

    name: str = "base"

    @abstractmethod
    def call(
        self,
        model: str,
        prompt: str,
        json_output: bool = False,
        yolo: bool = False,
    ) -> str:
        """Execute a prompt against the model and return the response."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is available."""
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name!r})>"
