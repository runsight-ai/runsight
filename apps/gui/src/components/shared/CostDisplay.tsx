interface CostDisplayProps {
  cost?: number | null;
  isEstimate?: boolean;
}

export function CostDisplay({ cost, isEstimate = false }: CostDisplayProps) {
  const value = Number(cost ?? 0);
  return (
    <span className="font-mono text-sm text-[#EDEDF0]">
      ${value.toFixed(4)}
      {isEstimate ? "*" : ""}
    </span>
  );
}

