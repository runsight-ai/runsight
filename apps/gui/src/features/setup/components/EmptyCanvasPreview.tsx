/**
 * Dashed placeholder box with a "+" icon representing a blank canvas.
 * Used inside the blank SelectionCard on the Setup Choose screen.
 */
export function EmptyCanvasPreview() {
  return (
    <div
      className="flex items-center justify-center h-16 w-full rounded border-2 border-dashed border-border-default text-secondary"
      aria-hidden="true"
    >
      <span className="text-xl font-light">+</span>
    </div>
  );
}
