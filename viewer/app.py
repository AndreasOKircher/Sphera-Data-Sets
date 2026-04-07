import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, abort, request, jsonify

import os
from dotenv import load_dotenv
load_dotenv()

from viewer.sections import SECTIONS, DEFAULT_OPEN
from core.llm import create_llm_client
from core.chroma_store import query_similar

# When frozen by PyInstaller:
#   - dataset/ lives next to the .exe  (user data, not bundled)
#   - templates/ are extracted into sys._MEIPASS by PyInstaller
if getattr(sys, "frozen", False):
    _BASE         = Path.cwd()
    _TEMPLATE_DIR = str(Path(sys._MEIPASS) / "templates")
else:
    _BASE         = Path(__file__).parent.parent
    _TEMPLATE_DIR = None  # Flask default: templates/ sibling to app.py

OUTPUT_DIR   = _BASE / "dataset" / "output"
ENRICHED_DIR = _BASE / "dataset" / "enriched"
CHROMA_DIR   = _BASE / "dataset" / "chroma"

app = Flask(__name__, **({"template_folder": _TEMPLATE_DIR} if _TEMPLATE_DIR else {}))

def _build_llm_client():
    provider = os.environ.get("LLM_PROVIDER", "anthropic")
    model    = os.environ.get("LLM_MODEL", "claude-haiku-4-5-20251001")
    if provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        return create_llm_client("anthropic", api_key=api_key, model=model) if api_key else None
    if provider == "vio":
        api_key   = os.environ.get("API_TOKEN", "")
        base_url  = os.environ.get("VIO_BASE_URL", "https://vio.automotive-wan.com:446")
        tenant_id = os.environ.get("VIO_TENANT_ID", "default_tenant")
        return create_llm_client("vio", api_key=api_key, model=model,
                                 base_url=base_url, tenant_id=tenant_id) if api_key else None
    return None

app.config["LLM_CLIENT"]   = _build_llm_client()
app.config["LLM_PROVIDER"] = os.environ.get("LLM_PROVIDER", "anthropic")
app.config["LLM_MODEL"]    = os.environ.get("LLM_MODEL", "claude-haiku-4-5-20251001")


@app.context_processor
def inject_output_dir():
    configured = app.config["LLM_CLIENT"] is not None
    return {
        "output_dir":   str(OUTPUT_DIR),
        "llm_provider": app.config["LLM_PROVIDER"],
        "llm_model":    app.config["LLM_MODEL"],
        "llm_configured": configured,
    }


def load_all() -> list[dict]:
    datasets = []
    if not OUTPUT_DIR.exists():
        return datasets
    for f in sorted(OUTPUT_DIR.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            enriched = load_enriched(d.get("uuid", ""))
            d["_summary"] = enriched.get("technology_description_summary", "")
            datasets.append(d)
        except Exception as e:
            print(f"[WARN] skipping {f.name}: {e}", file=sys.stderr)
    return datasets


def load_enriched(uuid: str) -> dict:
    path = ENRICHED_DIR / f"{uuid}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] could not read enriched {path.name}: {e}", file=sys.stderr)
        return {}


def load_one(uuid: str) -> dict | None:
    path = OUTPUT_DIR / f"{uuid}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] could not read {path.name}: {e}", file=sys.stderr)
        return None


@app.route("/")
def index():
    datasets = load_all()
    return render_template("index.html", datasets=datasets)


@app.route("/dataset/<uuid>")
def dataset_detail(uuid):
    data = load_one(uuid)
    if data is None:
        abort(404)
    return render_template(
        "dataset.html",
        data=data,
        sections=SECTIONS,
        default_open=DEFAULT_OPEN,
        enriched=load_enriched(uuid),
    )


@app.route("/query", methods=["POST"])
def query():
    body = request.get_json(silent=True) or {}
    question = body.get("question", "").strip()
    uuids = body.get("uuids")

    if not question:
        return jsonify({"error": "question is required"}), 400
    if not uuids:
        return jsonify({"error": "uuids is required"}), 400

    llm_client = app.config.get("LLM_CLIENT")
    if llm_client is None:
        return jsonify({"error": "LLM client not configured"}), 503

    all_datasets = load_all()
    uuid_set = set(uuids)
    selected = [d for d in all_datasets if d.get("uuid") in uuid_set]
    if not selected:
        return jsonify({"error": "No matching datasets found for provided uuids"}), 400

    fields = body.get("fields") or None

    try:
        from viewer.query import run_query
        results = run_query(question, selected, client=llm_client, fields=fields)
        return jsonify({"results": results})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/search", methods=["POST"])
def search():
    body = request.get_json(silent=True) or {}
    question = body.get("question", "").strip()
    if not question:
        return jsonify({"error": "question is required"}), 400

    filters = body.get("filters") or None

    results = query_similar(
        question,
        chroma_path=CHROMA_DIR,
        n_results=20,
        where=filters,
    )
    uuids = [r["uuid"] for r in results]
    return jsonify({"uuids": uuids, "matches": results})


@app.route("/chat", methods=["POST"])
def chat():
    body = request.get_json(silent=True) or {}
    question = body.get("question", "").strip()
    uuids = body.get("uuids")
    history = body.get("history") or []

    if not question:
        return jsonify({"error": "question is required"}), 400
    if not uuids:
        return jsonify({"error": "uuids is required"}), 400

    llm_client = app.config.get("LLM_CLIENT")
    if llm_client is None:
        return jsonify({"error": "LLM client not configured"}), 503

    all_datasets = load_all()
    uuid_set = set(uuids)
    selected = [d for d in all_datasets if d.get("uuid") in uuid_set]
    if not selected:
        return jsonify({"error": "No matching datasets found"}), 400

    fields = body.get("fields") or None
    try:
        from viewer.query import run_query
        results = run_query(question, selected, client=llm_client,
                            fields=fields, history=history)
        uuid_to_meta = {d["uuid"]: d for d in selected}
        for r in results:
            meta = uuid_to_meta.get(r.get("uuid"), {})
            r["location"] = meta.get("location", "")
            r["process_type"] = meta.get("process_type", "")
        return jsonify({"results": results})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/shutdown", methods=["POST"])
def shutdown():
    import os
    os._exit(0)


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    import threading
    import webbrowser

    def _open_browser():
        webbrowser.open("http://localhost:5000")

    print("=" * 48)
    print("  Sphera LCA Viewer")
    print("  http://localhost:5000")
    print("  Press Ctrl+C to stop.")
    print("=" * 48)

    # Open browser after Flask has had time to start
    threading.Timer(1.5, _open_browser).start()

    # debug=False is required when running as a PyInstaller bundle
    app.run(debug=False, port=5000)
