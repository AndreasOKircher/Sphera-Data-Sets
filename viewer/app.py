import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, abort

import os
from dotenv import load_dotenv
load_dotenv()

from viewer.sections import SECTIONS, DEFAULT_OPEN

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

app = Flask(__name__, **({"template_folder": _TEMPLATE_DIR} if _TEMPLATE_DIR else {}))

app.config["ANTHROPIC_API_KEY"] = os.environ.get("ANTHROPIC_API_KEY", "")


@app.context_processor
def inject_output_dir():
    return {"output_dir": str(OUTPUT_DIR)}


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
