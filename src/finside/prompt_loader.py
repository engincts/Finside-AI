from pathlib import Path
from typing import Tuple, Dict
from config import Config


class PromptLoader:
    """SOLID Single Responsibility: Markdown tabanlı prompt şablonlarını yükleme ve işleme sınıfı."""

    _cache: Dict[str, Tuple[str, str]] = {}

    @classmethod
    def load_prompt_md(cls, file_name: str = "bdr_analyst_v1.md") -> Tuple[str, str]:
        """
        Markdown prompt dosyasını okuyup (SYSTEM_PROMPT, USER_PROMPT) ikilisini döndürür.
        """
        if file_name in cls._cache:
            return cls._cache[file_name]

        prompt_file = Config.BASE_DIR / "prompts" / file_name
        if not prompt_file.exists():
            raise FileNotFoundError(f"Prompt dosyası bulunamadı: {prompt_file}")

        content = prompt_file.read_text(encoding="utf-8")

        system_prompt = ""
        user_prompt = ""

        # Standart Jargon Ayrıştırması: ## SYSTEM_PROMPT ve ## USER_PROMPT (veya ## USER_TEMPLATE)
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
