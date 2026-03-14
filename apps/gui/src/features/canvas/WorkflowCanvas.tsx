import { useParams } from "react-router";

export function Component() {
  const { id } = useParams();

  return (
    <div className="p-6">
      <h1 className="text-2xl font-semibold text-[#EDEDF0]">Workflow Canvas</h1>
      <p className="mt-2 text-sm text-[#9292A0]">
        Canvas module is available. Workflow ID: {id ?? "unknown"}.
      </p>
    </div>
  );
}

