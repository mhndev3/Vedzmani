"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import type { Locale } from "@/i18n/config";
import { SearchIcon, CloseIcon } from "./icons";

type SearchProduct = { id: number; name: string; slug: string; code: string | null };
type SearchResponse = { results: SearchProduct[] };
const HISTORY_KEY = "vedzmani:search-history";

export function SearchButton({ locale }: { locale: Locale }) {
  const router = useRouter();
  const root = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [query, setQuery] = useState("");
  const [history, setHistory] = useState<string[]>([]);
  const [results, setResults] = useState<SearchProduct[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!expanded) return;
    const onPointerDown = (event: PointerEvent) => {
      if (event.target instanceof Node && !root.current?.contains(event.target)) {
        setExpanded(false);
        setQuery("");
        setResults([]);
        setLoading(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setExpanded(false);
        setQuery("");
        setResults([]);
        setLoading(false);
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [expanded]);

  useEffect(() => {
    const term = query.trim();
    if (!expanded || !term) {
      setResults([]);
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    const timer = window.setTimeout(async () => {
      try {
        const response = await fetch(`/api/catalog/products/?search=${encodeURIComponent(term)}&page_size=8`, {
          credentials: "same-origin",
          cache: "no-store",
          signal: controller.signal,
          headers: { Accept: "application/json" },
        });
        if (!response.ok) throw new Error("search_failed");
        const data = await response.json() as SearchResponse;
        setResults(data.results ?? []);
      } catch {
        if (!controller.signal.aborted) setResults([]);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }, 280);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [expanded, query]);

  function remember(term: string) {
    const value = term.trim();
    if (!value) return;
    const next = [value, ...history.filter((item) => item !== value)].slice(0, 8);
    setHistory(next);
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
    } catch {
      // Search history is optional when browser storage is unavailable.
    }
  }

  function open() {
    try {
      const saved: unknown = JSON.parse(localStorage.getItem(HISTORY_KEY) ?? "[]");
      setHistory(Array.isArray(saved)
        ? saved.filter((item): item is string => typeof item === "string").slice(0, 8)
        : []);
    } catch {
      setHistory([]);
    }
    setQuery("");
    setResults([]);
    setLoading(false);
    setExpanded(true);
    window.setTimeout(() => input.current?.focus(), 160);
  }

  function close() {
    setExpanded(false);
    setQuery("");
    setResults([]);
    setLoading(false);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const term = query.trim();
    if (!term) return;
    remember(term);
    close();
    router.push(`/${locale}/products?search=${encodeURIComponent(term)}`);
  }

  function choose(product: SearchProduct) {
    remember(query);
    close();
    router.push(`/${locale}/products/${product.slug}`);
  }

  const showPanel = expanded && (query.trim().length > 0 || history.length > 0);

  return (
    <div
      ref={root}
      className={
        "relative z-50 h-10 shrink-0 transition-[width] duration-300 ease-out motion-reduce:transition-none " +
        (expanded
          ? "w-[min(48vw,28rem)] md:w-[min(38vw,30rem)]"
          : "w-10")
      }
    >
      <div
        className={
          "flex h-10 items-center overflow-hidden rounded-full border bg-background transition-[border-color,box-shadow] duration-200 " +
          (expanded
            ? "border-border shadow-sm ring-1 ring-border/60"
            : "border-transparent")
        }
      >
        {expanded ? (
          <button
            type="button"
            onClick={close}
            aria-label="بستن جستجو"
            className="inline-flex size-10 shrink-0 items-center justify-center rounded-full text-muted-foreground transition hover:bg-muted hover:text-foreground"
          >
            <CloseIcon />
          </button>
        ) : null}
        <form onSubmit={submit} className="flex h-full min-w-0 flex-1 items-center">
          <input
            ref={input}
            type="search"
            autoComplete="off"
            enterKeyHint="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onFocus={() => { if (!expanded) open(); }}
            placeholder="جستجوی نام یا کد محصول"
            aria-label="جستجوی نام یا کد محصول"
            aria-expanded={expanded}
            aria-controls="navbar-search-results"
            maxLength={100}
            tabIndex={expanded ? 0 : -1}
            className={
              "h-full min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground " +
              (expanded ? "px-2 opacity-100" : "w-0 px-0 opacity-0")
            }
          />
        </form>
        <button
          type="button"
          onClick={expanded ? () => input.current?.focus() : open}
          aria-label="جستجوی محصولات"
          aria-expanded={expanded}
          className={
            "inline-flex size-10 shrink-0 items-center justify-center rounded-full transition-colors " +
            (expanded ? "text-foreground hover:bg-muted" : "hover:bg-muted")
          }
        >
          <SearchIcon width={19} height={19} />
        </button>
      </div>

      {showPanel ? (
        <div
          id="navbar-search-results"
          className="absolute end-0 top-[calc(100%+0.55rem)] max-h-[min(65dvh,28rem)] w-[min(82vw,28rem)] overflow-y-auto rounded-2xl border border-border bg-background p-2 text-foreground shadow-xl md:w-full"
        >
          {!query.trim() ? (
            <section className="p-2">
              <h2 className="mb-2 px-2 text-xs font-semibold text-muted-foreground">جستجوهای اخیر</h2>
              <ul className="flex flex-wrap gap-2">
                {history.map((item) => (
                  <li key={item}>
                    <button
                      type="button"
                      onClick={() => setQuery(item)}
                      className="rounded-full border border-border px-3 py-1.5 text-sm transition hover:bg-muted"
                    >
                      {item}
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ) : loading ? (
            <p role="status" className="rounded-xl p-4 text-center text-sm text-muted-foreground">در حال جستجو…</p>
          ) : results.length > 0 ? (
            <ul className="space-y-1">
              {results.map((product) => (
                <li key={product.id}>
                  <button
                    type="button"
                    onClick={() => choose(product)}
                    className="flex w-full items-center justify-between gap-3 rounded-xl px-3 py-3 text-start transition hover:bg-muted"
                  >
                    <span className="min-w-0 truncate text-sm font-medium">{product.name}</span>
                    <span className="shrink-0 text-xs text-muted-foreground">کد: {product.code ?? "ثبت نشده"}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="rounded-xl p-4 text-center text-sm text-muted-foreground">محصولی با این نام یا کد پیدا نشد.</p>
          )}
        </div>
      ) : null}
    </div>
  );
}
