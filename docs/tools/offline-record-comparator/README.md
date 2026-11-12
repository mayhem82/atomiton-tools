# Offline Record Comparator · 0.1.0

A free, offline working tool for people comparing records while navigating a system. It displays supplied information, preserves missing values and supports search, sorting and printing.

## Use the example

Open comparison.html in a modern browser. The bundled records are explicitly synthetic. There is no account, subscription, paid API, network service or Atomiton dependency.

## Use your own records

Keep a copy of your original records. Create a JSON array containing 2–500 flat records, with strings or null as values. The limit is 30 fields and 512 KB. With Python 3.11 or newer:

```text
python compiler.py your-records.json --out your-comparison.html
```

Choose a new output filename; the compiler refuses to overwrite an existing file. Open the new HTML in a browser. To set a heading, add `--title "Your heading"`.

Source, compiler, instructions, MIT licence, technical evidence and file checksums are included in the versioned download. Original input stays unchanged. Source SHA-256 is displayed in the generated view. Null, absent and empty fields are displayed as Not provided, with the original input retained separately.

## Evidence and limits

Three JavaScript checks exercise the actual generated script in a Node VM with a DOM fixture. Separate document checks inspect data preservation and the script policy. A standalone rebuild check compares the output bytes with the shipped version. These are technical checks on synthetic data. They are not a real-person field trial or a full browser compatibility assessment.

The tool does not confirm that supplied information is current or correct, determine eligibility, contact a service, establish a structural harm mechanism or demonstrate a remedy. Missing data remains unknown. Report practical trials with the exact version, environment, task, actual results and remaining problems.

To repeat the script checks with Node.js installed, run `node --test tests/comparator.test.cjs` from this tool folder. Set `ATOMITON_TEST_PYTHON` to your Python executable if it is not available as `python` on PATH. Node.js is needed only for these developer checks, not for using the tool.
