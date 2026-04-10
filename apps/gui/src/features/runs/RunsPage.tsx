import { RunRow } from "./RunRow";
import { RunsTab } from "./RunsTab";

export function Component() {
  return <RunsTab RowComponent={RunRow} />;
}
