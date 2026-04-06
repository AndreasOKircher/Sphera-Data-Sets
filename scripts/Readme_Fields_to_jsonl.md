# make_jsonl.py

Batch-convert enriched JSON technology records into a JSONL file suitable for RAG pipelines and vector embedding, using `uuid` as the stable document ID and a labeled text field as embedding input.

---

## Idea

This script is designed to:

- Collect many `.json` files from a directory, wildcard pattern, or tree.
- Extract a subset of semantically relevant fields:
  - `name_base`
  - `name_treatment_standards_routes`
  - `synonyms`
  - `technology_description`
  - `general_comment`
  - `uuid`
- Build a **single text field** per record that is good embedding input by concatenating these fields with labels.
- Write one record per line as JSONL with a stable `id` (= `uuid`) and the combined `text` field for use in a RAG/vector store.

This gives you a clean, minimal dataset for embedding and retrieval while still retaining the original fields as structured metadata.

---

## Implementation

### Input collection

- Accepts:
  - A directory path
  - A single file
  - A wildcard pattern (e.g. `.\dataset\output\*.json`)
- Optional recursive traversal (`-r/--recursive`) to scan subdirectories for `*.json`.
- Deduplicates files by absolute path.

### JSON processing

For each JSON file:

1. Load the file as a single JSON object.
2. Extract:
   - `uuid` (required)
   - `name_base`
   - `technology_description`
   - `general_comment`
   - `name_treatment_standards_routes`
   - `synonyms`
3. Normalize values:
   - `None` stays `None`
   - Lists are joined with `", "`
   - Other values are converted to stripped strings
4. Build `text` as labeled sections, e.g.:

   ```text
   name_base: Aluminium sheet (AlMg3) primary

   name_treatment_standards_routes: hot rolling and cutting, primary production

   synonyms: AlMg3, EN AW-5754, Wrought alloy

   technology_description: There are two ways of producing primary aluminium alloys: ...

   general_comment: This dataset uses an ingot consumption mix as input. ...
   ```

5. If `uuid` is missing, or the resulting `text` is empty, the file is skipped with a reason printed to stderr.

### Output format

Each successfully processed file produces **one JSON object per line** (JSONL):

```json
{
  "id": "<uuid>",
  "text": "<combined labeled text>",
  "fields": {
    "name_base": "...",
    "technology_description": "...",
    "general_comment": "...",
    "name_treatment_standards_routes": "...",
    "synonyms": "...",
    "uuid": "<uuid>"
  }
}
```

- `id`: used as document key in vector DBs; equals `uuid`.
- `text`: used as embedding input.
- `fields`: preserved original fields for downstream filtering/metadata.

### Progress and stats

- Uses a terminal progress bar (`tqdm`) over input files.
- At the end prints:
  - Total input files scanned
  - Records written
  - Files skipped
  - Breakdown of skip reasons:
    - parse errors
    - missing `uuid`
    - empty text

---

## Requirements

- Python 3.10+ (for type hints like `list[str]`).
- Packages:
  - `tqdm`

Install dependencies:

```bash
pip install tqdm
```

---

## Usage

From the directory containing `make_jsonl.py`:

### Basic usage (defaults)

```bash
python make_jsonl.py
```

Defaults:

- Input: `.\dataset\output`
- Output: `.\dataset\jsonl\dataset.jsonl`
- Encoding: `utf-8`
- Non-recursive directory scan

### Recursive scan

Scan subdirectories for `*.json`:

```bash
python make_jsonl.py -r
```

### Custom input path

Input can be a directory, a single file, or a wildcard:

```bash
# Directory
python make_jsonl.py -i .\dataset\output

# Wildcard pattern
python make_jsonl.py -i ".\dataset\output\*.json"

# Single file
python make_jsonl.py -i ".\dataset\output\some_file.json"
```

### Custom output path

```bash
python make_jsonl.py -o ".\dataset\jsonl\my_tech_dataset.jsonl"
```

Combine options:

```bash
python make_jsonl.py \
  -i ".\dataset\output\*.json" \
  -o ".\dataset\jsonl\dataset.jsonl" \
  -r
```

### Encoding

If your JSON files use a different encoding:

```bash
python make_jsonl.py --encoding "latin-1"
```

### Help

```bash
python make_jsonl.py --help
```

Shows full usage, arguments, and examples.

---

## Integration into a RAG pipeline

Typical steps:

1. Run `make_jsonl.py` to produce `dataset.jsonl`.
2. For each line:
   - Parse JSON.
   - Embed `record["text"]`.
   - Store in your vector DB with:
     - `id = record["id"]`
     - `embedding = <vector>`
     - `metadata = record["fields"]`
3. At query time, embed the query, retrieve by vector similarity, and use the `fields` metadata for display or reranking.

Because the script outputs JSONL with `id` and a single `text` field, it is straightforward to plug into most vector DBs and RAG frameworks.