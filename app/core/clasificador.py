"""Clasificador de derivación Yachay.
Sugiere facultad(es), área, carreras relacionadas, confianza y explicación.
No decide la valencia final; solo recomienda para que la Unidad valide.
"""

import json
import re
from pathlib import Path

import numpy as np

from . import config


STOP = set(
    "de la el los las y o a en para con que del por su sus un una al se nos "
    "mi nuestra nuestro como mas más muy le sobre necesito necesitamos quiero "
    "queremos apoyo ayuda comunidad comunal"
    .split()
)

_state = {}


def _seeds_dir() -> Path:
    candidatos = [
        Path(__file__).parents[2] / "seeds",
        Path(__file__).parents[3] / "db" / "seeds",
    ]

    for p in candidatos:
        if p.exists():
            return p

    raise FileNotFoundError("Carpeta seeds no encontrada")


def _facultades_path() -> Path:
    p = _seeds_dir() / "facultades.json"
    if not p.exists():
        raise FileNotFoundError("facultades.json no encontrado")
    return p


def _index_path() -> Path:
    return _seeds_dir() / "facultades_index.json"


def _embeddings_path() -> Path:
    return _seeds_dir() / "facultades_embeddings.npy"


def _construir_texto_facultad(f: dict) -> str:
    facultad = f.get("facultad", "")
    area = f.get("area", "")
    descripcion = f.get("descripcion", "")

    carreras = f.get("carreras", [])
    keywords = f.get("keywords", [])
    ejemplos = f.get("ejemplos", [])

    carreras_txt = ", ".join(carreras)
    keywords_txt = ", ".join(keywords)
    ejemplos_txt = " | ".join(ejemplos)

    return f"""
Facultad: {facultad}
Área académica: {area}
Carreras relacionadas: {carreras_txt}
Casos que puede atender: {descripcion}
Palabras clave: {keywords_txt}
Ejemplos de solicitudes: {ejemplos_txt}
""".strip()


def init():
    """Carga modelo, facultades y embeddings. Llamar en startup."""
    from sentence_transformers import SentenceTransformer

    _state["model"] = SentenceTransformer(config.EMBED_MODEL)

    embeddings_file = _embeddings_path()
    index_file = _index_path()

    if embeddings_file.exists() and index_file.exists():
        _state["facultades"] = json.loads(index_file.read_text(encoding="utf-8"))
        _state["fac_embs"] = np.load(embeddings_file).astype(np.float32)
        print(f"[clasificador] embeddings cargados desde {embeddings_file}")
        return

    # Fallback: si no existen los embeddings, los calcula en memoria.
    facs = json.loads(_facultades_path().read_text(encoding="utf-8"))
    textos = [_construir_texto_facultad(f) for f in facs]

    embs = _state["model"].encode(
        [f"passage: {texto}" for texto in textos],
        normalize_embeddings=True,
    )

    index = []
    for i, f in enumerate(facs):
        index.append(
            {
                "idx": i,
                "facultad": f.get("facultad", ""),
                "area": f.get("area", ""),
                "carreras": f.get("carreras", []),
                "keywords": f.get("keywords", []),
                "descripcion": f.get("descripcion", ""),
                "texto_embedding": textos[i],
            }
        )

    _state["facultades"] = index
    _state["fac_embs"] = np.asarray(embs, dtype=np.float32)

    print("[clasificador] embeddings calculados en memoria")


def embed(texto: str) -> np.ndarray:
    return _state["model"].encode(
        [f"query: {texto}"],
        normalize_embeddings=True,
    )[0]


def _normalizar_texto(texto: str) -> str:
    return str(texto or "").strip().lower()


def _tokens(texto: str) -> list[str]:
    return [
        w
        for w in re.findall(r"[a-záéíóúñü]+", texto.lower())
        if w not in STOP and len(w) > 3
    ]


def _bonus_keywords(texto: str, facultad: dict) -> tuple[float, list[str]]:
    """
    Da un pequeño bonus si el texto contiene keywords explícitas.
    Esto ayuda en casos muy claros como anemia, riego, agua, legal, emprendimiento.
    """
    texto_l = _normalizar_texto(texto)
    keywords = facultad.get("keywords", []) or []

    coincidencias = []
    for kw in keywords:
        kw_l = str(kw).lower().strip()
        if kw_l and kw_l in texto_l:
            coincidencias.append(kw)

    # Bonus moderado para no destruir el score semántico.
    bonus = min(0.08, len(coincidencias) * 0.02)
    return bonus, coincidencias


def _nivel_confianza(top_score: float, margen: float) -> str:
    if top_score >= 0.82 and margen >= 0.06:
        return "alta"
    if top_score >= 0.76:
        return "media"
    return "baja"


def clasificar(texto: str) -> dict:
    """Devuelve facultades sugeridas, área, carreras, explicación y confianza."""
    texto = str(texto or "").strip()

    if not texto:
        return {
            "facultad_top": None,
            "score": 0,
            "facultades_sugeridas": [],
            "sugerencia_valencia": "monovalente",
            "facultades_relevantes": [],
            "explicacion": [],
            "embedding": [],
            "confianza": "baja",
            "requiere_revision": True,
            "motivo_revision": "Texto vacío o insuficiente.",
        }

    q = embed(texto)
    sims = _state["fac_embs"] @ q

    resultados = []
    for i, fac in enumerate(_state["facultades"]):
        score_semantico = float(sims[i])
        bonus, coincidencias = _bonus_keywords(texto, fac)
        score_final = score_semantico + bonus

        resultados.append(
            {
                "facultad": fac.get("facultad", ""),
                "area": fac.get("area", ""),
                "carreras": fac.get("carreras", []),
                "score": round(score_final, 3),
                "score_semantico": round(score_semantico, 3),
                "bonus_keywords": round(bonus, 3),
                "coincidencias": coincidencias,
            }
        )

    resultados = sorted(resultados, key=lambda x: x["score"], reverse=True)

    top = resultados[0]
    second = resultados[1] if len(resultados) > 1 else None

    top_score = top["score"]
    second_score = second["score"] if second else 0
    margen = round(top_score - second_score, 3)

    # Más flexible que 0.02. Para casos comunitarios, muchas necesidades son polivalentes.
    relevantes = [
        r for r in resultados
        if top_score - r["score"] <= 0.05
    ]

    sugerencia_valencia = "polivalente" if len(relevantes) >= 2 else "monovalente"

    confianza = _nivel_confianza(top_score, margen)

    requiere_revision = False
    motivo_revision = ""

    if confianza == "baja":
        requiere_revision = True
        motivo_revision = "La similitud no es suficientemente alta."
    elif sugerencia_valencia == "polivalente":
        requiere_revision = True
        motivo_revision = "Hay más de una facultad cercana; conviene revisión de la Unidad."
    elif margen < 0.04:
        requiere_revision = True
        motivo_revision = "La diferencia entre la primera y segunda facultad es pequeña."

    # Explicabilidad por palabras del usuario vs facultad top.
    fac_emb = _state["fac_embs"][
        next(
            i for i, f in enumerate(_state["facultades"])
            if f.get("facultad") == top["facultad"]
        )
    ]

    palabras = _tokens(texto)
    explicacion = []

    if palabras:
        unicos = list(dict.fromkeys(palabras))[:25]
        w_embs = _state["model"].encode(
            [f"query: {w}" for w in unicos],
            normalize_embeddings=True,
        )
        aportes = np.asarray(w_embs) @ fac_emb
        orden = np.argsort(-aportes)[:5]

        explicacion = [
            {
                "termino": unicos[i],
                "aporte": round(float(aportes[i]), 3),
            }
            for i in orden
        ]

    return {
        "facultad_top": top["facultad"],
        "area_top": top["area"],
        "carreras_top": top["carreras"],
        "score": top["score"],
        "confianza": confianza,
        "margen": margen,
        "facultades_sugeridas": resultados[:4],
        "sugerencia_valencia": sugerencia_valencia,
        "facultades_relevantes": [r["facultad"] for r in relevantes],
        "requiere_revision": requiere_revision,
        "motivo_revision": motivo_revision,
        "explicacion": explicacion,
        "embedding": q.tolist(),
    }