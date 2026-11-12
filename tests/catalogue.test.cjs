"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const {readFileSync} = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const root = path.resolve(__dirname, "..");
function field() { return {value: "", listeners: {}, addEventListener(name, fn) {this.listeners[name] = fn;}, focus() {this.focused = true;}}; }
function fixture() {
  const search = field(), origin = field(), result = {}, empty = {hidden: true}, clear = field();
  const cards = [{dataset: {search: "offline record comparator research", origin: "created"}}, {dataset: {search: "existing free timeline", origin: "existing"}}];
  const elements = {"tool-search": search, "origin-filter": origin, "filter-result": result, "empty-state": empty, "clear-filters": clear};
  const document = {getElementById(id) {return elements[id];}, querySelectorAll(selector) {assert.equal(selector, ".tool-card"); return cards;}};
  vm.runInNewContext(readFileSync(path.join(root, "web/app.js"), "utf8"), {document});
  return {search, origin, result, empty, clear, cards};
}
test("search and origin filters include existing tools and retain honest empty results", () => {
  const f = fixture();
  assert.equal(f.result.textContent, "2 of 2 free tools shown");
  f.search.value = "  TIMELINE  "; f.search.listeners.input();
  assert.equal(f.cards[0].hidden, true); assert.equal(f.cards[1].hidden, false);
  f.origin.value = "created"; f.origin.listeners.change();
  assert.equal(f.result.textContent, "0 of 2 free tools shown"); assert.equal(f.empty.hidden, false);
  f.clear.listeners.click();
  assert.equal(f.result.textContent, "2 of 2 free tools shown"); assert.equal(f.empty.hidden, true); assert.equal(f.search.focused, true);
});
test("the committed page carries adoption evidence and discloses missing field trials", () => {
  const html = readFileSync(path.join(root, "docs/index.html"), "utf8");
  assert.ok(html.includes("No real-person field trial has been recorded"));
  assert.ok(html.includes("Paywalled functions do not qualify"));
  assert.ok(html.includes("Download SHA-256"));
  assert.ok(html.includes("Where the tool came from"));
  assert.ok(html.includes('aria-live="polite"'));
  assert.equal(/https?:\/\/[^\s"']+\.(?:js|css)/.test(html), false);
});
