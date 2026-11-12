"""Compile a bounded comparison instrument; never eval worker-supplied code."""
from __future__ import annotations

import base64
import hashlib
import html
import json
from html.parser import HTMLParser

class Denied(ValueError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


MAX_SOURCE_BYTES = 512_000
MAX_ROWS = 500
MAX_FIELDS = 30


def load_records(data):
    if len(data) > MAX_SOURCE_BYTES:
        raise Denied("Source exceeds this prototype's 512 KB input limit")
    records = json.loads(data)
    if not isinstance(records, list) or not 2 <= len(records) <= MAX_ROWS:
        raise Denied("Supply 2 to 500 flat civilian-resource records")
    fields = []
    for row in records:
        if not isinstance(row, dict) or not row:
            raise Denied("Each source row must be a non-empty JSON object")
        for key, value in row.items():
            if not isinstance(key, str) or not 1 <= len(key) <= 100:
                raise Denied("Field names must contain 1 to 100 characters")
            if value is not None and (not isinstance(value, str) or len(value) > 5000):
                raise Denied("Values must be strings or null; no type coercion is permitted")
            if key not in fields:
                fields.append(key)
    if not 2 <= len(fields) <= MAX_FIELDS:
        raise Denied("Supply records with 2 to 30 distinct fields")
    return records, fields


def research(records, fields):
    missing = [
        {"row_index": index, "field": field,
         "locator": "/" + str(index) + "/" + field.replace("~", "~0").replace("/", "~1"),
         "observation": "missing" if field not in row else "null" if row[field] is None else "empty"}
        for index, row in enumerate(records) for field in fields
        if field not in row or row[field] is None or row[field] == ""
    ]
    return {
        "record_count": len(records), "fields": fields, "missing_observations": missing,
        "comparison_observation": "The supplied rows have multiple fields; comparison currently requires inspecting the source records.",
        "interpretation": "A searchable, printable comparison view may help the person compare these supplied records.",
        "interpretation_pf": 0,
        "existing_tool_assessment": "Raw JSON is available. No mission-specific comparison instrument has been admitted in this new mission; no claim is made about all external tools.",
    }


def validate_spec(spec, fields):
    if not isinstance(spec, dict) or set(spec) != {"kind", "version", "title", "columns", "missing_label"}:
        raise Denied("Only the admitted comparison instrument schema is accepted")
    if spec["kind"] != "offline_record_comparator" or spec["version"] != 1 or type(spec["version"]) is not int:
        raise Denied("Unsupported instrument kind/version")
    if not isinstance(spec["title"], str) or not 1 <= len(spec["title"]) <= 150:
        raise Denied("Instrument title must contain 1 to 150 characters")
    if not isinstance(spec["columns"], list) or spec["columns"] != fields:
        raise Denied("This admission profile requires all fields in original first-seen order")
    if spec["missing_label"] != "Not provided":
        raise Denied("Missing values must remain explicitly labelled")
    return spec


SCRIPT = r'''"use strict";
const source = JSON.parse(document.getElementById("source-data").textContent);
const columns = JSON.parse(document.getElementById("column-data").textContent);
const body = document.querySelector("tbody");
const search = document.getElementById("search");
const sort = document.getElementById("sort");
const count = document.getElementById("count");
const valueAt = (row, key) => Object.prototype.hasOwnProperty.call(row, key) ? row[key] : undefined;
function render() {
  const needle = search.value.toLocaleLowerCase();
  let rows = source.filter(row => columns.some(key => String(valueAt(row, key) ?? "").toLocaleLowerCase().includes(needle)));
  if (sort.value !== "") {
    const key = columns[Number(sort.value)];
    rows = rows.slice().sort((a, b) => String(valueAt(a, key) ?? "").localeCompare(String(valueAt(b, key) ?? "")));
  }
  body.replaceChildren();
  for (const row of rows) {
    const tr = document.createElement("tr");
    for (const key of columns) {
      const td = document.createElement("td");
      const value = valueAt(row, key);
      td.textContent = value === undefined || value === null || value === "" ? "Not provided" : value;
      if (value === undefined || value === null || value === "") td.className = "missing";
      tr.append(td);
    }
    body.append(tr);
  }
  count.textContent = `${rows.length} of ${source.length} records shown`;
}
search.addEventListener("input", render);
sort.addEventListener("change", render);
document.getElementById("print").addEventListener("click", () => window.print());
render();'''


def script_json(value):
    return json.dumps(value, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def compile_instrument(spec, records, source_sha256):
    fields = list(dict.fromkeys(key for row in records for key in row))
    validate_spec(spec, fields)
    script_hash = base64.b64encode(hashlib.sha256(SCRIPT.encode()).digest()).decode()
    title = html.escape(spec["title"])
    headers = "".join("<th scope=\"col\">" + html.escape(field) + "</th>" for field in fields)
    options = "".join(f'<option value="{i}">{html.escape(field)}</option>' for i, field in enumerate(fields))
    document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'sha256-{script_hash}'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>{title}</title><style>
:root{{color-scheme:light;font:16px system-ui,sans-serif;color:#172d33;background:#f5f4ee}}
body{{max-width:1200px;margin:auto;padding:32px}}h1{{font-size:2rem}}label{{display:block;margin:12px 0}}
input,select,button{{font:inherit;padding:10px;border:1px solid #52696f;border-radius:5px;background:white}}
input{{width:min(90%,500px)}}table{{width:100%;border-collapse:collapse;background:white}}
th,td{{border:1px solid #bcc6c8;padding:12px;text-align:left;vertical-align:top;overflow-wrap:anywhere}}
th{{background:#173d46;color:white}}.missing{{font-style:italic;color:#5a4a40}}.scroll{{overflow:auto}}
.context{{padding:16px;border-left:4px solid #17746c;background:#e7eeea}}small{{overflow-wrap:anywhere}}
@media print{{.controls{{display:none}}body{{padding:0;background:white}}th{{color:black;background:white}}}}
</style></head><body>
<h1>{title}</h1><p class="context">Working copy of supplied records. This tool preserves what the records say; it does not confirm the listed information. Missing information stays visible.</p>
<div class="controls"><label for="search">Find a word in the supplied records</label><input id="search" type="search" autocomplete="off">
<label for="sort">Sort records</label><select id="sort"><option value="">Original source order</option>{options}</select>
<button id="print" type="button">Print this view</button></div>
<p id="count" aria-live="polite"></p><div class="scroll"><table><thead><tr>{headers}</tr></thead><tbody></tbody></table></div>
<noscript>Enable JavaScript to use this comparison view. The unmodified source records are included in the handover package.</noscript>
<p><small>Source SHA-256: {source_sha256}. Compare with source.json and manifest.json in the handover.</small></p>
<script id="source-data" type="application/json">{script_json(records)}</script>
<script id="column-data" type="application/json">{script_json(fields)}</script>
<script>{SCRIPT}</script></body></html>'''
    return document.encode("utf-8")


class InstrumentParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = None
        self.values = {}
        self.executable_scripts = []
        self.csp = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta" and attrs.get("http-equiv") == "Content-Security-Policy":
            self.csp = attrs["content"]
        if tag == "script":
            self.active = attrs.get("id", "executable")
            if "src" in attrs:
                raise Denied("External scripts are outside the instrument profile")

    def handle_data(self, data):
        if self.active:
            self.values[self.active] = self.values.get(self.active, "") + data

    def handle_endtag(self, tag):
        if tag == "script":
            if self.active == "executable":
                self.executable_scripts.append(self.values.pop("executable", ""))
            self.active = None


def verify_instrument(document, source_bytes, spec):
    """Check compiled data independently against original bytes before admission."""
    source = json.loads(source_bytes)
    columns = []
    for row in source:
        for key in row:
            if key not in columns:
                columns.append(key)
    parsed = InstrumentParser()
    parsed.feed(document.decode("utf-8"))
    checks = {
        "source_rows_preserved": json.loads(parsed.values.get("source-data", "null")) == source,
        "every_field_preserved": json.loads(parsed.values.get("column-data", "null")) == columns == spec["columns"],
        "only_admitted_script": parsed.executable_scripts == [SCRIPT],
        "network_disabled_by_csp": parsed.csp is not None and "default-src 'none'" in parsed.csp,
        "source_digest_visible": digest(source_bytes) in document.decode("utf-8"),
    }
    return {
        "rule_id": "exact-row-preservation-v1", "passed": all(checks.values()),
        "checks": checks, "source_sha256": digest(source_bytes), "instrument_sha256": digest(document),
        "observation_scope": "Embedded data, field coverage, declared script, and document policy. Browser interaction is a separate check.",
        "record_count": len(source), "column_count": len(columns),
    }


def guide(spec):
    return ("THE ATOMITON — COMPARISON WORKING TOOL\n\n"
            + spec["title"] + "\n\n"
            "1. Open comparison.html in a modern browser. It works offline.\n"
            "2. Search to find words across the supplied records. Clear search to see every record.\n"
            "3. Choose a field to sort, or restore original source order.\n"
            "4. Print the current view if useful.\n"
            "5. Check source.json for the original supplied records.\n\n"
            "Not provided means absent, null, or empty in the supplied records. It does not mean a service is unavailable.\n"
            "This instrument organises supplied information. It does not establish eligibility, current availability, or any broader finding.\n"
            "Keep your existing records. The tool does not edit them or contact anyone.\n"
            "Review manifest.json and evidence/ for checks, lineage, and unresolved gaps.\n").encode()


def main():
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description="Build an offline comparison view from supplied flat JSON records.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--title", default="Compare your supplied records")
    args = parser.parse_args()
    data = args.source.read_bytes()
    records, fields = load_records(data)
    spec = {"kind": "offline_record_comparator", "version": 1, "title": args.title, "columns": fields, "missing_label": "Not provided"}
    with args.out.open("xb") as output:
        output.write(compile_instrument(spec, records, digest(data)))
    print("Created " + str(args.out))


if __name__ == "__main__":
    main()
