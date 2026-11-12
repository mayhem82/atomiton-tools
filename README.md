# The Atomiton · Public Tool Library

Free tools discovered, built or adapted through civilian research, with the evidence needed to judge and adopt them.

Browse: **https://mayhem82.github.io/atomiton-tools/**

Tools may already exist and be used by others. Their origin, original source, licence and usage evidence remain visible. Investigation can fill a gap by finding an existing instrument, adapting it or building a new one. A tool can serve the research itself, people already navigating a system, or a receiving human system.

Tools that require payment for their listed function do not qualify. Each published entry needs a verified usable free path, with account requirements, limits and dependencies disclosed. Optional paid features are outside the listed capability. Research candidates that have not cleared this check stay outside the published count.

The first release contains one downloadable offline comparison prototype. It passed its declared automated checks on synthetic records. No real-person field trial has been performed. The catalogue does not present a passed test as a demonstrated remedy or Red Stone outcome.

## Adopt a tool

Open its catalogue entry, read the tested function and limitations, and inspect the test report. Download the versioned bundle or clone the repository. Each bundled tool includes source, licence, instructions, sample data and checksums. Existing external tools retain their original source and licence links; inclusion grants no new rights over them.

The comparison tool works offline in a modern browser. Its standalone compiler needs only Python 3.11+ to create a version from new supplied records. Neither requires an AI account, paid API, subscription or connection to Atomiton.

## Contribute a discovery or trial

Use the [tool discovery form](https://github.com/mayhem82/atomiton-tools/issues/new?template=tool-discovery.yml) or [field trial form](https://github.com/mayhem82/atomiton-tools/issues/new?template=field-trial.yml). Reports must identify the tool/version, the task and conditions, the actual outcome and limitations. Cite actual evidence of third-party use; repository stars or an author's feature list do not establish use or benefit.

`catalogue.json` is the source register. The page distinguishes original test claims, Atomiton tests and field trials. Discovery, technical readiness, practical trial status and adoption are separate observations. See CONTRIBUTING.md for the entry contract.

## Build and check

```text
python scripts/build.py
python scripts/check.py
node --test tests/catalogue.test.cjs
```

`docs/` is the committed GitHub Pages output. CI rebuilds it and rejects stale output, broken local evidence/download links, changed bundle digests, missing free-access evidence and misreported test results. The site uses no paid service, external library, tracker or account system.

The MIT licence covers original source and bundled original tools in this repository. External tools remain under their own licences. Personal case records and the Atomiton control runtime are outside this public library.
