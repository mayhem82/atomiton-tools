"""Validate the free-tool register and generate the buildless Pages catalogue."""
from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode()


def local_file(relative):
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise ValueError("Missing or out-of-repository file: " + relative)
    return path


def require_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Source links must be credential-free HTTPS URLs")


def eligibility_errors(tool):
    errors = []
    access = tool.get("free_access", {})
    if access.get("payment_required") is not False:
        errors.append("The listed function requires payment or has no explicit no-payment determination")
    if access.get("verified") is not True:
        errors.append("The usable free path has not been verified")
    if access.get("paid_dependencies") != []:
        errors.append("The listed function has required paid dependencies")
    if not isinstance(access.get("path"), str) or not access["path"].strip():
        errors.append("A usable free path must be described")
    if not access.get("evidence"):
        errors.append("Free-path evidence is required")
    return errors


def validate(catalogue):
    if catalogue.get("catalogue_version") != "0.1.0" or not isinstance(catalogue.get("tools"), list):
        raise ValueError("Unsupported catalogue format")
    seen = set()
    required = {"id", "name", "version", "summary", "origin", "origin_label", "function", "audience", "research_gap", "tags", "readiness", "licence", "source_url", "licence_url", "launch_path", "free_access", "usage_evidence", "test_results", "trial_results", "limitations", "adoption_steps"}
    for tool in catalogue["tools"]:
        if set(tool) != required:
            raise ValueError("Unexpected or missing public entry fields")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", tool["id"]) or tool["id"] in seen:
            raise ValueError("Tool identifiers must be unique portable slugs")
        seen.add(tool["id"])
        if tool["origin"] not in ("created", "existing", "adapted"):
            raise ValueError("Record the tool's actual origin")
        errors = eligibility_errors(tool)
        if errors:
            raise ValueError(tool["id"] + ": " + "; ".join(errors))
        for key in ("source_url", "licence_url"):
            require_url(tool[key])
        if tool["launch_path"] is not None:
            local_file(tool["launch_path"])
        for key in ("name", "version", "summary", "function", "audience", "research_gap", "licence"):
            if not isinstance(tool[key], str) or not tool[key].strip():
                raise ValueError("Missing adoption information: " + key)
        if not tool["adoption_steps"] or not tool["limitations"]:
            raise ValueError("Adoption instructions and limitations must be explicit")
        for evidence in tool["free_access"]["evidence"]:
            if evidence.startswith("https://"):
                require_url(evidence)
            else:
                local_file(evidence)
        for usage in tool["usage_evidence"]:
            if usage.get("basis") not in ("direct_observation", "author_report", "third_party_report"):
                raise ValueError("Usage evidence must identify its observation basis")
            require_url(usage["source_url"])
            if not usage.get("scope"):
                raise ValueError("Usage evidence needs a precise scope")
        for result in tool["test_results"] + tool["trial_results"]:
            if result.get("kind") not in ("automated_test", "rebuild_check", "author_report", "third_party_report", "field_trial") or result.get("outcome") not in ("passed", "failed", "mixed", "not_run", "inconclusive"):
                raise ValueError("Unsupported test/trial state")
            for key in ("conducted_by", "scope", "environment", "report", "tool_version", "recorded_on"):
                if not result.get(key):
                    raise ValueError("Test/trial evidence is incomplete")
            report = result["report"]
            if report.startswith("https://"):
                require_url(report)
            else:
                data = local_file(report).read_text(encoding="utf-8")
                if report.endswith(".tap"):
                    for field, label in (("passed", "pass"), ("failed", "fail")):
                        matches = re.findall(r"^# " + label + r" (\d+)\s*$", data, re.MULTILINE)
                        if len(matches) != 1 or result.get(field) != int(matches[0]):
                            raise ValueError("Reported test totals disagree with retained TAP evidence")
                    actual = "passed" if result["failed"] == 0 else "failed"
                    if result["outcome"] != actual:
                        raise ValueError("Reported outcome disagrees with the test record")
                elif report.endswith(".json"):
                    checked = json.loads(data)
                    if result["outcome"] == "passed" and checked.get("passed") is not True:
                        raise ValueError("A passing test needs an actual passing check record")
    return catalogue


def rebuild_evidence():
    tool = ROOT / "tools/offline-record-comparator"
    expected = (tool / "comparison.html").read_bytes()
    with tempfile.TemporaryDirectory(prefix="atomiton-public-rebuild-") as folder:
        output = Path(folder) / "comparison.html"
        result = subprocess.run([sys.executable, "-I", str(tool / "compiler.py"), str(tool / "source.json"), "--out", str(output)], cwd=folder, capture_output=True, encoding="utf-8", timeout=15)
        if result.returncode or not output.exists():
            raise ValueError("Standalone compiler rebuild failed")
        actual = output.read_bytes()
    report = {"passed": actual == expected, "procedure": "Isolated Python standard-library invocation of compiler.py on the bundled synthetic source; compare output bytes.", "recorded_for_tool_version": "0.1.0", "source_sha256": sha((tool / "source.json").read_bytes()), "compiler_sha256": sha((tool / "compiler.py").read_bytes()), "expected_html_sha256": sha(expected), "actual_html_sha256": sha(actual), "atomiton_import_required": False, "data_scope": "synthetic", "field_trial": False}
    (ROOT / "evidence/comparator-standalone-rebuild.json").write_bytes(encoded(report))
    if not report["passed"]:
        raise ValueError("Standalone rebuild changed the shipped instrument")


def package(tool):
    source = ROOT / "tools" / tool["id"]
    if not source.is_dir():
        # Existing tools stay at their original source; no implied redistribution.
        return None
    files = {str(path.relative_to(source)).replace("\\", "/"): path.read_bytes() for path in sorted(source.rglob("*")) if path.is_file() and "__pycache__" not in path.parts}
    for evidence in tool["free_access"]["evidence"]:
        if not evidence.startswith("https://"):
            files["evidence/" + Path(evidence).name] = local_file(evidence).read_bytes()
    manifest = {"tool_id": tool["id"], "version": tool["version"], "licence": tool["licence"], "files": [{"path": name, "sha256": sha(data), "size_bytes": len(data)} for name, data in sorted(files.items())], "self_digest": "excluded to avoid circular hashing"}
    files["manifest.json"] = encoded(manifest)
    destination = ROOT / "docs/downloads"
    destination.mkdir(parents=True, exist_ok=True)
    relative = "downloads/" + tool["id"] + "-" + tool["version"] + ".zip"
    archive = ROOT / "docs" / relative
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as bundle:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(tool["id"] + "/" + name, date_time=(2026, 11, 13, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, data)
    return {"path": relative, "sha256": sha(archive.read_bytes()), "size_bytes": archive.stat().st_size}


def escape(value):
    return html.escape(str(value), quote=True)


def evidence_href(value):
    return value if value.startswith("https://") else value


def render_card(tool, bundle):
    e = escape
    tags = "".join('<span class="tag">' + e(tag) + '</span>' for tag in tool["tags"])
    source = e(tool["source_url"])
    if bundle:
        launch = e(tool["launch_path"]) if tool["launch_path"] else source
        actions = f'<a class="button primary" href="{launch}">Open tool <span aria-hidden="true">↗</span></a><a class="button" href="{e(bundle["path"])}" download>Download v{e(tool["version"])} <span aria-hidden="true">↓</span></a>'
        checksum = '<span class="sha">Download SHA-256<br>' + e(bundle["sha256"]) + '</span>'
    else:
        actions = f'<a class="button primary" href="{source}">Get the original tool <span aria-hidden="true">↗</span></a>'
        checksum = ""
    steps = "".join("<li>" + e(step) + "</li>" for step in tool["adoption_steps"])
    limits = "".join("<li>" + e(value) + "</li>" for value in tool["limitations"] + tool["free_access"]["limits"])
    reports = "".join(f'<a class="evidence-link" href="{e(evidence_href(report["report"]))}">{e(report["kind"].replace("_", " ").title())} · {e(report["outcome"])} ↗</a><p>{e(report["scope"])}<br>{e(report["environment"])}<br>Conducted by: {e(report["conducted_by"])}.</p>' for report in tool["test_results"])
    trials = "".join(f'<a class="evidence-link" href="{e(evidence_href(report["report"]))}">{e(report["outcome"])} · {e(report["conducted_by"])} ↗</a><p>{e(report["scope"])} {e(report["environment"])}</p>' for report in tool["trial_results"]) or '<p>No real-person field trial has been recorded for this version.</p>'
    usage = "".join(f'<a class="evidence-link" href="{e(record["source_url"])}">{e(record["basis"].replace("_", " ").title())} ↗</a><p>{e(record["scope"])}</p>' for record in tool["usage_evidence"]) or '<p>Independent usage evidence has not been recorded for this version.</p>'
    accounts = ", ".join(tool["free_access"]["accounts"]) or "No account required"
    search = " ".join([tool["name"], tool["summary"], tool["function"], *tool["tags"]]).lower()
    outcomes = {record["outcome"] for record in tool["test_results"]}
    tested = "Declared technical checks passed" if outcomes == {"passed"} else "Mixed or unresolved test evidence" if outcomes else "Technical testing not recorded"
    return f'''<article class="tool-card" id="{e(tool["id"])}" data-origin="{e(tool["origin"])}" data-search="{e(search)}">
<div class="tool-main"><div><div class="tool-id"><span class="free">FREE TO USE</span><span>{e(tool["origin_label"])}</span></div><h3>{e(tool["name"])}</h3><p class="summary">{e(tool["summary"])}</p><div class="tags">{tags}</div><div class="tool-actions">{actions}<a class="button" href="{source}">View source ↗</a></div></div>
<aside class="evidence-panel" aria-label="Evidence at a glance"><h4>Evidence, at this version</h4><div class="evidence-row"><b><span class="status-dot"></span>{e(tested)}</b><p>{len(tool["test_results"])} retained reports · see their procedures and conditions</p></div><div class="evidence-row"><b><span class="status-dot open"></span>{"Field-trial evidence available" if tool["trial_results"] else "Field trial: not yet recorded"}</b><p>{e(tool["readiness"])} · v{e(tool["version"])} · {e(tool["licence"])}</p></div><div class="evidence-row"><b>Free access verified</b><p>{e(accounts)}. Listed function requires no payment.</p></div></aside></div>
<details class="tool-details"><summary>Test reports, limitations &amp; adoption instructions</summary><div class="details-body"><section><h4>The research need</h4><p>{e(tool["research_gap"])}</p><h4>Who it is for</h4><p>{e(tool["audience"])}</p><h4>Take it on</h4><ol>{steps}</ol>{checksum}<a class="evidence-link" href="{e(tool["licence_url"])}">Read the licence ↗</a></section><section><h4>What was checked</h4>{reports}<h4>Field trials</h4>{trials}<h4>Evidence of use</h4>{usage}<h4>Limits to carry forward</h4><ul>{limits}</ul></section></div></details></article>'''


def render(catalogue, bundles):
    e = escape
    tools = catalogue["tools"]
    cards = "\n".join(render_card(tool, bundles[tool["id"]]) for tool in tools)
    reports = sum(len(tool["test_results"]) for tool in tools)
    trials = sum(sum(result["kind"] == "field_trial" and result["outcome"] != "not_run" for result in tool["trial_results"]) for tool in tools)
    repo = e(catalogue["repository_url"])
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#f5f2e9"><meta name="description" content="Free tools found, built and tested through civilian research. Inspect the source, technical evidence and trial results, then take a tool on."><meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; form-action 'none'"><title>The Atomiton · Free Tool Library</title><link rel="stylesheet" href="assets/style.css"><script src="assets/app.js" defer></script></head>
<body><a class="skip" href="#library">Skip to the tools</a><header class="top"><nav class="wrap nav" aria-label="Main navigation"><a class="brand" href="./"><span class="symbol" aria-hidden="true"><i></i><i></i><i></i><i></i></span>THE ATOMITON</a><div class="navlinks"><a href="#library">The library</a><a href="#method">The evidence</a><a href="#trials">Contribute</a><a class="repo" href="{repo}">GitHub <span aria-hidden="true">↗</span></a></div></nav></header>
<main><section class="wrap hero"><div><div class="eyebrow">Civilian research · Public tool library</div><h1>Find a useful tool.<br><em>See what holds up.</em></h1><p class="lede">Research uncovers gaps. Sometimes it finds a tool already in use; sometimes it creates one. This library carries the source, checks and trial results forward, so others can take the work on.</p><div class="hero-actions"><a class="button primary" href="#library">Explore the tools <span aria-hidden="true">↓</span></a><a class="text-link" href="#method">How entries earn their place</a></div></div><aside class="research-note"><span class="mono">Open work / Evidence attached</span><h2>Useful beyond<br>the investigation.</h2><p>For people already navigating a system, the researchers working with them, and the people who come next.</p><ol class="process"><li><span>01</span>Discover or build an instrument</li><li><span>02</span>Test the stated function</li><li><span>03</span>Retain the result and its limits</li><li><span>04</span>Make independent reuse possible</li></ol></aside></section>
<div class="wrap stats" aria-label="Current catalogue"><div class="stat"><strong>{len(tools):02d}</strong><span>free {'tool' if len(tools)==1 else 'tools'}<br>currently available</span></div><div class="stat"><strong>{reports:02d}</strong><span>technical evidence<br>reports retained</span></div><div class="stat"><strong>{trials:02d}</strong><span>real-world field trials<br>recorded so far</span></div></div>
<section class="wrap section" id="library"><div class="section-head"><h2>The tool library</h2><p>Original builds, adaptations and existing tools · Free paths only</p></div><div class="filters"><div class="field"><label for="tool-search">Search tools and functions</label><input id="tool-search" type="search" placeholder="Try comparison, records or offline" autocomplete="off"></div><div class="field"><label for="origin-filter">Where the tool came from</label><select id="origin-filter"><option value="">All origins</option><option value="existing">Already exists</option><option value="created">Built through research</option><option value="adapted">Adapted through research</option></select></div></div><p class="filter-result" id="filter-result" aria-live="polite">{len(tools)} free tool entries</p><div id="tool-list">{cards}</div><div class="empty" id="empty-state" hidden><h3>No tools match these filters</h3><p>The library grows as research discovers and checks useful instruments.</p><button class="button" id="clear-filters" type="button">Clear filters</button></div></section>
<section class="method" id="method"><div class="wrap section"><div class="section-head"><h2>Keep the evidence with the tool.</h2><p>Every entry has conditions. Make them visible.</p></div><div class="method-grid"><section class="method-card"><span class="mono">01 / Access</span><h3>A usable free path.</h3><p>The listed function must work without payment. Accounts, limits and dependencies are disclosed. Paywalled functions do not qualify for the library.</p></section><section class="method-card"><span class="mono">02 / Provenance</span><h3>Credit where it came from.</h3><p>Existing tools keep their original source and licence. Evidence of use by others is recorded alongside what the author reports and what Atomiton actually checked.</p></section><section class="method-card"><span class="mono">03 / Trial</span><h3>A result with its limits.</h3><p>Synthetic checks, practical trials and observed benefit have separate records. Failed and mixed results stay useful. A passing test carries its version and conditions.</p></section></div></div></section>
<section class="wrap section trial" id="trials"><div><div class="eyebrow">Discovery continues</div><h2>Already using something<br>that helps?</h2><p>An investigation may find an existing tool doing useful work. Bring its original source, free access path and evidence of use. If you try a listed tool, record what happened so the next person has more to go on.</p><a class="text-link" href="{repo}/issues/new?template=tool-discovery.yml">Submit a tool discovery ↗</a></div><aside class="trial-box"><h3>A useful trial record carries:</h3><ul><li>The tool and exact version used</li><li>The task, setting and procedure</li><li>What worked, failed or stayed unresolved</li><li>Evidence, limitations and ongoing requirements</li></ul><a class="button primary" href="{repo}/issues/new?template=field-trial.yml">Record a field trial <span aria-hidden="true">↗</span></a></aside></section></main>
<footer class="wrap footer"><div><span class="mono">MAYHEM / The Atomiton</span><p>Research that carries useful instruments into other hands.<br>Initial catalogue · Real-recipient benefit and sustained external change remain to be demonstrated.</p></div><div><a href="{repo}">Source repository ↗</a><p>Original code: MIT · External tools retain their own licences.<br><a href="catalogue.json">Read the catalogue data</a></p></div></footer></body></html>'''


def main():
    rebuild_evidence()
    catalogue = validate(json.loads((ROOT / "catalogue.json").read_bytes()))
    output = ROOT / "docs"
    (output / "assets").mkdir(parents=True, exist_ok=True)
    for name in ("style.css", "app.js"):
        shutil.copyfile(ROOT / "web" / name, output / "assets" / name)
    shutil.copytree(ROOT / "evidence", output / "evidence", dirs_exist_ok=True)
    bundles = {}
    for tool in catalogue["tools"]:
        source = ROOT / "tools" / tool["id"]
        if source.is_dir():
            shutil.copytree(source, output / "tools" / tool["id"], dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        bundles[tool["id"]] = package(tool)
    (output / "index.html").write_text(render(catalogue, bundles), encoding="utf-8", newline="\n")
    (output / "catalogue.json").write_bytes(encoded({**catalogue, "bundles": bundles}))
    (output / ".nojekyll").write_bytes(b"")
    print(json.dumps({"built": "docs/index.html", "free_tools": len(catalogue["tools"]), "bundles": sum(value is not None for value in bundles.values())}))


if __name__ == "__main__":
    main()
