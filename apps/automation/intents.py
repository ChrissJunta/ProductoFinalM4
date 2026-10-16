"""Intent Engine por reglas (SPEC §30, BE-T13).

Orden: reglas determinísticas → coincidencias configuradas (`Intent.keywords`).
El LLM (BE-T16/T17) solo interviene si esto no resuelve; en el grafo LangGraph
(BE-T18A) esta función es el nodo `classify_rules`.
"""

import re
import unicodedata
from dataclasses import dataclass, field

from .models import Intent

TICKET_CODE_RE = re.compile(r"\bHD-\d{4}-\d{6}\b", re.IGNORECASE)

# Las reglas son determinísticas: si resuelven, la confianza es fija y supera el
# umbral de revisión humana (0.85, SPEC §46). Un empate es una solicitud ambigua
# (CA-006) y queda bajo 0.70, por lo que el Autonomy Engine la envía a N4.
CODE_CONFIDENCE = 1.0
RULES_CONFIDENCE = 0.90
AMBIGUOUS_CONFIDENCE = 0.50
# Un mensaje formado SOLO por estas palabras es un saludo (ADR-083). Con cualquier otra
# palabra decide el resto del motor: «hola, necesito un certificado» sigue siendo trámite.
GREETING_WORDS = frozenset(
    "hola holi hey buenas buenos buen dia dias tardes noches saludos que tal gracias muchas "
    "mil ok okay vale listo perfecto genial adios chao hasta luego pronto manana "
    "como estas esta muy bien".split()
)


@dataclass(frozen=True)
class IntentMatch:
    intent: Intent | None
    confidence: float
    source: str = "RULES"
    candidates: tuple[str, ...] = ()
    entities: dict = field(default_factory=dict)

    @property
    def ambiguous(self):
        return self.intent is None and len(self.candidates) > 1


def normalize(text):
    """Minúsculas, sin tildes (ñ → n) y solo letras/dígitos separados por un espacio."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def parse_keywords(raw):
    """Cada línea es una lista de partes que deben aparecer todas («a + b»)."""
    rules = []
    for line in raw.splitlines():
        parts = tuple(p for p in (normalize(x) for x in line.split("+")) if p)
        if parts:
            rules.append(parts)
    return rules


def score(norm_text, rules):
    """Suma, por cada regla que coincide, el número de palabras que la forman."""
    padded = f" {norm_text} "
    return sum(
        sum(len(p.split()) for p in parts)
        for parts in rules
        if all(f" {p} " in padded for p in parts)
    )


def identify_intent(text):
    """Devuelve un `IntentMatch`. `intent=None` significa «las reglas no resuelven»."""
    code = TICKET_CODE_RE.search(text)
    if code:
        intent = Intent.objects.filter(code="CHECK_TICKET", is_active=True).first()
        if intent:
            return IntentMatch(
                intent,
                CODE_CONFIDENCE,
                candidates=(intent.code,),
                entities={"ticket_code": code.group(0).upper()},
            )

    norm = normalize(text)
    if norm and set(norm.split()) <= GREETING_WORDS:
        # Solo saludo o cortesía: responde el asistente, sin ticket (ADR-083).
        intent = Intent.objects.filter(code="GENERAL_QUESTION", is_active=True).first()
        if intent:
            return IntentMatch(intent, RULES_CONFIDENCE, candidates=(intent.code,))
    scores = {}
    for intent in Intent.objects.filter(is_active=True).exclude(keywords=""):
        points = score(norm, parse_keywords(intent.keywords))
        if points:
            scores[intent] = points
    if not scores:
        return IntentMatch(None, 0.0)
    best = max(scores.values())
    top = sorted((i for i, s in scores.items() if s == best), key=lambda i: i.code)
    if len(top) > 1:
        return IntentMatch(None, AMBIGUOUS_CONFIDENCE, candidates=tuple(i.code for i in top))
    return IntentMatch(top[0], RULES_CONFIDENCE, candidates=(top[0].code,))
