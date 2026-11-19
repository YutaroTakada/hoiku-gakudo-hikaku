/** 比較に入れた施設（この端末の localStorage に保存）。どの画面でも件数と比較への入口を出す。 */
export const KEY = "hgh-compare";
export const MAX = Number(document.documentElement.dataset.maxCompare || 4);

export function load(): string[] {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) || "[]");
    return Array.isArray(v) ? v.filter((x) => typeof x === "string").slice(0, MAX) : [];
  } catch {
    return [];
  }
}
export function save(ids: string[]) {
  try { localStorage.setItem(KEY, JSON.stringify(ids.slice(0, MAX))); } catch { /* 保存できない端末では何もしない */ }
  paint();
}
/** 入れる・外す。入れられなかったら false */
export function toggle(id: string): boolean {
  const s = load();
  if (s.includes(id)) { save(s.filter((x) => x !== id)); return true; }
  if (s.length >= MAX) return false;
  save([...s, id]);
  return true;
}

const listeners: (() => void)[] = [];
export const onChange = (fn: () => void) => listeners.push(fn);

/** ヘッダーの件数、下のバー、各「比較」ボタンを今の状態に合わせる */
export function paint() {
  const s = load();
  for (const el of document.querySelectorAll<HTMLElement>("[data-cmp-count]")) {
    el.textContent = String(s.length);
    el.hidden = s.length === 0;
  }
  const bar = document.getElementById("cmpbar");
  if (bar) {
    bar.hidden = s.length === 0;
    document.body.classList.toggle("has-bar", s.length > 0);
    bar.querySelector("[data-bar-n]")!.textContent = String(s.length);
    const go = bar.querySelector<HTMLAnchorElement>("[data-bar-go]")!;
    go.href = go.dataset.base + "?ids=" + s.join(",");
  }
  for (const b of document.querySelectorAll<HTMLButtonElement>("button[data-add]")) {
    const on = s.includes(b.dataset.add!);
    b.setAttribute("aria-pressed", String(on));
    b.disabled = !on && s.length >= MAX;
    const t = b.querySelector("[data-t]");
    if (t) t.textContent = on ? "比較中" : s.length >= MAX ? `${MAX}件まで` : "比較";
  }
  listeners.forEach((fn) => fn());
}

document.addEventListener("click", (e) => {
  const b = (e.target as Element).closest<HTMLButtonElement>("button[data-add]");
  if (b) toggle(b.dataset.add!);
});
// 別のタブで変えたとき・戻るで表示したときも合わせる
addEventListener("storage", (e) => { if (e.key === KEY) paint(); });
addEventListener("pageshow", paint);
paint();
