"""MANDO: exposición de los negocios del usuario a eventos, por canal (docs/spec/02 M14). Reglas deterministas:
jurisdicción (país del evento ∈ jurisdicciones o UE) × sector/palabras clave × canal por vocabulario.
Cada alerta explica su canal y su confianza. Nada del perfil sale del proceso.
"""

from __future__ import annotations

from typing import Any

from ..db import Database, loads, new_id, now_iso
from ..embed import normalize_text

EU_MEMBERS = {"AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"}

CHANNEL_VOCAB: dict[str, tuple[str, ...]] = {
    "regulatory": ("reglamento", "regulation", "directiva", "directive", "ley", "law", "norma", "ai act", "mdr", "rgpd", "gdpr", "ehds", "autoriza", "approval", "ema", "fda", "licencia", "prohib", "ban", "etiquetado", "labelling", "certificación", "compliance", "consulta pública", "public consultation"),
    "tax": ("impuesto", "tax", "fiscal", "iva", "vat", "sociedades", "corporate tax", "pilar 2", "pillar two", "hacienda", "tributari", "aranceles", "tariff"),
    "fx": ("euro", "dólar", "dollar", "tipo de cambio", "exchange rate", "divisa", "currency", "bce", "ecb", "fed", "tipos de interés", "interest rate"),
    "supply_chain": ("cadena de suministro", "supply chain", "proveedor", "supplier", "escasez", "shortage", "fletes", "freight", "puerto", "port", "logística", "logistics", "aduana", "customs", "exportación", "export", "importación", "import", "chip", "principio activo", "api shortage"),
    "demand": ("consumo", "consumer", "demanda", "demand", "gasto", "spending", "salario", "wages", "empleo", "employment", "recesión", "recession", "turismo", "tourism", "poder adquisitivo", "purchasing power"),
    "reputation": ("boicot", "boycott", "escándalo", "scandal", "reputación", "reputation", "greenwashing", "fraude", "fraud", "investigación", "investigation", "polémica", "controversy"),
    "competition": ("competidor", "competitor", "fusión", "merger", "adquisición", "acquisition", "ronda", "funding round", "lanza", "launches", "patente", "patent", "ensayo clínico", "clinical trial"),
}

SECTOR_VOCAB: dict[str, tuple[str, ...]] = {
    "biotecnología": ("biotec", "biotech", "farmac", "pharma", "medicamento", "drug", "terapia", "therapy", "ensayo clínico", "clinical trial", "ema", "fda", "genética", "genomic"),
    "salud": ("salud", "health", "sanidad", "hospital", "médic", "medical", "paciente", "patient", "oms", "who", "envejecimiento", "ageing", "aging", "longevidad", "longevity"),
    "formación": ("formación", "training", "educación", "education", "universidad", "university", "certificación", "certification", "fp ", "vocational"),
    "fitness": ("fitness", "gimnasio", "gym", "deporte", "sport", "ejercicio", "exercise", "entrenador", "trainer", "wellness", "bienestar"),
    "investigación aplicada": ("investigación", "research", "ciencia", "science", "i+d", "r&d", "horizonte europa", "horizon europe", "publicación", "paper"),
    "salud digital": ("app de salud", "health app", "salud digital", "digital health", "wearable", "telemedicina", "telemedicine", "datos de salud", "health data", "ai act", "inteligencia artificial", "artificial intelligence", "mdr", "software médico"),
    "consumo": ("consumo", "consumer", "retail", "comercio", "moda", "fashion", "textil", "textile", "ropa", "apparel"),
    "textil": ("textil", "textile", "algodón", "cotton", "ropa", "apparel", "moda", "fashion", "streetwear", "zara", "inditex", "shein"),
}


def _match_terms(blob: str, vocab: tuple[str, ...]) -> list[str]:
    return [t for t in vocab if normalize_text(t) in blob]


MIN_MATERIALITY = 30.0


def evaluate_event(db: Database, event_id: str) -> list[dict[str, Any]]:
    ev = db.one("SELECT id, title_neutral, countries, coverage_stats, domain, materiality, lead_document_id FROM event WHERE id = ?", (event_id,))
    if not ev or (ev["materiality"] or 0) < MIN_MATERIALITY:
        return []
    lead = db.one("SELECT title, lede FROM document WHERE id = ?", (ev["lead_document_id"],))
    # solo el documento principal: el asunto del evento, no el ruido acumulado de 20 titulares
    blob = normalize_text(f"{ev['title_neutral']} {(lead['title'] if lead else '')} {(lead['lede'] if lead else '') or ''}")
    countries = set(loads(ev["countries"], []))
    alerts: list[dict[str, Any]] = []
    for b in db.all("SELECT * FROM business_unit"):
        juris = set(loads(b["jurisdictions"], []))
        in_juris = bool(countries & juris) or ("EU" in juris and bool(countries & EU_MEMBERS)) or ("EU" in juris and ("union europea" in blob or "comision europea" in blob or "parlamento europeo" in blob))
        if not in_juris:
            continue
        sectors = loads(b["sectors"], [])
        keywords = [normalize_text(k) for k in loads(b["keywords"], []) if k]
        sector_hits: list[str] = []
        for s in sectors:
            sector_hits += _match_terms(blob, SECTOR_VOCAB.get(s, (s,)))
        sector_hits = sorted(set(sector_hits))
        kw_hits = [k for k in keywords if k in blob]
        reg_hits = [r for r in loads(b["regulations"], []) if normalize_text(r.split("(")[0].strip()) in blob]
        # pertinencia sectorial: ≥ 2 términos distintos del sector, o palabra clave propia, o regulación nombrada
        if not (len(sector_hits) >= 2 or kw_hits or reg_hits):
            continue
        for channel, vocab in CHANNEL_VOCAB.items():
            ch_hits = sorted(set(_match_terms(blob, vocab)))
            if len(ch_hits) < 2 and not (reg_hits and channel == "regulatory"):
                continue
            conf = 0.2 * min(3, len(sector_hits)) + 0.3 * min(2, len(kw_hits)) + 0.1 * min(3, len(ch_hits)) + (0.25 if reg_hits else 0.0) + 0.15
            conf = round(min(0.95, conf), 2)
            if conf < 0.6:
                continue
            explanation = (
                f"Toca a «{b['name']}» por el canal {channel}: términos del sector ({', '.join(sector_hits[:3]) or '—'}), "
                f"del canal ({', '.join(ch_hits[:3])})"
                + (f", palabras clave ({', '.join(kw_hits[:2])})" if kw_hits else "")
                + (f", regulación ({', '.join(reg_hits[:2])})" if reg_hits else "")
                + (". Jurisdicción coincide." if in_juris else ". Jurisdicción no coincide: exposición indirecta.")
            )
            alerts.append({"business_id": b["id"], "business_name": b["name"], "event_id": event_id, "channel": channel, "explanation": explanation, "confidence": conf})
    if alerts:
        ts = now_iso()
        with db.tx() as conn:
            for a in alerts:
                conn.execute(
                    """INSERT INTO exposure_alert(id, business_id, event_id, channel, explanation, confidence, created_at)
                       VALUES (?,?,?,?,?,?,?)
                       ON CONFLICT(business_id, event_id, channel) DO UPDATE SET explanation=excluded.explanation,
                       confidence=excluded.confidence""",
                    (new_id(), a["business_id"], a["event_id"], a["channel"], a["explanation"], a["confidence"], ts),
                )
    return alerts
