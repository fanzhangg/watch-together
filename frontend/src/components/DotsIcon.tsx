/**
 * The overflow menu's trigger. Drawn rather than the "⋯" character, which is a
 * glyph whose size and baseline shift with the font — it sat noticeably high
 * inside a round button — and which read as a fourth icon idiom next to the eye
 * and the thumbs.
 */
export default function DotsIcon({ size = 18 }: { size?: number }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="currentColor"
      aria-hidden="true"
    >
      <circle cx="5.2" cy="12" r="1.7" />
      <circle cx="12" cy="12" r="1.7" />
      <circle cx="18.8" cy="12" r="1.7" />
    </svg>
  );
}
