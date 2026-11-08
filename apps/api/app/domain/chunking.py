"""Divisor de Markdown: títulos e depois blocos de 1.000 com sobreposição de 150. Seção 7.3.

Camada de domínio. `IngestionService` (`app/services/ingestion.py`) chama `split_markdown` no
texto de cada versão de documento, inclusive no texto extraído de um PDF, e grava um chunk por
pedaço. `SeedService` (`app/services/seed.py`) chama `markdown_title` para dar título aos
arquivos de `content/corpus`.

A seção 6.4 pede o divisor num threadpool. Hoje a ingestão chama `split_markdown` direto no
loop de eventos; a Etapa 13.1 do plano passa a chamá-lo com `asyncio.to_thread`.
"""

import re
from dataclasses import dataclass

# Tamanhos em caracteres, não em tokens (seção 7.3).
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
# Título ATX do Markdown: de 1 a 6 `#`, espaço ou tab e o texto. O grupo 1 é o nível e o
# grupo 2 o texto, sem os espaços do fim.
_HEADING = re.compile(r"^(#{1,6})[ \t]+(.*\S)\s*$")


@dataclass(frozen=True, slots=True)
class TextChunk:
    """Um pedaço de documento antes do embedding. Vira uma linha de `chunks` (seção 8.1).

    `heading` é o título da seção onde o pedaço está, ou `None` no texto antes do primeiro
    título. Ele entra no texto de embedding (seção 8.3) e no bloco de contexto do gerador.
    """

    heading: str | None
    content: str


def markdown_title(markdown: str, fallback: str) -> str:
    """Texto do primeiro título de nível 1 (`# Título`), ou `fallback` sem nenhum.

    A semente passa o nome do arquivo sem extensão como `fallback`.
    """
    for line in markdown.splitlines():
        match = _HEADING.match(line.strip())
        if match and match.group(1) == "#":
            return match.group(2).strip()
    return fallback


def split_markdown(
    markdown: str,
    *,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[TextChunk]:
    """Divide o documento em `TextChunk`, na ordem do texto. Seção 7.3 do SDD.

    1. Normaliza as quebras de linha do Windows e do Mac antigo para LF.
    2. Separa as seções pelos títulos (`_sections`). Cada título vira o `heading` dos pedaços
       da seção.
    3. Divide o corpo de cada seção em blocos de até `chunk_size` caracteres
       (`_split_recursive`).
    4. Tira os espaços das pontas e descarta os pedaços vazios.
    """
    # 1.
    normalized = markdown.replace("\r\n", "\n").replace("\r", "\n")
    chunks: list[TextChunk] = []
    # 2.
    for heading, body in _sections(normalized):
        # 3.
        for piece in _split_recursive(body, chunk_size, overlap):
            # 4.
            content = piece.strip()
            if content:
                chunks.append(TextChunk(heading, content))
    return chunks


def _sections(markdown: str) -> list[tuple[str | None, str]]:
    """Agrupa as linhas por título, como pares `(título, corpo)`.

    A primeira seção, sem título, junta o texto antes do primeiro título. A linha do título não
    entra no corpo: ela vira o `heading`. A comparação usa a linha crua, então uma linha com
    espaço antes do `#` não é título aqui, ao contrário de `markdown_title`.
    """
    sections: list[tuple[str | None, list[str]]] = [(None, [])]
    for line in markdown.split("\n"):
        match = _HEADING.match(line)
        if match:
            sections.append((match.group(2).strip(), []))
            continue
        sections[-1][1].append(line)
    return [(heading, "\n".join(lines).strip()) for heading, lines in sections]


def _split_recursive(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Corta `text` em blocos de até `chunk_size` caracteres, com `overlap` de sobreposição.

    A seção 7.3 chama isto de divisor recursivo: cada corte prefere o fim de um parágrafo,
    depois o de uma linha e depois um espaço (`_preferred_end`). É uma implementação própria,
    porque o domínio não importa o LangChain (seção 6.2). O bloco seguinte começa `overlap`
    caracteres antes do corte, então o texto perto do corte aparece nos dois blocos.
    """
    if text == "":
        return []
    if len(text) <= chunk_size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        # Só o último bloco termina no fim exato do texto. Os outros procuram um separador.
        if end < len(text):
            end = _preferred_end(text, start, end)
        # Proteção para `chunk_size` zero ou negativo: avança pelo menos um caractere.
        if end <= start:
            end = min(start + max(chunk_size, 1), len(text))
        chunks.append(text[start:end])
        if end >= len(text):
            break
        next_start = end - overlap
        # Uma sobreposição do tamanho do bloco faria o laço não avançar: aí não há sobreposição.
        if next_start <= start:
            next_start = end
        start = next_start
    return chunks


def _preferred_end(text: str, start: int, end: int) -> int:
    """Posição do corte dentro de `text[start:end]`.

    Procura, do fim para o começo, uma linha em branco, senão uma quebra de linha, senão um
    espaço. O separador fica fora deste bloco. Sem nenhum separador, corta em `end`, no meio
    da palavra. `index > 0` impede um bloco vazio.
    """
    window = text[start:end]
    for separator in ("\n\n", "\n", " "):
        index = window.rfind(separator)
        if index > 0:
            return start + index
    return end
