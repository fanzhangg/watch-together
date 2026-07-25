/**
 * 👍 / 👎 as a drawn icon, for the same reason EyeIcon exists: an emoji renders
 * differently on every platform, carries its own colour and internal detail, and
 * can't take the button's. Next to the eye's clean 2px stroke, emoji thumbs were
 * the busiest thing on the page.
 *
 * Down is up rotated half a turn, so the two are exactly symmetrical rather than
 * two hand-drawn shapes that nearly match.
 */
export default function ThumbIcon({
  up = true,
  size = 18,
}: {
  up?: boolean;
  size?: number;
}) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <g transform={up ? undefined : "rotate(180 12 12)"}>
        <rect x="2.4" y="10.6" width="3.9" height="10.2" rx="1.3" />
        <path d="M6.3 10.9 10.7 3.1a2.2 2.2 0 0 1 2.2 2.2V9.2h5.4a2 2 0 0 1 2 2.35l-1.15 6.8A2.3 2.3 0 0 1 16.9 20.8H6.3Z" />
      </g>
    </svg>
  );
}
