from abc import ABC, abstractmethod
from typing import Any


class BaseLoader(ABC):
    """SOLID Dependency Inversion (DIP): Tüm veri ve dosya yükleyiciler için soyut taban sınıfı."""

    @abstractmethod
    def load(self) -> Any:
        """Veri veya dosya yükleme metodunu çalıştırır ve yüklenen nesneyi döndürür."""
        pass
