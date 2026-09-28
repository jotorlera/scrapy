"""Motores deterministas: silencio sintético, pronósticos, léxico, diff, afirmaciones, materialidad, clustering."""

from __future__ import annotations

import math

from atlas_core.engines import forecast as fm
from atlas_core.engines.claims import (
    ClaimCandidate,
    compute_status,
    heuristic_claims,
    persist_claims,
    quote_supported,
)
from atlas_core.engines.coverage import coverage_for_docs, shares_from_docs, silence_index
from atlas_core.engines.diff import diff_documents
from atlas_core.engines.lexicon import fightin_words
from atlas_core.engines.materiality import compute_materiality, irreversibility_score
from atlas_core.gazetteer import classify_domain, countries_from_mentions, find_mentions
from conftest import make_doc, make_source

# ───────── PRISMA: índice de silencio ─────────


def test_silence_index_synthetic_event_triggers_other_ecosystems():
    """Un evento cubierto solo por un ecosistema dispara el índice en los demás (test obligatorio, docs/07 §4)."""
    baseline = []
    for eco, n in (("left", 100), ("center", 100), ("right", 100)):
        baseline += [
            {
                "ideology_label": eco,
                "region_bloc": "es",
                "lang": "es",
                "type": "newspaper",
                "state_relation": "independent",
            }
        ] * n
    shares = shares_from_docs(baseline)
    event_docs = [
        {
            "ideology_label": "right",
            "region_bloc": "es",
            "lang": "es",
            "type": "newspaper",
            "state_relation": "independent",
            "tier": 2,
            "source_id": f"s{i}",
        }
        for i in range(30)
    ]
    cov = coverage_for_docs(event_docs, shares)
    ideo = cov["axes"]["ideology"]
    assert ideo["left"]["silent"] and ideo["center"]["silent"]
    assert not ideo["right"]["silent"] and ideo["right"]["over"]
    assert ideo["left"]["s"] > 2 and ideo["left"]["expected"] >= 5
    assert {s["ecosystem"] for s in cov["silences"] if s["axis"] == "ideology"} == {"left", "center"}


def test_silence_index_not_triggered_when_expected_small():
    si = silence_index({"left": 0}, {"left": 0.3}, total=6)
    assert si["left"]["expected"] < 5 and not si["left"]["silent"]


# ───────── PRONÓSTICOS ─────────


def test_brier_and_log_score():
    assert math.isclose(fm.brier(0.8, 1), 0.04) and math.isclose(fm.brier(0.8, 0), 0.64)
    assert fm.log_score(0.5, 1) == math.log(0.5)
    assert fm.log_score(0.999, 0) == math.log(0.01)  # recorte


def test_aggregate_ensemble_and_market_blend():
    agg = fm.aggregate_ensemble([0.6, 0.7, 0.65])
    assert 0.6 < agg["raw"] < 0.7
    assert agg["extremized"] > agg["raw"]  # a=1.5 aleja del 50%
    p = fm.blend_with_market(0.9, 0.5, alpha=0.4)
    assert 0.5 < p < 0.9
    assert fm.blend_with_market(0.9, None) == 0.9


def test_calibration_bins_and_wilson():
    pairs = [(0.9, 1)] * 9 + [(0.9, 0)] + [(0.1, 0)] * 9 + [(0.1, 1)]
    cal = fm.calibration(pairs)
    assert cal["n"] == 20
    top = cal["bins"][9]
    assert top["n"] == 10 and top["freq"] == 0.9 and top["ci"][0] < 0.9 < top["ci"][1]
    assert abs(cal["reliability"]) < 1e-9  # perfectamente calibrado
    lo, hi = fm.wilson(0, 10)
    assert lo == 0.0 and 0.2 < hi < 0.35


def test_question_quality_filter():
    assert fm.question_quality_issues("Sube", "x", 0.5)
    assert not fm.question_quality_issues(
        "¿Bajará el BCE los tipos en su próxima reunión?",
        "Comunicado oficial del BCE; SÍ si baja la facilidad de depósito.",
        0.4,
    )
    assert fm.question_quality_issues(
        "¿Saldrá el sol mañana en Madrid?", "Observatorio: SÍ si amanece; criterio con fuente y umbral.", 0.99
    )


# ───────── LÉXICO DIFERENCIAL ─────────


def test_fightin_words_separates_vocabularies():
    left = ["recorte del gasto social golpea a los trabajadores"] * 6 + [
        "los trabajadores denuncian el recorte"
    ] * 4
    right = ["reforma del gasto público alivia a los contribuyentes"] * 6 + [
        "los contribuyentes celebran la reforma"
    ] * 4
    lex = fightin_words({"left": left, "right": right}, min_count=2)
    assert "recorte" in {t["term"] for t in lex["left"]} or "trabajadores" in {t["term"] for t in lex["left"]}
    assert "reforma" in {t["term"] for t in lex["right"]} or "contribuyentes" in {
        t["term"] for t in lex["right"]
    }


# ───────── DIFF ─────────


def test_diff_detects_material_change():
    old = "El Consejo de Gobierno mantiene los tipos en el 2,00%. La inflación seguirá cerca del objetivo. Vigilaremos los datos."
    new = "El Consejo de Gobierno baja los tipos al 1,75%. La inflación seguirá cerca del objetivo. Vigilaremos los datos."
    d = diff_documents(old, new)
    assert d["n_changed"] >= 1
    assert any(m["kind"] == "changed" and "1,75" in (m["new"] or "") for m in d["material_changes"])
    assert diff_documents(old, old)["summary"] == "Sin cambios de texto."


# ───────── AFIRMACIONES: cita o descarta ─────────


def test_quote_supported_is_literal_but_tolerant():
    text = "El Gobierno aprobó   hoy la Ley de Presupuestos con 176 votos a favor."
    assert quote_supported("el gobierno aprobo hoy la ley de presupuestos", text)
    assert not quote_supported("El Gobierno rechazó la ley", text)
    assert not quote_supported("corto", text)


def test_heuristic_claims_have_quotes_levels_and_attribution():
    doc = {
        "id": "d1",
        "title": "El Congreso aprueba la ley de pensiones con 172 votos a favor y 164 en contra",
        "lede": "Según el ministro de Economía, la reforma costará 3.000 millones de euros anuales. Los sindicatos deberían aceptar el acuerdo, opinan varios analistas.",
        "text": "",
    }
    cands = heuristic_claims(doc, {"type": "newspaper", "tier": 2, "name": "Diario"})
    assert cands, "debe extraer afirmaciones"
    assert all(quote_supported(c.quote, doc["title"] + "\n" + doc["lede"]) for c in cands)
    levels = {c.level for c in cands}
    assert "data" in levels
    attributed = [c for c in cands if c.attributed_to]
    assert attributed and "ministro" in attributed[0].attributed_to.lower()
    assert any(c.level == "opinion" for c in cands)


def test_persist_claims_drops_unsupported_quote_and_merges_duplicates(db):
    s1 = make_source(db, "diario1")
    s2 = make_source(db, "diario2", bloc="eu", country="FR")
    title = "El Gobierno anuncia una subida del salario mínimo del 5% para el próximo año"
    d1 = make_doc(
        db, s1, title, "La medida afecta a dos millones de trabajadores según el Ministerio de Trabajo."
    )
    d2 = make_doc(db, s2, title, "El Ministerio de Trabajo cifra en dos millones los trabajadores afectados.")
    db.exec(
        "INSERT INTO event(id, title_neutral, first_seen_at, last_update_at) VALUES ('e1', ?, '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')",
        (title,),
    )
    db.exec("UPDATE document SET event_id = 'e1'")
    doc1 = dict(db.one("SELECT * FROM document WHERE id = ?", (d1,)))
    doc2 = dict(db.one("SELECT * FROM document WHERE id = ?", (d2,)))
    fake = ClaimCandidate(
        text="El Gobierno dimite en bloque",
        quote="El Gobierno dimite en bloque",
        level="fact",
        check_worthy=0.9,
    )
    good = ClaimCandidate(text=title, quote=title, level="fact", check_worthy=0.7)
    st1 = persist_claims(db, doc1, {"id": s1, "tier": 2, "type": "newspaper"}, "e1", [good, fake])
    assert st1["new"] == 1 and st1["dropped"] == 1
    assert db.one("SELECT status FROM claim")["status"] == "unverified"
    # misma afirmación canónica, sostenida por una cita distinta (si la cita fuera idéntica, sería copia de agencia)
    quote2 = "El Ministerio de Trabajo cifra en dos millones los trabajadores afectados."
    st2 = persist_claims(
        db,
        doc2,
        {"id": s2, "tier": 2, "type": "newspaper"},
        "e1",
        [ClaimCandidate(text=title, quote=quote2, level="fact", check_worthy=0.7)],
    )
    assert st2["merged"] == 1 and st2["new"] == 0
    assert db.one("SELECT status FROM claim")["status"] == "confirmed"  # 2 fuentes independientes tier ≤ 2
    assert db.scalar("SELECT COUNT(*) FROM claim_revision") == 1


def test_compute_status_rules():
    assert compute_status([{"stance": "supports", "quote": "a", "source_id": "s1", "tier": 1}]) == "confirmed"
    assert (
        compute_status([{"stance": "supports", "quote": "a", "source_id": "s1", "tier": 2}]) == "unverified"
    )
    same = [
        {"stance": "supports", "quote": "misma cita de agencia", "source_id": "s1", "tier": 2},
        {"stance": "supports", "quote": "misma cita de agencia", "source_id": "s2", "tier": 2},
    ]
    assert compute_status(same) == "unverified"  # misma agencia: no independientes
    assert (
        compute_status(
            [
                {"stance": "supports", "quote": "a", "source_id": "s1", "tier": 2},
                {"stance": "refutes", "quote": "b", "source_id": "s2", "tier": 2},
            ]
        )
        == "disputed"
    )


# ───────── GAZETTEER Y DOMINIO ─────────


def test_gazetteer_mentions_and_countries():
    m = find_mentions(
        "El BCE mantiene los tipos mientras Alemania entra en recesión y Francia protesta.",
        "Lagarde advierte a Berlín",
    )
    keys = {x.key for x in m}
    assert "institution:Banco Central Europeo" in keys and "country:DE" in keys and "country:FR" in keys
    assert countries_from_mentions(m)[0] == "DE"
    # siglas ambiguas solo en mayúsculas
    assert "country:US" not in {x.key for x in find_mentions("la usa para cocinar")}
    assert "institution:Reserva Federal" not in {x.key for x in find_mentions("se fed up")}


def test_domain_classifier():
    assert classify_domain("El BCE sube los tipos de interés y la inflación cae") == "economy"
    assert classify_domain("Bombardeo con misiles deja 20 muertos en el frente") == "conflict"
    assert classify_domain("La OMS declara emergencia por el brote de ébola") == "health"


def test_irreversibility_scoring_discounts_future_tense():
    assert irreversibility_score(["El presidente dimite tras el escándalo"]) >= 0.8
    assert irreversibility_score(["El presidente amenaza con dimitir si..."]) < 0.5
    assert irreversibility_score(["Reunión ordinaria del consejo"]) == 0.0


# ───────── MATERIALIDAD ─────────


def test_materiality_single_source_dampened_and_breakdown_present(db):
    s1 = make_source(db, "boe", type="institution", tier=1, country="ES")
    s2 = make_source(db, "pais", tier=2, country="ES")
    s3 = make_source(db, "guardian", tier=2, country="GB", bloc="anglo")
    title = "El Congreso aprueba la ley de presupuestos y entra en vigor mañana"
    for eid, sources in (("single", [s1]), ("multi", [s1, s2, s3])):
        db.exec(
            "INSERT INTO event(id, title_neutral, countries, first_seen_at, last_update_at, n_docs) VALUES (?,?,?, datetime('now'), datetime('now'), ?)",
            (eid, title, '["ES"]', len(sources)),
        )
        for s in sources:
            d = make_doc(db, s, title, "Texto")
            db.exec("UPDATE document SET event_id = ? WHERE id = ?", (eid, d))
    b_single = compute_materiality(db, "single")
    b_multi = compute_materiality(db, "multi")
    assert b_single["single_source"] and not b_multi["single_source"]
    assert b_multi["score"] > b_single["score"]
    assert set(b_multi["contributions"]) >= {
        "power",
        "irreversibility",
        "primary_document",
        "independent_coverage",
    }
    assert b_multi["features"]["primary_document"] == 1.0
    assert db.one("SELECT materiality FROM event WHERE id='multi'")["materiality"] == b_multi["score"]


# ───────── CLUSTERING ─────────


def test_cluster_joins_similar_docs_and_respects_same_source_rule(db):
    from atlas_core.embed import IDF, get_embedder, set_idf
    from atlas_core.engines.cluster import ClusterIndex

    corpus = [
        "noticia cualquiera sobre economía",
        "otra noticia distinta de deportes",
        "el gobierno anuncia medidas",
    ]
    corpus += [
        f"Resolución de 22 de septiembre de 2026, del Ayuntamiento de Ciudad{i}, referente a la convocatoria de plazas"
        for i in range(12)
    ]
    set_idf(IDF.from_texts(corpus))
    emb = get_embedder()
    idx = ClusterIndex(db)
    t1 = "Serbia's president Vučić resigns to run for prime minister"
    t2 = "Serbian President Aleksandar Vucic announces resignation to become prime minister"
    keys = ["country:RS"]
    v1 = emb.embed(t1, extra_tokens=keys)
    v2 = emb.embed(t2, extra_tokens=keys)
    e1, _, created1 = idx.assign(
        "d1", v1, keys, ["RS"], "2026-09-28T10:00:00+00:00", "politics", t1, [], source_id="scmp"
    )
    e2, sim, created2 = idx.assign(
        "d2", v2, keys, ["RS"], "2026-09-28T11:00:00+00:00", "politics", t2, [], source_id="guardian"
    )
    assert created1 and not created2 and e1 == e2 and sim >= idx.theta
    # boilerplate de la misma fuente con otro asunto: no se agrupa
    t3 = "Resolución de 22 de septiembre de 2026, del Ayuntamiento de Ubrique, referente a la convocatoria de una plaza"
    t4 = "Resolución de 22 de septiembre de 2026, del Ayuntamiento de Huesca, referente a la convocatoria de dos plazas"
    e3, _, _ = idx.assign(
        "d3",
        emb.embed(t3, extra_tokens=["country:ES"]),
        ["country:ES"],
        ["ES"],
        "2026-09-28T10:00:00+00:00",
        "law",
        t3,
        [],
        source_id="boe",
    )
    e4, _, created4 = idx.assign(
        "d4",
        emb.embed(t4, extra_tokens=["country:ES"]),
        ["country:ES"],
        ["ES"],
        "2026-09-28T10:00:00+00:00",
        "law",
        t4,
        [],
        source_id="boe",
    )
    assert created4 and e3 != e4
    created, updated = idx.flush()
    assert created == 3 and updated == 0
    assert db.scalar("SELECT COUNT(*) FROM event") == 3
