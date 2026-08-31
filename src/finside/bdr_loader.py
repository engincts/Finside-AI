from pathlib import Path
from typing import Dict, Any, List, Optional
import re


class BDRLoader:
    """BDR metin dosyalarını yükleme, temizleme ve işleme sınıfı."""

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"BDR dosyası bulunamadı: {self.file_path}")

    def load_raw_text(self) -> str:
        """Dosyadan ham metni okur."""
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            # UTF-8 başarısız olursa latin-1 dene
            with open(self.file_path, "r", encoding="latin-1") as f:
                return f.read()

    def clean_text(self, text: str) -> str:
        """Metindeki fazla boşlukları ve sayfa başlıkları/altlıklarını temizler."""
        # Birden fazla boş satırı ve fazla boşlukları düzenle
        cleaned = re.sub(r'\n{3,}', '\n\n', text)
        cleaned = re.sub(r'[ \t]+', ' ', cleaned)
        return cleaned.strip()

    def get_processed_bdr(self) -> Dict[str, Any]:
        """İşlenmiş metni ve dosya meta verilerini döndürür."""
        raw = self.load_raw_text()
        cleaned = self.clean_text(raw)
        
        return {
            "file_name": self.file_path.name,
            "file_path": str(self.file_path.resolve()),
            "character_count": len(cleaned),
            "word_count": len(cleaned.split()),
            "content": cleaned
        }
