import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, abort

from viewer.sections import SECTIONS, DEFAULT_OPEN

OUTPUT_DIR = Path(__file__).parent.parent / "dataset" / "output"

app = Flask(__name__)


@app.context_processor
def inject_output_dir():
    return {"output_dir": str(OUTPUT_DIR)}


def load_all() -> list[dict]:
    datasets = []
    if not OUTPUT_DIR.exists():
        return datasets
    for f in sorted(OUTPUT_DIR.glob("*.json")):
        try:
            datasets.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"[WARN] skipping {f.name}: {e}", file=sys.stderr)
    return datasets


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
    )


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=True, port=5000)
