/**
 * "Watched" — used on the card's quick-mark button and the detail page's.
 *
 * Drawn rather than an 👁 emoji: emoji rendering varies wildly per platform and
 * can't take the button's colour. This inherits currentColor.
 */
export default function EyeIcon({ size = 18 }: { size?: number }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M1.5 12S5 5.5 12 5.5 22.5 12 22.5 12 19 18.5 12 18.5 1.5 12 1.5 12Z" />
      <circle cx="12" cy="12" r="3.2" />
    </svg>
  );
}
