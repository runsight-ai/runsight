import { useState, useMemo } from "react";
import { cn } from "@/utils/helpers";
import { Input } from "@runsight/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@runsight/ui/table";
import { ChevronUp, ChevronDown, Search } from "lucide-react";

export interface Column {
  key: string;
  header: string;
  width?: string;
  sortable?: boolean;
  render?: (row: Record<string, unknown>) => React.ReactNode;
  sortValue?: (row: Record<string, unknown>) => string | number | null | undefined;
}

interface DataTableProps {
  columns: Column[];
  data: Record<string, unknown>[];
  searchable?: boolean;
  sortable?: boolean;
  searchPlaceholder?: string;
  className?: string;
  emptyState?: React.ReactNode;
  onRowClick?: (row: Record<string, unknown>) => void;
}

export function DataTable({
  columns,
  data,
  searchable = false,
  sortable = false,
  searchPlaceholder = "Search...",
  className,
  emptyState,
  onRowClick,
}: DataTableProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");

  const filteredData = useMemo(() => {
    if (!searchable || !searchQuery) return data;

    const query = searchQuery.toLowerCase();
    return data.filter((row) =>
      columns.some((col) => {
        const value = row[col.key];
        if (value == null) return false;
        return String(value).toLowerCase().includes(query);
      })
    );
  }, [data, searchQuery, searchable, columns]);

  const sortedData = useMemo(() => {
    if (!sortable || !sortKey) return filteredData;

    const sortColumn = columns.find((column) => column.key === sortKey);

    if (!sortColumn) return filteredData;

    const getSortValue = (row: Record<string, unknown>) =>
      sortColumn.sortValue ? sortColumn.sortValue(row) : row[sortKey];

    const sampleValue = filteredData
      .map((row) => getSortValue(row))
      .find((value) => value != null);
    const isNumericSort = typeof sampleValue === "number";

    return [...filteredData].sort((a, b) => {
      const aVal = getSortValue(a);
      const bVal = getSortValue(b);

      if (aVal == null && bVal == null) return 0;
      if (aVal == null) return sortDirection === "asc" ? -1 : 1;
      if (bVal == null) return sortDirection === "asc" ? 1 : -1;

      const comparison =
        isNumericSort && typeof aVal === "number" && typeof bVal === "number"
          ? aVal - bVal
          : String(aVal).localeCompare(String(bVal));
      return sortDirection === "asc" ? comparison : -comparison;
    });
  }, [columns, filteredData, sortKey, sortDirection, sortable]);

  const handleSort = (key: string) => {
    if (!sortable) return;

    if (sortKey === key) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDirection("asc");
    }
  };

  if (data.length === 0 && emptyState) {
    return <div className={className}>{emptyState}</div>;
  }

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      {searchable && (
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input
            type="text"
            placeholder={searchPlaceholder}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
      )}

      <div className="rounded-lg border border-border-default">
        <Table>
          <TableHeader>
            <TableRow className="border-b border-border-default hover:bg-transparent">
              {columns.map((column) => (
                <TableHead
                  key={column.key}
                  className={cn(
                    "h-11 px-3 text-xs font-medium uppercase tracking-wide text-muted",
                    column.width && `w-[${column.width}]`,
                    sortable && column.sortable && "cursor-pointer select-none"
                  )}
                  onClick={() => column.sortable && handleSort(column.key)}
                >
                  <div className="flex items-center gap-1">
                    {column.header}
                    {sortable && column.sortable && sortKey === column.key && (
                      <span className="text-primary">
                        {sortDirection === "asc" ? (
                          <ChevronUp className="h-3 w-3" />
                        ) : (
                          <ChevronDown className="h-3 w-3" />
                        )}
                      </span>
                    )}
                  </div>
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedData.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center text-sm text-muted"
                >
                  No results found
                </TableCell>
              </TableRow>
            ) : (
              sortedData.map((row, rowIndex) => (
                <TableRow
                  key={rowIndex}
                  className={cn(
                    "border-b border-border-default transition-colors hover:bg-surface-tertiary/50",
                    onRowClick && "cursor-pointer"
                  )}
                  onClick={() => onRowClick?.(row)}
                >
                  {columns.map((column) => (
                    <TableCell key={column.key} className="px-3 py-2.5 text-sm">
                      {column.render
                        ? column.render(row)
                        : (row[column.key] as React.ReactNode)}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
