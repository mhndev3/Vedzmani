import { expect, test } from "@playwright/test";
import { defaultDestination, safeRedirectPath, signInHref } from "../../frontend/src/lib/auth/redirect";

/** Pure unit tests (no browser, no server): the `?next=` open-redirect guard. */
test.describe("safeRedirectPath", () => {
  const fallback = defaultDestination("en");

  test("keeps same-origin locale-prefixed paths and queries", () => {
    expect(safeRedirectPath("/en/checkout", "en")).toBe("/en/checkout");
    expect(safeRedirectPath("/en/products/some-shirt", "en")).toBe("/en/products/some-shirt");
    expect(safeRedirectPath("/en/products?color=black&size=m", "en")).toBe("/en/products?color=black&size=m");
    expect(safeRedirectPath("/en", "en")).toBe("/en");
  });

  test("re-prefixes with the current locale", () => {
    expect(safeRedirectPath("/fa/checkout", "en")).toBe("/en/checkout");
    expect(safeRedirectPath("/en/cart", "fa")).toBe("/fa/cart");
  });

  test("drops the hash", () => {
    expect(safeRedirectPath("/en/cart#x", "en")).toBe("/en/cart");
  });

  for (const bad of [
    "//evil.com",
    "//evil.com/en/cart",
    "/\\evil.com",
    "/\\/evil.com",
    "https://evil.com/en/cart",
    "http://evil.com",
    "javascript:alert(1)",
    "data:text/html,x",
    "evil.com",
    "checkout",
    "",
    "/",
    "/checkout",
    "/de/checkout",
    "/en/../admin/",
    "/en/%2e%2e/admin/",
    "/\t/evil.com",
    "/en/cart\nSet-Cookie: x=1",
    "/en/sign-in",
    "/en/sign-in?next=/en/cart",
    "/en/" + "a".repeat(600),
  ]) {
    test(`rejects ${JSON.stringify(bad).slice(0, 40)}`, () => {
      expect(safeRedirectPath(bad, "en")).toBe(fallback);
    });
  }

  test("rejects non-strings and uses the first of repeated params", () => {
    expect(safeRedirectPath(undefined, "en")).toBe(fallback);
    expect(safeRedirectPath(42, "en")).toBe(fallback);
    expect(safeRedirectPath(["/en/cart", "//evil.com"], "en")).toBe("/en/cart");
    expect(safeRedirectPath(["//evil.com", "/en/cart"], "en")).toBe(fallback);
  });

  test("signInHref encodes the destination", () => {
    expect(signInHref("fa", "/fa/products?a=1&b=2")).toBe("/fa/sign-in?next=%2Ffa%2Fproducts%3Fa%3D1%26b%3D2");
  });
});
