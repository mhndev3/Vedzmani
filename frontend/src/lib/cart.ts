import { apiRequest } from "./browser-api";

/**
 * Types mirror backend/apps/cart/serializers.py exactly (see backend/CART.md).
 * Money is a whole-unit Decimal string; nothing here computes price, stock or totals.
 */
export type CartItem = {
  id: number;
  quantity: number;
  availability: "available" | "insufficient_stock" | "unavailable";
  unit_price: string;
  subtotal: string;
  product: { id: number; name: string; slug: string };
  color: { name: string; slug: string; hex_color: string };
  variant_size: { id: number; sku: string; size: string; label: string };
  image: { url: string; alt_text: string; width: number; height: number } | null;
};

export type Cart = {
  items: CartItem[];
  item_count: number;
  total_quantity: number;
  total: string;
  has_issues: boolean;
};

/** Every call returns the full, server-authoritative cart. */
export const cartApi = {
  get: () => apiRequest<Cart>("GET", "/api/cart/"),
  add: (variantSizeId: number, quantity = 1) =>
    apiRequest<Cart>("POST", "/api/cart/items/", { variant_size_id: variantSizeId, quantity }),
  setQuantity: (itemId: number, quantity: number) =>
    apiRequest<Cart>("PATCH", `/api/cart/items/${itemId}/`, { quantity }),
  remove: (itemId: number) => apiRequest<Cart>("DELETE", `/api/cart/items/${itemId}/`),
};
