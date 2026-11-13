"use client";

import { useEffect } from "react";

const RELEASE_VERSION = process.env.NEXT_PUBLIC_RELEASE_TAG || "development";
const VERSION_KEY = "vedzmani:release-version";
const RELOAD_GUARD_KEY = "vedzmani:release-reload-guard";

/**
 * Detects release changes without touching authentication cookies, cart data,
 * customer preferences, or unrelated origin storage. Next's deploymentId is
 * the primary protection against mixing chunks/RSC payloads; this guard also
 * gives returning browsers one clean document navigation after an upgrade.
 */
export function ReleaseCacheGuard() {
  useEffect(() => {
    try {
      const previous = window.localStorage.getItem(VERSION_KEY);
      if (previous === RELEASE_VERSION) return;

      // A browser that has never stored a release may still have an old
      // development/staging document in its navigation cache. Give it one
      // clean load too, but guard the navigation to prevent reload loops.
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
          .then((keys) =>
            Promise.all(
              keys
                .filter((key) => key.startsWith("vedzmani:"))
                .map((key) => window.caches.delete(key)),
            ),
          )
          .then(reload, reload);
      } else {
        reload();
      }
    } catch {
      // Storage may be unavailable in private/restricted contexts. Next's
      // deploymentId still protects release consistency without this guard.
    }
  }, []);

  return null;
}
