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


def test_diff_keeps_short_sentences_and_table_lines():
    """Las frases cortas con cifras (tablas de tipos de un banco central) no pueden desaparecer del diff."""
    d = diff_documents(
        "El tipo de depósito queda en el 2,00%. Sin cambios.",
        "El tipo de depósito queda en el 2,00%. Sube 25 pb.",
    )
    assert d["n_changed"] == 1 and d["summary"] != "Sin cambios de texto."
    assert any("25 pb" in (m["new"] or "") for m in d["material_changes"])

    d = diff_documents(
        "Facilidad de depósito: 2,00%. Tipo principal: 2,15%.",
        "Facilidad de depósito: 1,75%. Tipo principal: 1,90%.",
    )
    assert d["n_old"] == d["n_new"] == 2
    assert [m["new"] for m in d["material_changes"]] == [
        "Facilidad de depósito: 1,75%.",
        "Tipo principal: 1,90%.",
    ]

    d = diff_documents(
        "Facilidad de depósito: 2,00%\nTipo principal: 2,15%\nFacilidad marginal: 2,40%",
        "Facilidad de depósito: 1,75%\nTipo principal: 1,90%\nFacilidad marginal: 2,40%",
    )
    assert d["n_old"] == 3 and d["n_changed"] == 2
    assert {m["new"] for m in d["material_changes"]} == {
        "Facilidad de depósito: 1,75%",
        "Tipo principal: 1,90%",
    }


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
    assert irreversibility_score(["El presidente podría presentar su dimisión"]) < 0.5
    assert irreversibility_score(["Prime minister could be ousted by his own party"]) < 0.5
    assert irreversibility_score(["Reunión ordinaria del consejo"]) == 0.0


def test_irreversibility_ignores_month_may_and_markers_in_other_clauses():
    assert irreversibility_score(["Prime minister resigns on May 12 after corruption scandal"]) == 0.8
    assert (
        irreversibility_score(["Vučić resigns to run for PM. His term would otherwise end in May next year."])
        == 0.8
    )
    assert irreversibility_score(["El presidente dimite. La oposición pide elecciones anticipadas"]) == 0.8
    assert irreversibility_score(["El presidente dimite y la oposición pide elecciones anticipadas"]) == 0.8
    assert irreversibility_score(["Dimite el ministro."]) == 0.8  # título corto, no debe descartarse
    assert irreversibility_score(["Fed May Cut Rates, analysts say"]) < 0.5  # aquí "may" sí es modal


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


def test_materiality_is_idempotent_after_its_own_deltas(db):
    """Los deltas que deltas_from_event deriva del propio título no realimentan Δstate; uno externo sí."""
    from atlas_core.db import new_id, now_iso
    from atlas_core.engines.state import _variable_id, deltas_from_event

    s1 = make_source(db, "pais", tier=2, country="ES")
    s2 = make_source(db, "mundo", tier=2, country="ES")
    title = "El presidente dimite tras el escándalo"
    d1 = make_doc(db, s1, title, "Texto")
    d2 = make_doc(db, s2, title, "Texto")
    db.exec(
        "INSERT INTO event(id, title_neutral, countries, first_seen_at, last_update_at, n_docs, lead_document_id) VALUES ('e1', ?, '[\"ES\"]', ?, ?, 2, ?)",
        (title, now_iso(), now_iso(), d1),
    )
    db.exec("UPDATE document SET event_id = 'e1' WHERE id IN (?, ?)", (d1, d2))
    first = compute_materiality(db, "e1")
    assert first["features"]["irreversibility"] >= 0.7 and first["features"]["delta_state"] == 0.0
    assert (
        deltas_from_event(db, "e1") == 1
    )  # POWER.head_of_government, con source_doc_id = documento del evento
    again = compute_materiality(db, "e1")
    assert again["score"] == first["score"] and again["features"]["delta_state"] == 0.0
    assert deltas_from_event(db, "e1") == 0 and compute_materiality(db, "e1")["score"] == first["score"]
    # un delta con procedencia externa (serie de mercado enlazada al evento) sí mueve la variable de estado
    vid = _variable_id(db, "ES", "fx_vs_usd", create=True)
    db.exec(
        "INSERT INTO state_delta(id, variable_id, event_id, detected_at, magnitude, description) VALUES (?,?,?,?,?,?)",
        (new_id(), vid, "e1", now_iso(), 2.5, "EURUSD=X: -2.5%"),
    )
    ext = compute_materiality(db, "e1")
    assert ext["features"]["delta_state"] == 0.5 and ext["score"] > first["score"]


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


def _hours_ago(h: float) -> str:
    from datetime import UTC, datetime, timedelta

    return (datetime.now(UTC) - timedelta(hours=h)).replace(microsecond=0).isoformat()


def test_cluster_first_seen_at_is_oldest_document_not_first_processed(db):
    """El lote se procesa del más reciente al más antiguo: first_seen_at debe retroceder al documento más antiguo
    y la novedad calcularse sobre la edad real del evento."""
    from atlas_core.embed import get_embedder
    from atlas_core.engines.cluster import ClusterIndex

    title = "El Consejo Europeo aprueba el nuevo paquete de sanciones contra Rusia"
    keys = ["institution:Unión Europea", "country:RU"]
    vec = get_embedder().embed(title, extra_tokens=keys)
    idx = ClusterIndex(db)
    stamps = [_hours_ago(1), _hours_ago(36), _hours_ago(60)]
    sources = [make_source(db, f"src{i}", country="FR", bloc="eu") for i in range(3)]
    docs = [make_doc(db, s, title, "Texto", published_at=ts) for s, ts in zip(sources, stamps, strict=True)]
    eids = {
        idx.assign(d, vec, keys, ["RU"], ts, "politics", title, [], source_id=s)[0]
        for d, ts, s in zip(docs, stamps, sources, strict=True)
    }
    assert len(eids) == 1
    eid = eids.pop()
    idx.flush()
    ev = db.one("SELECT first_seen_at, last_update_at FROM event WHERE id = ?", (eid,))
    assert ev["first_seen_at"] == stamps[2] and ev["last_update_at"] == stamps[0]
    db.exec("UPDATE document SET event_id = ? WHERE id IN (?,?,?)", (eid, *docs))
    novelty = compute_materiality(db, eid)["features"]["novelty"]
    assert novelty == round(1 - (59 - 24) / 144, 3)
    # segunda pasada sobre el índice recargado: un documento aún más antiguo también retrocede la fecha
    idx2 = ClusterIndex(db)
    older = _hours_ago(70)
    d4 = make_doc(db, make_source(db, "src9", country="FR", bloc="eu"), title, "Texto", published_at=older)
    assert idx2.assign(d4, vec, keys, ["RU"], older, "politics", title, [], source_id="src9")[0] == eid
    idx2.flush()
    assert db.one("SELECT first_seen_at FROM event WHERE id = ?", (eid,))["first_seen_at"] == older


def _seed_event_pair(db, keys_win: list[str], keys_lose: list[str]):
    import numpy as np

    from atlas_core.db import dumps, now_iso, vec_to_blob
    from atlas_core.embed import DIM, get_embedder

    s1, s2 = make_source(db, "c1"), make_source(db, "c2")
    v = np.zeros(DIM, dtype=np.float32)
    v[:8] = 1.0
    now = now_iso()
    for eid, n, keys, first in (("win", 2, keys_win, now), ("lose", 1, keys_lose, _hours_ago(30))):
        db.exec(
            "INSERT INTO event(id,title_neutral,countries,entity_keys,first_seen_at,last_update_at,n_docs,centroid,embedding_model) VALUES (?,?,?,?,?,?,?,?,?)",
            (eid, eid, dumps(["ES"]), dumps(keys), first, now, n, vec_to_blob(v), get_embedder().name),
        )
    d1, d2 = make_doc(db, s1, "A"), make_doc(db, s2, "B")
    d3 = make_doc(db, s2, "C", published_at=_hours_ago(30))
    db.exec("UPDATE document SET event_id='win', embedding=? WHERE id IN (?,?)", (vec_to_blob(v), d1, d2))
    db.exec("UPDATE document SET event_id='lose', embedding=? WHERE id=?", (vec_to_blob(v), d3))
    db.exec(
        "INSERT INTO claim(id,event_id,document_id,text_canonical,level,status,extracted_by,created_at) VALUES ('k1','lose',?,'x','fact','unverified','heuristic',?)",
        (d3, now),
    )
    return d1, d2, d3


def test_consolidate_merges_duplicate_events_and_keeps_history(db):
    from atlas_core.db import new_id, now_iso
    from atlas_core.engines.cluster import consolidate_events

    d1, d2, d3 = _seed_event_pair(db, ["country:ES"], ["country:ES"])
    db.exec("INSERT INTO event_document(event_id, document_id, similarity) VALUES ('lose', ?, 0.9)", (d3,))
    db.exec(
        "INSERT INTO state_variable(id, scope, dimension, key) VALUES ('sv1','ES','POWER','head_of_government')"
    )
    db.exec(
        "INSERT INTO state_delta(id, variable_id, event_id, detected_at, magnitude, description, source_doc_id) VALUES (?,?,?,?,?,?,?)",
        (new_id(), "sv1", "lose", now_iso(), 1.0, "x", d3),
    )
    db.exec(
        "INSERT INTO business_unit(id, name) VALUES ('b1', 'Negocio')",
    )
    db.exec(
        "INSERT INTO exposure_alert(id, business_id, event_id, channel, explanation, confidence, created_at) VALUES ('ea1','b1','lose','tax','x',0.7,?)",
        (now_iso(),),
    )
    db.exec(
        "INSERT INTO forecast_question(id, title, resolution_criteria, open_at, close_at, origin_event_id) VALUES ('q1','t','c',?,?,'lose')",
        (now_iso(), now_iso()),
    )
    res = consolidate_events(db, hours=48)
    assert res["merged"] == 1 and res["winners"] == ["win"]
    lose = db.one("SELECT status, merged_into FROM event WHERE id='lose'")
    assert lose["status"] == "merged" and lose["merged_into"] == "win"  # nunca se borra historia
    assert db.scalar("SELECT COUNT(*) FROM document WHERE event_id='win'") == 3
    assert db.scalar("SELECT COUNT(*) FROM document WHERE event_id='lose'") == 0
    assert db.one("SELECT event_id FROM claim WHERE id='k1'")["event_id"] == "win"
    assert db.one("SELECT event_id FROM state_delta")["event_id"] == "win"
    assert db.one("SELECT event_id FROM exposure_alert WHERE id='ea1'")["event_id"] == "win"
    assert db.one("SELECT origin_event_id FROM forecast_question WHERE id='q1'")["origin_event_id"] == "win"
    assert db.one("SELECT event_id FROM event_document WHERE document_id=?", (d3,))["event_id"] == "win"
    win = db.one("SELECT n_docs, first_seen_at, last_update_at FROM event WHERE id='win'")
    assert win["n_docs"] == 3
    # el ganador adopta la fecha más antigua (del perdedor y de su documento) sin perder la más reciente
    assert (
        win["first_seen_at"] == db.one("SELECT published_at FROM document WHERE id=?", (d3,))["published_at"]
    )
    assert (
        win["last_update_at"] == db.one("SELECT published_at FROM document WHERE id=?", (d1,))["published_at"]
    )
    assert consolidate_events(db, hours=48)["merged"] == 0  # idempotente


def test_consolidate_does_not_merge_events_with_disjoint_entities(db):
    from atlas_core.engines.cluster import consolidate_events

    _seed_event_pair(db, ["country:ES"], ["country:FR"])
    assert consolidate_events(db, hours=48)["merged"] == 0
    assert db.scalar("SELECT COUNT(*) FROM event WHERE status = 'merged'") == 0
    assert db.one("SELECT event_id FROM claim WHERE id='k1'")["event_id"] == "lose"


# ───────── MANDO: exposición ─────────


def test_exposure_alert_for_business_unit_explains_channel(seeded):
    from atlas_core.db import dumps, now_iso
    from atlas_core.engines.exposure import evaluate_event

    s = make_source(seeded, "boe_x", type="institution", tier=1)
    title = "Hacienda aprueba la ley del impuesto de sociedades para centros de formación profesional y certificación"
    d = make_doc(
        seeded,
        s,
        title,
        "La norma fiscal afecta a la formación y a la educación universitaria; el reglamento entra en vigor.",
    )
    seeded.exec(
        "INSERT INTO event(id,title_neutral,countries,first_seen_at,last_update_at,n_docs,materiality,lead_document_id) VALUES ('ex1',?,?,?,?,1,55,?)",
        (title, dumps(["ES"]), now_iso(), now_iso(), d),
    )
    alerts = evaluate_event(seeded, "ex1")
    assert {a["channel"] for a in alerts} == {"regulatory", "tax"}
    assert all(
        "Formación de pruebas" in a["business_name"] and 0.6 <= a["confidence"] <= 0.95 for a in alerts
    )
    assert all("canal" in a["explanation"] and "Jurisdicción coincide" in a["explanation"] for a in alerts)
    reg = next(a for a in alerts if a["channel"] == "regulatory")
    assert "ley" in reg["explanation"] and "formación profesional" in reg["explanation"]
    assert seeded.scalar("SELECT COUNT(*) FROM exposure_alert WHERE event_id='ex1'") == 2
    # upsert: reevaluar no duplica
    assert (
        len(evaluate_event(seeded, "ex1")) == 2 and seeded.scalar("SELECT COUNT(*) FROM exposure_alert") == 2
    )
    seeded.exec("UPDATE event SET materiality = 10 WHERE id='ex1'")
    assert evaluate_event(seeded, "ex1") == []  # MIN_MATERIALITY


def test_exposure_ignores_substring_matches_inside_words(seeded):
    """«ema» dentro de «alemán» y «ley» dentro de «leyenda» no son términos del sector ni del canal (caso real:
    documental de Schumacher → alerta regulatoria de un negocio biotech)."""
    from atlas_core.db import dumps, now_iso
    from atlas_core.engines.exposure import evaluate_event

    s = make_source(seeded, "prensa_x", country="DE", bloc="eu")
    title = "Llega a Netflix un nuevo documental de Schumacher en el que actualiza su estado de salud"
    d = make_doc(
        seeded,
        s,
        title,
        "El piloto alemán, leyenda de la Fórmula 1, aparece por primera vez desde el accidente. Sistema y problema, importante reporte.",
    )
    seeded.exec(
        "INSERT INTO event(id,title_neutral,countries,first_seen_at,last_update_at,n_docs,materiality,lead_document_id) VALUES ('ex2',?,?,?,?,1,38.8,?)",
        (title, dumps(["DE"]), now_iso(), now_iso(), d),
    )
    assert evaluate_event(seeded, "ex2") == []
    assert seeded.scalar("SELECT COUNT(*) FROM exposure_alert") == 0


# ───────── ESTADO: deltas de mercado ─────────


def _fx_history(vals: list[float]) -> str:
    import json

    return json.dumps([{"t": f"2026-09-{20 + i:02d}T00:00:00+00:00", "v": v} for i, v in enumerate(vals)])


def test_fx_deltas_direction_threshold_and_dedup(seeded):
    from atlas_core.db import now_iso
    from atlas_core.engines.state import deltas_from_markets

    observed = "2026-09-26T00:00:00+00:00"
    for sym, vals in (
        ("USDTRY=X", [30, 30.2, 30.5, 30.7, 30.8, 30.9, 30.93]),  # +2.4 % → lira se deprecia
        ("EURUSD=X", [1.10, 1.09, 1.08, 1.07, 1.07, 1.065, 1.066]),  # −2.2 % → euro se deprecia
        ("USDBRL=X", [5.0, 5.0, 5.01, 5.0, 5.02, 5.01, 5.02]),  # +0.4 % → sin delta
    ):
        seeded.exec(
            "INSERT INTO market_quote(symbol,label,group_name,price,observed_at,fetched_at,source,history) VALUES (?,?,?,?,?,?,?,?)",
            (sym, sym, "fx", vals[-1], observed, now_iso(), "test", _fx_history(vals)),
        )
    assert deltas_from_markets(seeded) == 2
    ds = [r["description"] for r in seeded.all("SELECT description FROM state_delta ORDER BY description")]
    assert ds[0].startswith("EURUSD=X: -2.2%") and "se deprecia" in ds[0]
    assert ds[1].startswith("USDTRY=X: +2.4%") and "se deprecia" in ds[1]
    assert deltas_from_markets(seeded) == 0  # dedup 6 días
    assert seeded.scalar("SELECT COUNT(*) FROM state_observation") == 3


def test_fx_every_mapped_symbol_records_observation(seeded):
    from atlas_core.db import now_iso
    from atlas_core.engines.state import FX_SYMBOL_TO_COUNTRY, deltas_from_markets

    flat = _fx_history([100.0] * 7)
    for sym in FX_SYMBOL_TO_COUNTRY:
        seeded.exec(
            "INSERT INTO market_quote(symbol,label,group_name,price,fetched_at,source,history) VALUES (?,?,?,?,?,?,?)",
            (sym, sym, "fx", 100.0, now_iso(), "test", flat),
        )
    assert deltas_from_markets(seeded) == 0  # variación 0 %: sin deltas
    scopes = {
        r["scope"]
        for r in seeded.all(
            "SELECT sv.scope FROM state_observation o JOIN state_variable sv ON sv.id = o.variable_id WHERE sv.key = 'fx_vs_usd'"
        )
    }
    assert scopes == set(FX_SYMBOL_TO_COUNTRY.values())  # incluye JP, que no es de nivel A
