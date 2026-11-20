/**
 * 一覧の検索・絞り込み・並べ替え。状態は URL のクエリに置く（共有・再読込・戻るで同じ表示になる）。
 * 一覧のパスは市区町村とカテゴリを表す。
 */
type F = { key: string; kind: "one" | "many" | "age" | "flag"; label: string; byAge?: boolean; options?: Record<string, string> };
type Cfg = { unit: string; short: string; sorts: Record<string, "asc" | "desc">; filters: F[] };

const cfg: Cfg = JSON.parse(document.getElementById("list-cfg")!.textContent!);
const form = document.getElementById("f") as HTMLFormElement;
const q = document.getElementById("q") as HTMLInputElement;
const sortSel = document.getElementById("sort") as HTMLSelectElement;
const ul = document.getElementById("items")!;
const items = [...ul.children] as HTMLLIElement[];
const sheet = document.getElementById("filters") as HTMLDialogElement;
const countEl = document.getElementById("count")!;
const activeN = document.getElementById("active-n")!;
const empty = document.getElementById("empty")!;
const emptyActs = document.getElementById("empty-acts")!;

/* ── 検索用の文字の正規化（全角半角・かなカナ・漢数字の丁目・番地の書き方をそろえる） ── */
const KD: Record<string, number> = { 一: 1, 二: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9 };
const kanjiNum = (s: string) => {
  const [a, b] = s.split("十");
  if (b === undefined) return String(KD[a] ?? a);
  return String((a ? KD[a] : 1) * 10 + (b ? KD[b] : 0));
};
const norm = (s: string) =>
  s
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[ァ-ヶ]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0x60))
    .replace(/([一二三四五六七八九十]+)丁目/g, (_, n) => kanjiNum(n) + "-")
    .replace(/丁目|番地|番|号|の/g, "-")
    .replace(/[‐－―ー−]/g, "-")
    .replace(/\s+/g, "");
const hay = new Map(items.map((li) => [li, norm([li.querySelector("h3")!.textContent, li.dataset.alt ?? "", li.querySelector(".addr")?.textContent ?? ""].join(" "))]));

/* ── 状態 ── */
type State = { q: string; sort: string; one: Record<string, string>; age: string; flags: Set<string>; many: Record<string, Set<string>> };
const ones = cfg.filters.filter((f) => f.kind === "one");
const manys = cfg.filters.filter((f) => f.kind === "many");
const flagDefs = cfg.filters.filter((f) => f.kind === "flag");
const hasAge = cfg.filters.some((f) => f.kind === "age");
const all = (f: F) => new Set(Object.keys(f.options!));

function fromUrl(): State {
  const p = new URLSearchParams(location.search);
  const one: Record<string, string> = {};
  for (const f of ones) {
    const v = p.get(f.key) ?? "";
    one[f.key] = v in f.options! ? v : "";
  }
  const many: Record<string, Set<string>> = {};
  for (const f of manys) {
    const v = p.get(f.key);
    const s = v ? new Set(v.split(",").filter((x) => x in f.options!)) : all(f);
    many[f.key] = s.size ? s : all(f);
  }
  const sort = p.get("sort") ?? "";
  return {
    q: p.get("q") ?? "",
    sort: sort in cfg.sorts ? sort : "",
    one,
    age: hasAge && /^\d$/.test(p.get("age") ?? "") ? p.get("age")! : "",
    flags: new Set(flagDefs.filter((f) => p.get(f.key) === "1").map((f) => f.key)),
    many,
  };
}

function fromForm(): State {
  const fd = new FormData(form);
  const one: Record<string, string> = {};
  for (const f of ones) one[f.key] = String(fd.get(f.key) ?? "");
  const many: Record<string, Set<string>> = {};
  for (const f of manys) many[f.key] = new Set(fd.getAll(f.key) as string[]);
  return {
    q: q.value.trim(),
    sort: sortSel.value,
    one,
    age: hasAge ? String(fd.get("age") ?? "") : "",
    flags: new Set(flagDefs.filter((f) => fd.get(f.key) === "1").map((f) => f.key)),
    many,
  };
}

function toForm(s: State) {
  q.value = s.q;
  sortSel.value = s.sort;
  for (const el of form.elements as unknown as HTMLInputElement[]) {
    if (el.type === "radio") el.checked = el.name === "age" ? el.value === s.age : el.value === (s.one[el.name] ?? "");
    else if (el.type === "checkbox") el.checked = el.name in s.many ? s.many[el.name].has(el.value) : s.flags.has(el.name);
  }
}

function toUrl(s: State) {
  const p = new URLSearchParams();
  for (const f of ones) if (s.one[f.key]) p.set(f.key, s.one[f.key]);
  if (s.age) p.set("age", s.age);
  for (const k of s.flags) p.set(k, "1");
  for (const f of manys) if (s.many[f.key].size < all(f).size) p.set(f.key, [...s.many[f.key]].join(","));
  if (s.q) p.set("q", s.q);
  if (s.sort) p.set("sort", s.sort);
  const qs = p.toString();
  const url = location.pathname + (qs ? "?" + qs : "");
  if (url !== location.pathname + location.search) history.replaceState(history.state, "", url);
  // 詳細から一覧へ戻るリンクのため、最後に見た一覧の URL を覚える
  try { sessionStorage.setItem("hgh-list:" + location.pathname, url); } catch { /* 無視 */ }
}

/* ── 年齢別の空き ── */
const va = (li: HTMLElement, age: string): number | null => {
  const m = (li.dataset.va ?? "").match(new RegExp(`(?:^| )${age}:(\\d+)`));
  return m ? +m[1] : null;
};
const vacDt = items.map((li) => li.querySelector<HTMLElement>('dt[data-k="vac"]'));
const vacDd = items.map((li) => li.querySelector<HTMLElement>('dd[data-k="vac"]'));
const vacHtml = vacDd.map((d) => d?.innerHTML ?? "");

/* ── 反映 ── */
function apply(s: State) {
  const qn = norm(s.q);
  const qParts = qn.split(/[,、]/).filter(Boolean);
  let n = 0;
  items.forEach((li, i) => {
    const d = li.dataset;
    let ok = true;
    for (const f of ones) if (ok && s.one[f.key]) ok = d["f" + cap(f.key)] === s.one[f.key];
    for (const f of manys) if (ok) ok = s.many[f.key].has(d["f" + cap(f.key)] ?? "");
    if (ok && s.age) {
      const [lo, hi] = (d.age ?? "").split("-");
      ok = lo !== undefined && hi !== undefined && lo !== "" && +lo <= +s.age && +s.age <= +hi;
    }
    for (const f of flagDefs) {
      if (!ok || !s.flags.has(f.key)) continue;
      const byAge = f.byAge && s.age && d.va ? va(li, s.age) : null;
      ok = byAge !== null ? byAge > 0 : (d.flags ?? "").split(" ").includes(f.key);
    }
    if (ok && qParts.length) ok = qParts.some((p) => hay.get(li)!.includes(p));
    li.hidden = !ok;
    if (ok) n++;
    // 年齢を選んでいるときは、その年齢の空きを出す
    const dt = vacDt[i], dd = vacDd[i];
    if (dt && dd) {
      const v = s.age && d.va ? va(li, s.age) : null;
      dt.textContent = v !== null ? `空き(${s.age}${cfg.short})` : "空き";
      if (v !== null) dd.textContent = `${v}人`;
      else dd.innerHTML = vacHtml[i];
    }
  });
  countEl.textContent = String(n);
  document.querySelectorAll("[data-n]").forEach((el) => (el.textContent = String(n)));
  sortItems(s);
  const act = actives(s);
  const nf = act.filter((a) => a.key !== "q").length;
  activeN.textContent = String(nf);
  activeN.hidden = nf === 0;
  empty.hidden = n > 0;
  ul.hidden = n === 0;
  if (n === 0) renderEmpty(act);
  toUrl(s);
}
const cap = (k: string) => k[0].toUpperCase() + k.slice(1);

function sortItems(s: State) {
  const k = s.sort;
  const val = (li: HTMLElement): number | null => {
    if (k === "vac" && s.age && li.dataset.va) return va(li, s.age);
    const v = li.dataset["s" + cap(k)];
    return v === undefined ? null : +v;
  };
  const sorted = items
    .map((li, i) => ({ li, i, v: k ? val(li) : null }))
    .sort((a, b) => {
      if (k) {
        if (a.v === null && b.v !== null) return 1;
        if (b.v === null && a.v !== null) return -1;
        if (a.v !== null && b.v !== null && a.v !== b.v) return cfg.sorts[k] === "asc" ? a.v - b.v : b.v - a.v;
      }
      return a.i - b.i; // 同じ値は名前順（サーバーで名前順に並べてある）
    });
  if (sorted.some((x, i) => ul.children[i] !== x.li)) ul.append(...sorted.map((x) => x.li));
}

/* ── 今かかっている条件（0件のときに1つずつ外せるようにする） ── */
type Active = { key: string; label: string; clear: (s: State) => void };
function actives(s: State): Active[] {
  const a: Active[] = [];
  if (s.q) a.push({ key: "q", label: `「${s.q}」`, clear: (x) => (x.q = "") });
  for (const f of ones) if (s.one[f.key]) a.push({ key: f.key, label: f.options![s.one[f.key]], clear: (x) => (x.one[f.key] = "") });
  if (s.age) a.push({ key: "age", label: `${s.age}${cfg.unit}`, clear: (x) => (x.age = "") });
  for (const f of flagDefs) if (s.flags.has(f.key)) a.push({ key: f.key, label: f.label, clear: (x) => x.flags.delete(f.key) });
  for (const f of manys) if (s.many[f.key].size < all(f).size) a.push({ key: f.key, label: `${f.label}の絞り込み`, clear: (x) => (x.many[f.key] = all(f)) });
  return a;
}
function renderEmpty(act: Active[]) {
  emptyActs.replaceChildren();
  for (const a of act) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "btn";
    b.textContent = `${a.label}を外す`;
    b.addEventListener("click", () => { const s = fromForm(); a.clear(s); toForm(s); apply(s); });
    emptyActs.append(b);
  }
  if (act.length > 1) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "btn ghost";
    b.textContent = "すべて外す";
    b.addEventListener("click", reset);
    emptyActs.append(b);
  }
}
function reset() {
  const s = fromForm();
  s.q = "";
  for (const f of ones) s.one[f.key] = "";
  for (const f of manys) s.many[f.key] = all(f);
  s.age = "";
  s.flags.clear();
  toForm(s);
  apply(s);
}

/* ── 操作 ── */
form.addEventListener("change", () => apply(fromForm()));
sortSel.addEventListener("change", () => apply(fromForm()));
let t = 0;
q.addEventListener("input", () => { clearTimeout(t); t = window.setTimeout(() => apply(fromForm()), 150); });
document.querySelector("[data-reset]")!.addEventListener("click", () => { const s = fromForm(); const keep = s.q; reset(); if (keep) { q.value = keep; apply(fromForm()); } });

// スマホ：下からのシート。PCでは左の列に常に出ている（CSS）
const wide = matchMedia("(min-width: 960px)");
document.getElementById("open-filters")!.addEventListener("click", () => sheet.showModal());
sheet.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", () => sheet.close()));
sheet.addEventListener("click", (e) => { if (e.target === sheet) sheet.close(); });
wide.addEventListener("change", () => { if (wide.matches && sheet.open) sheet.close(); });

// 初めの表示と、戻る・進むで URL が変わったとき
const init = () => { const s = fromUrl(); toForm(s); apply(s); };
addEventListener("popstate", init);
init();
document.documentElement.classList.remove("list-pending");
