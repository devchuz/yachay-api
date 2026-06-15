import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer


ROOT = Path(__file__).resolve().parents[1]
SEEDS_DIR = ROOT / "seeds"

FACULTADES_PATH = SEEDS_DIR / "facultades.json"
INDEX_PATH = SEEDS_DIR / "facultades_index.json"
EMBEDDINGS_PATH = SEEDS_DIR / "facultades_embeddings.npy"

MODEL_NAME = "intfloat/multilingual-e5-small"


def construir_texto_facultad(f: dict) -> str:
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


def main():
    if not FACULTADES_PATH.exists():
        raise FileNotFoundError(f"No encontré {FACULTADES_PATH}")

    facultades = json.loads(FACULTADES_PATH.read_text(encoding="utf-8"))

    textos = [construir_texto_facultad(f) for f in facultades]

    print(f"Modelo: {MODEL_NAME}")
    print(f"Facultades a embeber: {len(textos)}")

    model = SentenceTransformer(MODEL_NAME)

    embeddings = model.encode(
        [f"passage: {texto}" for texto in textos],
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    np.save(EMBEDDINGS_PATH, np.asarray(embeddings, dtype=np.float32))

    index = []
    for i, f in enumerate(facultades):
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

    INDEX_PATH.write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"OK embeddings guardados en: {EMBEDDINGS_PATH}")
    print(f"OK índice guardado en: {INDEX_PATH}")


if __name__ == "__main__":
    main()