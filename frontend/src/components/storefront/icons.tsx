import type { SVGProps } from "react";

/** Decorative inline icons (aria-hidden). None are directional, so they are RTL-safe. */
function Svg(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={20}
      height={20}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...props}
    />
  );
}

export const MenuIcon = (p: SVGProps<SVGSVGElement>) => (
  <Svg {...p}><path d="M4 7h16M4 12h16M4 17h16" /></Svg>
);
export const CloseIcon = (p: SVGProps<SVGSVGElement>) => (
  <Svg {...p}><path d="M6 6l12 12M18 6L6 18" /></Svg>
);
export const ChevronDownIcon = (p: SVGProps<SVGSVGElement>) => (
  <Svg {...p}><path d="m6 9 6 6 6-6" /></Svg>
);
export const SunIcon = (p: SVGProps<SVGSVGElement>) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </Svg>
);
export const MoonIcon = (p: SVGProps<SVGSVGElement>) => (
  <Svg {...p}><path d="M20 14.5A8 8 0 019.5 4 8 8 0 1020 14.5z" /></Svg>
);
export const SearchIcon = (p: SVGProps<SVGSVGElement>) => (
  <Svg {...p}><circle cx="10.8" cy="10.8" r="6.8" /><path d="m16 16 5 5" /></Svg>
);
export const BagIcon = (p: SVGProps<SVGSVGElement>) => (
  <Svg {...p}><path d="M5 8h14l1 13H4L5 8Z" /><path d="M9 8V6a3 3 0 0 1 6 0v2" /></Svg>
);
export const GlobeIcon = (p: SVGProps<SVGSVGElement>) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M3 12h18M12 3c2.5 2.7 3.8 5.7 3.8 9s-1.3 6.3-3.8 9c-2.5-2.7-3.8-5.7-3.8-9S9.5 5.7 12 3z" />
  </Svg>
);
export const CheckCircleIcon = (p: SVGProps<SVGSVGElement>) => (
  <Svg {...p}><circle cx="12" cy="12" r="9" /><path d="M8 12.5l2.7 2.7L16 9.8" /></Svg>
);
