/**
 * Dashed placeholder box with a "+" icon representing a blank canvas.
 * Used inside the blank SelectionCard on the Setup Choose screen.
 */
export function EmptyCanvasPreview() {
  return (
    <div
      className="flex items-center justify-center py-6 px-4 bg-surface-primary rounded-md border border-neutral-3"
      aria-hidden="true"
    >
      <div className="flex items-center justify-center w-[100px] h-14 rounded-md border-[1.5px] border-dashed border-border-subtle text-neutral-7">
        <span className="text-xl font-light text-neutral-9">+</span>
      </div>
    </div>
  );
}
