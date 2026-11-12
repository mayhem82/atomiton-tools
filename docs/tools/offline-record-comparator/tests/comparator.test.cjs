"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const {execFileSync} = require("node:child_process");
const {createHash} = require("node:crypto");
const {readFileSync, writeFileSync, mkdtempSync, rmSync} = require("node:fs");
const {tmpdir} = require("node:os");
const path = require("node:path");
const vm = require("node:vm");
const root = path.resolve(__dirname, "..");

function instrument(records) {
  const taskDir = mkdtempSync(path.join(tmpdir(), "atomiton-tool-test-"));
  try {
    const input = path.join(taskDir, "source.json");
    const output = path.join(taskDir, "comparison.html");
    writeFileSync(input, JSON.stringify(records));
    execFileSync(process.env.ATOMITON_TEST_PYTHON || "python", ["-I", path.join(root, "compiler.py"), input, "--out", output], {cwd: taskDir, encoding: "utf8"});
    return readFileSync(output, "utf8");
  } finally {
    const target = path.resolve(taskDir);
    if (path.dirname(target) !== path.resolve(tmpdir()) || !path.basename(target).startsWith("atomiton-tool-test-")) throw new Error("Refusing cleanup outside the owned test directory");
    rmSync(target, {recursive: true, force: true});
  }
}

function element() {
  return {children: [], textContent: "", value: "", listeners: {},
    append(child) { this.children.push(child); },
    replaceChildren() { this.children = []; },
    addEventListener(name, callback) { this.listeners[name] = callback; }};
}

function exercise(html) {
  const source = html.match(/<script id="source-data" type="application\/json">([\s\S]*?)<\/script>/)[1];
  const columns = html.match(/<script id="column-data" type="application\/json">([\s\S]*?)<\/script>/)[1];
  const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
  const fields = ["source-data", "column-data", "search", "sort", "count", "print", "tbody"];
  const elements = Object.fromEntries(fields.map(key => [key, element()]));
  elements["source-data"].textContent = source;
  elements["column-data"].textContent = columns;
  let prints = 0;
  const window = {print() { prints++; }};
  const document = {getElementById(id) { return elements[id]; }, querySelector(selector) { assert.equal(selector, "tbody"); return elements.tbody; }, createElement() { return element(); }};
  vm.runInNewContext(script, {document, window}, {timeout: 2000});
  return {elements, window, rows: () => elements.tbody.children.map(row => row.children.map(cell => cell.textContent)), prints: () => prints, script};
}

test("generated script searches, restores source order and sorts the actual embedded rows", () => {
  const records = JSON.parse(readFileSync(path.join(root, "source.json"), "utf8"));
  const view = exercise(instrument(records));
  assert.equal(view.elements.count.textContent, "3 of 3 records shown");
  assert.equal(view.rows()[1][4], "Not provided");
  assert.equal(view.rows()[1][5], "Not provided");
  view.elements.search.value = "email";
  view.elements.search.listeners.input();
  assert.equal(view.elements.count.textContent, "1 of 3 records shown");
  assert.equal(view.rows()[0][1], "Example Records Helper");
  view.elements.search.value = "";
  view.elements.search.listeners.input();
  view.elements.sort.value = "1";
  view.elements.sort.listeners.change();
  assert.deepEqual(view.rows().map(row => row[1]), ["Example Access Support", "Example Community Desk", "Example Records Helper"]);
  view.elements.sort.value = "";
  view.elements.sort.listeners.change();
  assert.equal(view.rows()[0][1], "Example Community Desk");
  view.elements.print.listeners.click();
  assert.equal(view.prints(), 1);
});

test("hostile strings and inherited property names remain literal or missing data", () => {
  const records = JSON.parse('[{"name":"</script><script>window.compromised=true</script>","note":null},{"name":"Second","constructor":"Supplied constructor field","__proto__":"Supplied prototype field"}]');
  const html = instrument(records);
  const view = exercise(html);
  assert.equal(view.rows()[0][0], records[0].name);
  assert.equal(view.rows()[0][2], "Not provided");
  assert.equal(view.rows()[0][3], "Not provided");
  assert.equal(view.rows()[1][2], "Supplied constructor field");
  assert.equal(view.rows()[1][3], "Supplied prototype field");
  assert.equal(view.window.compromised, undefined);
  assert.equal(html.includes("<script>window.compromised"), false);
});

test("the document CSP admits the exact generated script and disables external resources", () => {
  const html = instrument([{name: "A", contact: "One"}, {name: "B", contact: "Two"}]);
  const view = exercise(html);
  const hash = createHash("sha256").update(view.script).digest("base64");
  assert.ok(html.includes("script-src 'sha256-" + hash + "'"));
  assert.ok(html.includes("default-src 'none'"));
  assert.ok(html.includes("form-action 'none'"));
});
