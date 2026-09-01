from abc import ABC, abstractmethod
from typing import Any


class BaseLoader(ABC):
    """SOLID Dependency Inversion: Tüm Veri ve Prompt Yükleyicileri için Soyut Taban Sınıf."""

    @abstractmethod
    def load() -> Any:
        """Veri veya dosya yükleme metodunu tanımlar."""
        pass
