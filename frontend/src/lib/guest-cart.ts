"use client";

/**
 * Guest cart storage contains catalog display snapshots plus variant IDs only.
 * Snapshots are never authoritative: the authenticated merge endpoint resolves
 * catalog data and prices again from Django before accepting a line.
 */
export type GuestCartLine = {
  variant_size_id: number;
  quantity: number;
  stock_quantity: number;
  product: { id: number; name: string; slug: string };
  color: { name: string; slug: string; hex_color: string };
  variant_size: { id: number; sku: string; label: string };
  unit_price: string;
  image: { url: string; thumbnail_url: string; alt_text: string; width: number; height: number } | null;
};

type StoredGuestCart = { token: string; items: GuestCartLine[] };
const KEY = "vedzmani.guest-cart.v1";

function emptyCart(): StoredGuestCart {
  return { token: crypto.randomUUID(), items: [] };
}

function emit(items: GuestCartLine[]) {
  window.dispatchEvent(new CustomEvent("vedzmani:cart-updated", {
    detail: { itemCount: items.length },
  }));
}

function readStored(): StoredGuestCart {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return emptyCart();
    const parsed = JSON.parse(raw) as Partial<StoredGuestCart>;
    if (typeof parsed.token !== "string" || !Array.isArray(parsed.items)) return emptyCart();
    const items = parsed.items.filter((item): item is GuestCartLine =>
      !!item &&
      Number.isSafeInteger(item.variant_size_id) &&
      item.variant_size_id > 0 &&
      Number.isSafeInteger(item.quantity) &&
      item.quantity > 0 &&
      !!item.product && typeof item.product.slug === "string" &&
      !!item.color && typeof item.color.slug === "string" &&
      !!item.variant_size && typeof item.variant_size.label === "string" &&
      typeof item.unit_price === "string"
    );
    return { token: parsed.token, items };
  } catch {
    return emptyCart();
  }
}

function writeStored(cart: StoredGuestCart) {
  localStorage.setItem(KEY, JSON.stringify(cart));
  emit(cart.items);
}

export function readGuestCart(): StoredGuestCart {
  return readStored();
}

export function addGuestCartItem(item: GuestCartLine): void {
  const stored = readStored();
  const existing = stored.items.find((line) => line.variant_size_id === item.variant_size_id);
  const items = existing
    ? stored.items.map((line) => line.variant_size_id === item.variant_size_id
      ? { ...item, quantity: Math.min(item.stock_quantity, line.quantity + item.quantity) }
      : line)
    : [...stored.items, { ...item, quantity: Math.min(item.stock_quantity, item.quantity) }];
  writeStored({ token: stored.token, items });
}

export function setGuestCartQuantity(variantSizeId: number, quantity: number): GuestCartLine[] {
  const stored = readStored();
  const items = stored.items.map((line) =>
    line.variant_size_id === variantSizeId ? { ...line, quantity: Math.min(line.stock_quantity, Math.max(1, Math.floor(quantity))) } : line
  );
  writeStored({ token: stored.token, items });
  return items;
}

export function removeGuestCartItem(variantSizeId: number): GuestCartLine[] {
  const stored = readStored();
  const items = stored.items.filter((line) => line.variant_size_id !== variantSizeId);
  writeStored({ token: stored.token, items });
  return items;
}

export function clearGuestCart(itemCount = 0): void {
  localStorage.removeItem(KEY);
  window.dispatchEvent(new CustomEvent("vedzmani:cart-updated", {
    detail: { itemCount: Math.max(0, itemCount) },
  }));
}

export function guestCartMergePayload(): { token: string; items: { variant_size_id: number; quantity: number }[] } | null {
  const stored = readStored();
  if (stored.items.length === 0) return null;
  return {
    token: stored.token,
    items: stored.items.map(({ variant_size_id, quantity }) => ({ variant_size_id, quantity })),
  };
}
