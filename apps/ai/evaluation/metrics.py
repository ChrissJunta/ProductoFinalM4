"""Accuracy y Macro F1 (SPEC §50) sin dependencias externas."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Report:
    total: int
    accuracy: float
    macro_f1: float
    per_label: dict  # etiqueta → (precision, recall, f1, soporte)
    errors: list  # (texto, esperado, predicho)


def evaluate(examples, predict):
    labels = sorted({e.intent for e in examples})
    pairs = [(e, predict(e.text)) for e in examples]
    per_label = {}
    for label in labels:
        tp = sum(1 for e, p in pairs if e.intent == label and p == label)
        fp = sum(1 for e, p in pairs if e.intent != label and p == label)
        fn = sum(1 for e, p in pairs if e.intent == label and p != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_label[label] = (precision, recall, f1, tp + fn)
    correct = sum(1 for e, p in pairs if e.intent == p)
    return Report(
        total=len(pairs),
        accuracy=correct / len(pairs) if pairs else 0.0,
        macro_f1=sum(v[2] for v in per_label.values()) / len(labels) if labels else 0.0,
        per_label=per_label,
        errors=[(e.text, e.intent, p) for e, p in pairs if e.intent != p],
    )
