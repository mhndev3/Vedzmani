"use client";

import { useEffect } from "react";

const RELEASE_VERSION = process.env.NEXT_PUBLIC_RELEASE_TAG || "development";
const VERSION_KEY = "vedzmani:release-version";
const RELOAD_GUARD_KEY = "vedzmani:release-reload-guard";

/**
 * A new immutable frontend release gets one clean document load. Only this
 * storefront's Cache Storage entries and explicitly namespaced cache keys are
 * cleared; authentication/session cookies and theme preferences are preserved.
 */
export function ReleaseCacheGuard() {
  useEffect(() => {
    try {
      const previous = window.localStorage.getItem(VERSION_KEY);
      if (!previous) {
        window.localStorage.setItem(VERSION_KEY, RELEASE_VERSION);
        return;
      }
      if (previous === RELEASE_VERSION) return;
      if (window.sessionStorage.getItem(RELOAD_GUARD_KEY) === RELEASE_VERSION) {
        window.localStorage.setItem(VERSION_KEY, RELEASE_VERSION);
        return;
      }
      window.sessionStorage.setItem(RELOAD_GUARD_KEY, RELEASE_VERSION);
      const reload = () => {
        window.localStorage.setItem(VERSION_KEY, RELEASE_VERSION);
        window.location.reload();
      };
      if ("caches" in window) {
        void window.caches.keys()
          .then((keys) => Promise.all(keys.filter((key) => key.startsWith("vedzmani:")).map((key) => window.caches.delete(key))))
          .then(reload, reload);
      } else {
        reload();
      }
    } catch {
      // Storage can be disabled; the app remains usable without cache cleanup.
    }
  }, []);

  return null;
}
