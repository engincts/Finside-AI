from pathlib import Path
from typing import Tuple, Dict
from config import Config
from finside.loaders.base_loader import BaseLoader


class PromptLoader(BaseLoader):
    """SOLID Single Responsibility: Markdown tabanlı prompt şablonlarını yükleme ve önbellekleme sınıfı."""

    _cache: Dict[str, Tuple[str, str]] = {}

    def __init__(self, file_name: str = "bdr_analyst_v1.md"):
        self.file_name = file_name

    def load(self) -> Tuple[str, str]:
        """Markdown prompt dosyasını okur ve (SYSTEM_PROMPT, USER_PROMPT) ikilisini döndürür."""
        return self.load_prompt_md(self.file_name)

    @classmethod
    def load_prompt_md(cls, file_name: str = "bdr_analyst_v1.md") -> Tuple[str, str]:
        if file_name in cls._cache:
            return cls._cache[file_name]

        prompt_file = Config.BASE_DIR / "prompts" / file_name
        if not prompt_file.exists():
            raise FileNotFoundError(f"Prompt dosyası bulunamadı: {prompt_file}")

        content = prompt_file.read_text(encoding="utf-8")

        system_prompt = ""
        user_prompt = ""

        user_header = "## USER_PROMPT" if "## USER_PROMPT" in content else "## USER_TEMPLATE"

        if "## SYSTEM_PROMPT" in content and user_header in content:
            parts = content.split("## SYSTEM_PROMPT")[1].split(user_header)
            system_prompt = parts[0].strip()
            user_prompt = parts[1].strip()
        else:
            system_prompt = content.strip()
            user_prompt = "{bdr_text}"

        cls._cache[file_name] = (system_prompt, user_prompt)
        return system_prompt, user_prompt
