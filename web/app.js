"use strict";
const search = document.getElementById("tool-search");
const origin = document.getElementById("origin-filter");
const cards = [...document.querySelectorAll(".tool-card")];
const result = document.getElementById("filter-result");
const empty = document.getElementById("empty-state");
function filterTools() {
  const query = search.value.trim().toLocaleLowerCase();
  let visible = 0;
  for (const card of cards) {
    const matches = card.dataset.search.includes(query) && (!origin.value || card.dataset.origin === origin.value);
    card.hidden = !matches;
    if (matches) visible++;
  }
  result.textContent = `${visible} of ${cards.length} free ${cards.length === 1 ? "tool" : "tools"} shown`;
  empty.hidden = visible !== 0;
}
search.addEventListener("input", filterTools);
origin.addEventListener("change", filterTools);
document.getElementById("clear-filters").addEventListener("click", () => {
  search.value = "";
  origin.value = "";
  filterTools();
  search.focus();
});
filterTools();
