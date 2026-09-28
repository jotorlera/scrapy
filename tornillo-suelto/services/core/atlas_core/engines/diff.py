"""DIFF de documentos oficiales (PRIMARIAS): comparación frase a frase con difflib y resumen de cambios
materiales (frases con cifras o modales que cambian). Determinista; el resumen semántico con LLM es opcional.
"""

from __future__ import annotations

import difflib
import re
from typing import Any

from ..util import split_sentences

_NUM = re.compile(r"\d")
_MODAL = re.compile(r"\b(will|shall|may|must|should|expects?|intend|deber[áa]|podr[áa]|prev[ée]|se compromete|mantendr[áa]|subir[áa]|bajar[áa]|raise|cut|hold|maintain|increase|decrease)\b", re.I)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def diff_documents(old_text: str, new_text: str) -> dict[str, Any]:
    a = split_sentences(old_text or "") or [old_text or ""]
    b = split_sentences(new_text or "") or [new_text or ""]
    sm = difflib.SequenceMatcher(a=[_norm(x) for x in a], b=[_norm(x) for x in b], autojunk=False)
    ops: list[dict[str, Any]] = []
    material: list[dict[str, Any]] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i1, i2):
                ops.append({"op": "equal", "old": a[k], "new": b[j1 + (k - i1)]})
            continue
        olds, news = a[i1:i2], b[j1:j2]
        if tag == "replace":
            for k in range(max(len(olds), len(news))):
                o = olds[k] if k < len(olds) else None
                n = news[k] if k < len(news) else None
                ops.append({"op": "replace", "old": o, "new": n, "inline": _inline(o, n) if o and n else None})
                if (o and (_NUM.search(o) or _MODAL.search(o))) or (n and (_NUM.search(n) or _MODAL.search(n))):
                    material.append({"kind": "changed", "old": o, "new": n})
        elif tag == "delete":
            for o in olds:
                ops.append({"op": "delete", "old": o, "new": None})
                if _NUM.search(o) or _MODAL.search(o):
                    material.append({"kind": "removed", "old": o, "new": None})
        elif tag == "insert":
            for n in news:
                ops.append({"op": "insert", "old": None, "new": n})
                if _NUM.search(n) or _MODAL.search(n):
                    material.append({"kind": "added", "old": None, "new": n})
    n_changed = sum(1 for o in ops if o["op"] != "equal")
    return {
        "ratio": round(sm.ratio(), 3),
        "n_old": len(a),
        "n_new": len(b),
        "n_changed": n_changed,
        "ops": ops,
        "material_changes": material[:40],
        "summary": _summary(len(a), len(b), n_changed, material),
        "method": "difflib.SequenceMatcher por frases + reglas (cifras/modales)",
    }


def _inline(o: str, n: str) -> list[dict[str, str]]:
    sm = difflib.SequenceMatcher(a=o.split(), b=n.split(), autojunk=False)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            out.append({"t": "eq", "s": " ".join(o.split()[i1:i2])})
        else:
            if i2 > i1:
                out.append({"t": "del", "s": " ".join(o.split()[i1:i2])})
            if j2 > j1:
                out.append({"t": "ins", "s": " ".join(n.split()[j1:j2])})
    return out


def _summary(n_old: int, n_new: int, n_changed: int, material: list[dict[str, Any]]) -> str:
    if n_changed == 0:
        return "Sin cambios de texto."
    parts = [f"{n_changed} frases cambian ({n_old} → {n_new})."]
    if material:
        kinds = {"changed": 0, "added": 0, "removed": 0}
        for m in material:
            kinds[m["kind"]] += 1
        parts.append(
            f"Cambios con cifras o compromisos: {kinds['changed']} modificados, {kinds['added']} añadidos, {kinds['removed']} eliminados."
        )
    else:
        parts.append("Ningún cambio afecta a cifras ni a compromisos explícitos.")
    return " ".join(parts)
