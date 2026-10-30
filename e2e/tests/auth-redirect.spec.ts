import { expect, test } from "@playwright/test";
import { defaultDestination, safeRedirectPath, signInHref } from "../../frontend/src/lib/auth/redirect";

/** Pure unit tests for the Persian-only locale-prefixed open-redirect guard. */
test.describe("safeRedirectPath", () => {
  const fallback = defaultDestination("fa");

  test("keeps same-origin Persian paths and queries", () => {
    expect(safeRedirectPath("/fa/checkout", "fa")).toBe("/fa/checkout");
    expect(safeRedirectPath("/fa/products/some-shirt", "fa")).toBe("/fa/products/some-shirt");
    expect(safeRedirectPath("/fa/products?color=black&size=m", "fa")).toBe("/fa/products?color=black&size=m");
    expect(safeRedirectPath("/fa", "fa")).toBe("/fa");
  });

  test("rejects unsupported locales and re-prefixes only the supported locale", () => {
    expect(safeRedirectPath("/en/cart", "fa")).toBe(fallback);
    expect(safeRedirectPath("/de/checkout", "fa")).toBe(fallback);
    expect(safeRedirectPath("/fa/cart", "fa")).toBe("/fa/cart");
  });

  test("drops the hash", () => {
    expect(safeRedirectPath("/fa/cart#x", "fa")).toBe("/fa/cart");
  });

  for (const bad of [
    "//evil.com", "//evil.com/fa/cart", "/\\evil.com", "/\\/evil.com",
    "https://evil.com/fa/cart", "http://evil.com", "javascript:alert(1)",
    "data:text/html,x", "evil.com", "checkout", "", "/", "/checkout",
    "/fa/../admin/", "/fa/%2e%2e/admin/", "/\t/evil.com",
    "/fa/cart\nSet-Cookie: x=1", "/fa/sign-in", "/fa/sign-in?next=/fa/cart",
    "/fa/" + "a".repeat(600),
  ]) {
    test(`rejects ${JSON.stringify(bad).slice(0, 40)}`, () => {
      expect(safeRedirectPath(bad, "fa")).toBe(fallback);
    });
  }

  test("rejects non-strings and uses the first of repeated params", () => {
    expect(safeRedirectPath(undefined, "fa")).toBe(fallback);
    expect(safeRedirectPath(42, "fa")).toBe(fallback);
    expect(safeRedirectPath(["/fa/cart", "//evil.com"], "fa")).toBe("/fa/cart");
    expect(safeRedirectPath(["//evil.com", "/fa/cart"], "fa")).toBe(fallback);
  });

  test("signInHref encodes the destination", () => {
    expect(signInHref("fa", "/fa/products?a=1&b=2")).toBe("/fa/sign-in?next=%2Ffa%2Fproducts%3Fa%3D1%26b%3D2");
  });
});
