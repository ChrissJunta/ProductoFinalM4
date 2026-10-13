"""Dataset etiquetado de intenciones (BE-T17): 20 ejemplos por intención.

Cada frase base produce dos ejemplos: la frase tal cual y una variante informal
(sin tildes ni signos de apertura, con saludo o cierre). Las frases base 2, 5 y 8
de cada intención forman el conjunto de **prueba**; el resto, el de **desarrollo**.
Ajustar palabras clave mirando solo el conjunto de desarrollo.
"""

import unicodedata
from dataclasses import dataclass

from .base_phrases import BASES

TEST_POSITIONS = {2, 5, 8}
PREFIXES = ["Hola, ", "Buenas, ", "Disculpe, ", ""]
SUFFIXES = ["", " por favor", " gracias", ""]


@dataclass(frozen=True)
class Example:
    text: str
    intent: str
    split: str  # "dev" | "test"


def informal(text, seed):
    plain = unicodedata.normalize("NFKD", text)
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    plain = plain.replace("¿", "").replace("¡", "").lower().rstrip("?!.")
    return f"{PREFIXES[seed % 4]}{plain}{SUFFIXES[(seed // 4) % 4]}"


def load_dataset(split=None):
    examples = []
    for n, (intent, bases) in enumerate(sorted(BASES.items())):
        for i, base in enumerate(bases):
            part = "test" if i in TEST_POSITIONS else "dev"
            examples.append(Example(base, intent, part))
            examples.append(Example(informal(base, n + i), intent, part))
    return [e for e in examples if split in (None, e.split)]
