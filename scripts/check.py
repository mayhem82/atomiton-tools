"""Check the public catalogue, evidence, source links and adoption bundles."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from build import ROOT, eligibility_errors, validate


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        self.links += [value for key, value in attrs if key in ("src", "href") and value]


def main():
    catalogue = validate(json.loads((ROOT / "catalogue.json").read_bytes()))
    published = json.loads((ROOT / "docs/catalogue.json").read_bytes())
    if catalogue != {key: value for key, value in published.items() if key != "bundles"}:
        raise ValueError("Published catalogue is stale")
    checked_links = 0
    for page in (ROOT / "docs").rglob("*.html"):
        parser = Links()
        parser.feed(page.read_text(encoding="utf-8"))
        for link in parser.links:
            parsed = urlsplit(link)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            target = (page.parent / unquote(parsed.path)).resolve()
            if not target.is_relative_to(ROOT / "docs") or not target.exists():
                raise ValueError("Broken public link: " + link)
            checked_links += 1
    bundle_files = 0
    for tool_id, info in published["bundles"].items():
        if info is None:
            continue
        path = ROOT / "docs" / info["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != info["sha256"]:
            raise ValueError("Download checksum changed")
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if any(name.startswith("/") or ".." in Path(name).parts for name in names):
                raise ValueError("Unsafe archive filename")
            manifest = json.loads(archive.read(tool_id + "/manifest.json"))
            expected_names = {tool_id + "/manifest.json"}
            for record in manifest["files"]:
                name = tool_id + "/" + record["path"]
                expected_names.add(name)
                if hashlib.sha256(archive.read(name)).hexdigest() != record["sha256"]:
                    raise ValueError("A bundle file differs from its adoption manifest")
                bundle_files += 1
            if expected_names != set(names):
                raise ValueError("Bundle includes unlisted files")
    # Regressions for the user's no-paywall rule and truthful test declarations.
    base = catalogue["tools"][0]
    for changed in ({"payment_required": True}, {"verified": False}, {"paid_dependencies": ["paid API"]}):
        candidate = copy.deepcopy(base)
        candidate["free_access"].update(changed)
        if not eligibility_errors(candidate):
            raise ValueError("Payment-required or unverified tool passed the free-access gate")
    bad = copy.deepcopy(catalogue)
    bad["tools"][0]["test_results"][0]["passed"] += 1
    try:
        validate(bad)
    except ValueError:
        pass
    else:
        raise ValueError("Misreported test totals passed validation")
    print(json.dumps({"passed": True, "free_tools": len(catalogue["tools"]), "local_links_checked": checked_links, "bundle_files_verified": bundle_files, "payment_gate_regressions": 3, "misreported_result_rejected": True, "field_trials": sum(len(tool["trial_results"]) for tool in catalogue["tools"])}))


if __name__ == "__main__":
    main()
