"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import type { Locale } from "@/i18n/config";
import { SearchIcon, CloseIcon } from "./icons";

type Product = { id: number; variant_id: number; name: string; slug: string; code: string | null; color: { name: string; slug: string } };
type ResponseData = { results: Product[] };
const HISTORY_KEY = "vedzmani:search-history";

export function MobileSearchPanel({ locale, open, onClose }: { locale: Locale; open: boolean; onClose: () => void }) {
  const router = useRouter();
  const root = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [history, setHistory] = useState<string[]>([]);
  const [results, setResults] = useState<Product[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    let savedHistory: string[] = [];
    try {
      const saved: unknown = JSON.parse(localStorage.getItem(HISTORY_KEY) ?? "[]");
      savedHistory = Array.isArray(saved)
        ? saved.filter((item): item is string => typeof item === "string").slice(0, 8)
        : [];
    } catch {
      savedHistory = [];
    }
    const frame = window.requestAnimationFrame(() => {
      setHistory(savedHistory);
      input.current?.focus();
    });
    const onPointerDown = (event: PointerEvent) => {
      if (event.target instanceof Node && !root.current?.contains(event.target)) onClose();
    };
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open, onClose]);

  useEffect(() => {
    const term = query.trim();
    if (!open || !term) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setLoading(true);
      try {
        const response = await fetch(`/api/catalog/variant-products/?search=${encodeURIComponent(term)}&page_size=8`, {
          credentials: "same-origin", cache: "no-store", signal: controller.signal, headers: { Accept: "application/json" },
        });
        if (!response.ok) throw new Error("search_failed");
        const data = await response.json() as ResponseData;
        setResults(data.results ?? []);
      } catch {
        if (!controller.signal.aborted) setResults([]);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }, 280);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [open, query]);

  function remember(value: string) {
    const term = value.trim();
    if (!term) return;
    const next = [term, ...history.filter((item) => item !== term)].slice(0, 8);
    setHistory(next);
    try { localStorage.setItem(HISTORY_KEY, JSON.stringify(next)); } catch { /* optional */ }
  }
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const term = query.trim();
    if (!term) return;
    remember(term);
    onClose();
    router.push(`/${locale}/products?search=${encodeURIComponent(term)}`);
  }
  function choose(product: Product) {
    remember(query);
    onClose();
    router.push(`/${locale}/products/${product.slug}/${encodeURIComponent(product.color.slug)}`);
  }

  return (
    <div
      ref={root}
      data-testid="mobile-search-panel"
      aria-hidden={!open}
      className="grid w-full overflow-hidden transition-[grid-template-rows,opacity] duration-300 ease-out md:hidden"
      style={{ gridTemplateRows: open ? "1fr" : "0fr", opacity: open ? 1 : 0 }}
    >
      <div className="min-h-0 overflow-hidden">
        <div
          className="origin-left px-3 pb-3 pt-1 transition-transform duration-300 ease-out motion-reduce:transition-none"
          style={{ transform: open ? "scaleX(1)" : "scaleX(0)" }}
        >
          <form onSubmit={submit} className="flex h-12 w-full items-center gap-3 rounded-2xl border border-border bg-background px-3">
            <SearchIcon width={19} height={19} />
            <input
              ref={input}
              type="search"
              role="searchbox"
              aria-label="جستجوی نام یا کد محصول"
              placeholder="جستجوی محصولات"
              autoComplete="off"
              enterKeyHint="search"
              maxLength={100}
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setResults([]);
                setLoading(false);
              }}
              className="h-full min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            />
            <button type="button" onClick={() => { setQuery(""); setResults([]); onClose(); }} aria-label="بستن جستجو" className="inline-flex size-9 shrink-0 items-center justify-center rounded-full hover:bg-muted">
              <CloseIcon />
            </button>
          </form>
          {(query.trim() || history.length > 0) ? (
            <div id="mobile-navbar-search-results" className="mt-2 max-h-[min(42dvh,22rem)] overflow-y-auto rounded-2xl border border-border bg-background p-2 text-foreground shadow-lg">
              {!query.trim() ? (
                <section className="p-2">
                  <h2 className="mb-2 px-2 text-xs font-semibold text-muted-foreground">جستجوهای اخیر</h2>
                  <ul className="flex flex-wrap gap-2">
                    {history.map((item) => <li key={item}><button type="button" onClick={() => setQuery(item)} className="rounded-full border border-border px-3 py-1.5 text-sm hover:bg-muted">{item}</button></li>)}
                  </ul>
                </section>
              ) : loading ? (
                <p role="status" className="p-4 text-center text-sm text-muted-foreground">در حال جستجو…</p>
              ) : results.length ? (
                <ul className="space-y-1">
                  {results.map((product) => (
                    <li key={product.variant_id}>
                      <button type="button" onClick={() => choose(product)} className="flex w-full items-center justify-between gap-3 rounded-xl px-3 py-3 text-start hover:bg-muted">
                        <span className="min-w-0 truncate text-sm font-medium">{product.name} · {product.color.name}</span>
                        <span className="shrink-0 text-xs text-muted-foreground">کد: {product.code ?? "ثبت نشده"}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="p-4 text-center text-sm text-muted-foreground">محصولی با این نام یا کد پیدا نشد.</p>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
