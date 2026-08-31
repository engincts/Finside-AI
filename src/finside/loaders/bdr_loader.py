from pathlib import Path
from typing import Dict, Any, Union
from finside.loaders.base_loader import BaseLoader


class BDRLoader(BaseLoader):
    """SOLID Single Responsibility: BDR ve finansal metin dosyalarını yükleme ve temizleme sınıfı."""

    def __init__(self, file_path: Union[str, Path]):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"BDR dosyası bulunamadı: {self.file_path}")

    def load(self) -> str:
        """BDR metin içeriğini okur ve gereksiz boşlukları temizler."""
        content = self.file_path.read_text(encoding="utf-8")
        return self._clean_text(content)

    def get_processed_bdr(self) -> Dict[str, Any]:
        """BDR metnini ve metin istatistiklerini paket halinde döndürür."""
        cleaned_content = self.load()
        return {
            "file_name": self.file_path.name,
            "file_path": str(self.file_path),
            "content": cleaned_content,
            "character_count": len(cleaned_content),
            "word_count": len(cleaned_content.split())
        }

    def _clean_text(self, text: str) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)
