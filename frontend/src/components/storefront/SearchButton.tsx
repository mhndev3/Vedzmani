"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import type { Locale } from "@/i18n/config";
import { SearchIcon, CloseIcon } from "./icons";

type SearchProduct = { id: number; name: string; slug: string; code: string | null };
type SearchResponse = { results: SearchProduct[] };
const HISTORY_KEY = "vedzmani:search-history";

export function SearchButton({ locale }: { locale: Locale }) {
  const router = useRouter();
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [history, setHistory] = useState<string[]>([]);
  const [results, setResults] = useState<SearchProduct[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(HISTORY_KEY) ?? "[]");
      if (Array.isArray(saved)) setHistory(saved.filter((item): item is string => typeof item === "string").slice(0, 8));
    } catch { setHistory([]); }
  }, []);

  useEffect(() => {
    const term = query.trim();
    if (!term) { setResults([]); setLoading(false); return; }
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setLoading(true);
      try {
        const response = await fetch(`/api/catalog/products/?search=${encodeURIComponent(term)}&page_size=8`, {
          credentials: "same-origin", cache: "no-store", signal: controller.signal,
          headers: { Accept: "application/json" },
        });
        if (!response.ok) throw new Error("search_failed");
        const data = await response.json() as SearchResponse;
        setResults(data.results ?? []);
      } catch (error) {
        if (!controller.signal.aborted) setResults([]);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }, 220);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [query]);

  function remember(term: string) {
    const value = term.trim();
    if (!value) return;
    const next = [value, ...history.filter((item) => item !== value)].slice(0, 8);
    setHistory(next);
    try { localStorage.setItem(HISTORY_KEY, JSON.stringify(next)); } catch { /* history is optional */ }
  }

  function open() {
    setQuery("");
    setResults([]);
    dialog.current?.showModal();
    window.setTimeout(() => input.current?.focus(), 0);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const term = query.trim();
    if (!term) return;
    remember(term);
    dialog.current?.close();
    router.push(`/${locale}/products?search=${encodeURIComponent(term)}`);
  }

  function choose(product: SearchProduct) {
    remember(query);
    dialog.current?.close();
    router.push(`/${locale}/products/${product.slug}`);
  }

  return (
    <>
      <button type="button" onClick={open} aria-label="جستجوی محصولات" className="inline-flex size-9 items-center justify-center rounded-lg hover:bg-muted">
        <SearchIcon width={19} height={19} />
      </button>
      <dialog
        ref={dialog}
        onClick={(event) => { if (event.target === event.currentTarget) dialog.current?.close(); }}
        className="fixed inset-x-3 top-[12vh] m-auto max-h-[76vh] w-full max-w-xl overflow-hidden rounded-2xl border border-border bg-background p-0 text-foreground shadow-2xl backdrop:bg-black/50"
      >
        <div className="flex items-center gap-2 border-b border-border p-3">
          <SearchIcon width={19} height={19} />
          <form onSubmit={submit} className="min-w-0 flex-1">
            <input
              ref={input}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="نام یا کد محصول را جستجو کنید"
              aria-label="نام یا کد محصول"
              maxLength={100}
              className="h-10 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            />
          </form>
          <button type="button" onClick={() => dialog.current?.close()} aria-label="بستن جستجو" className="inline-flex size-9 items-center justify-center rounded-lg hover:bg-muted">
            <CloseIcon />
          </button>
        </div>
        <div className="max-h-[60vh] overflow-y-auto p-3">
          {!query.trim() ? (
            history.length > 0 && (
              <section>
                <h2 className="mb-2 text-xs font-semibold text-muted-foreground">جستجوهای اخیر</h2>
                <ul className="flex flex-wrap gap-2">
                  {history.map((item) => (
                    <li key={item}>
                      <button type="button" onClick={() => setQuery(item)} className="rounded-full border border-border px-3 py-1.5 text-sm hover:bg-muted">{item}</button>
                    </li>
                  ))}
                </ul>
              </section>
            )
          ) : loading ? (
            <p role="status" className="p-4 text-center text-sm text-muted-foreground">در حال جستجو…</p>
          ) : results.length > 0 ? (
            <ul className="divide-y divide-border">
              {results.map((product) => (
                <li key={product.id}>
                  <button type="button" onClick={() => choose(product)} className="flex w-full items-center justify-between gap-3 rounded-lg px-3 py-3 text-start hover:bg-muted">
                    <span className="font-medium">{product.name}</span>
                    <span className="shrink-0 text-xs text-muted-foreground">کد: {product.code ?? "ثبت نشده"}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="p-4 text-center text-sm text-muted-foreground">محصولی با این نام یا کد پیدا نشد.</p>
          )}
        </div>
      </dialog>
    </>
  );
}
