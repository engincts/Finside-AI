import re
from typing import List

_HEADING_REGEXES = [
    re.compile(r"^\s*(?:NOT|D[İI]PNOT)\s*[-–—:.]?\s*\d+[A-Za-z]?[.)]?\s+\S", re.IGNORECASE),
    re.compile(r"^\s*\d{1,2}[.)]\s+[0-9A-ZÇĞİÖŞÜ][^\n]{2,120}$"),
    re.compile(r"^\s*[A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜ0-9 .,\-/()&’'\"]{16,}$"),
    re.compile(
        r"^\s*(?:KİLİT DENETİM KONULARI|BAĞIMSIZ DENETÇİ|GÖRÜŞÜN DAYANAĞI|"
        r"İŞLETMENİN SÜREKLİLİĞİ|RAPORLAMA DÖNEMİNDEN SONRAKİ|FİNANSAL RİSK YÖNETİMİ)",
        re.IGNORECASE,
    ),
]


def _is_heading(line: str) -> bool:
    stripped = line.strip()
    if len(stripped) < 4 or len(stripped) > 160:
        return False
    return any(rx.match(line) for rx in _HEADING_REGEXES)


def split_sections(text: str) -> List[str]:
    """BDR metnini dipnot/başlık sınırlarında kendi içinde bütün bölümlere ayırır."""
    sections: List[str] = []
    buffer: List[str] = []
    for line in text.splitlines(keepends=True):
        if buffer and _is_heading(line):
            sections.append("".join(buffer))
            buffer = [line]
        else:
            buffer.append(line)
    if buffer:
        sections.append("".join(buffer))
    return sections


def _hard_split(text: str, max_chars: int) -> List[str]:
    return [text[i:i + max_chars] for i in range(0, len(text), max_chars)] or [""]


def pack_sections(sections: List[str], max_chars: int) -> List[str]:
    """Ardışık bölümleri sınırı aşmadan aç gözlü şekilde tek parçalarda toplar."""
    chunks: List[str] = []
    current = ""
    for section in sections:
        if len(section) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_hard_split(section, max_chars))
        elif current and len(current) + len(section) > max_chars:
            chunks.append(current)
            current = section
        else:
            current += section
    if current:
        chunks.append(current)
    return chunks


def build_chunks(text: str, max_chars: int, header_chars: int = 1200) -> List[str]:
    """Yapı-farkında parçalar üretir; ilk parça dışındakilere firma künyesini ekler."""
    if len(text) <= max_chars:
        return [text]

    header = text[:header_chars].strip()
    body_budget = max(max_chars - len(header) - 32, max_chars // 2)
    packed = pack_sections(split_sections(text), body_budget)

    result: List[str] = []
    for index, chunk in enumerate(packed):
        chunk = chunk.strip()
        if index == 0:
            result.append(chunk)
        else:
            result.append(f"{header}\n\n[... rapor devamı ...]\n\n{chunk}")
    return result
