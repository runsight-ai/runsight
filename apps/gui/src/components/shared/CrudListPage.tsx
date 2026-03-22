import { useState } from "react";
import { PageHeader } from "@/components/shared/PageHeader";
import { DataTable, type Column } from "@/components/shared/DataTable";
import { EmptyState } from "@/components/shared/EmptyState";
import { DeleteConfirmDialog } from "@/components/shared/DeleteConfirmDialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Search, AlertCircle, RotateCcw } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { UseMutationResult } from "@tanstack/react-query";

export interface CrudListPageConfig<T> {
  resourceName: string;
  resourceNamePlural: string;
  icon: LucideIcon;
  useList: () => {
    data: { items: T[]; total: number } | undefined;
    isLoading: boolean;
    error: Error | null;
    refetch: () => void;
  };
  useCreate: () => UseMutationResult<any, Error, any>;
  useUpdate: () => UseMutationResult<any, Error, any>;
  useDelete: () => UseMutationResult<any, Error, string>;
  columns: Column[];
  searchKeys: string[];
  getItemName: (item: T) => string;
  getItemId: (item: T) => string;
  CreateModal: React.ComponentType<{ open: boolean; onClose: () => void }>;
  EditModal: React.ComponentType<{ item: T | null; open: boolean; onClose: () => void }>;
  emptyTitle?: string;
  emptyDescription?: string;
}

interface CrudListPageProps<T> {
  config: CrudListPageConfig<T>;
}

function filterItems<T>(items: T[], searchQuery: string, searchKeys: string[]): T[] {
  if (!searchQuery.trim()) return items;
  const query = searchQuery.toLowerCase();
  return items.filter((item) =>
    searchKeys.some((key) => {
      const value = (item as Record<string, unknown>)[key];
      return typeof value === "string" && value.toLowerCase().includes(query);
    })
  );
}

export function CrudListPage<T>({ config }: CrudListPageProps<T>) {
  const {
    resourceName,
    resourceNamePlural,
    icon: Icon,
    useList: useListHook,
    useDelete: useDeleteHook,
    columns,
    searchKeys,
    getItemName,
    getItemId,
    CreateModal,
    EditModal,
    emptyTitle,
    emptyDescription,
  } = config;

  const { data, isLoading, error, refetch } = useListHook();
  const deleteMutation = useDeleteHook();

  const [searchQuery, setSearchQuery] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [itemToEdit, setItemToEdit] = useState<T | null>(null);
  const [itemToDelete, setItemToDelete] = useState<T | null>(null);

  const items = data?.items || [];
  const totalCount = data?.total || 0;

  // Derive filtered items from search query — no useMemo needed for this scale
  const filteredItems = filterItems(items, searchQuery, searchKeys);

  const handleDelete = async () => {
    if (!itemToDelete) return;
    try {
      await deleteMutation.mutateAsync(getItemId(itemToDelete));
      setItemToDelete(null);
    } catch (err) {
      console.error(`Failed to delete ${resourceName.toLowerCase()}:`, err);
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="flex-1 flex flex-col bg-[var(--background)]">
        <PageHeader title={resourceNamePlural} subtitle="Loading..." />
        <div className="flex-1 p-6">
          <div className="bg-[var(--card)] border border-[var(--border)] rounded-lg overflow-hidden">
            <div className="h-14 border-b border-[var(--border)] flex items-center px-4">
              <div className="h-4 w-32 bg-[var(--border)] rounded animate-pulse" />
            </div>
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-16 border-b border-[var(--border)] flex items-center px-4 gap-4">
                <div className="h-10 w-10 bg-[var(--border)] rounded-md animate-pulse" />
                <div className="flex-1">
                  <div className="h-4 w-48 bg-[var(--border)] rounded animate-pulse mb-2" />
                  <div className="h-3 w-32 bg-[var(--border)] rounded animate-pulse" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="flex-1 flex flex-col bg-[var(--background)]">
        <PageHeader title={resourceNamePlural} />
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="text-center max-w-md">
            <AlertCircle className="h-12 w-12 mx-auto mb-4 text-destructive" />
            <h3 className="text-lg font-medium text-foreground mb-2">
              Failed to load {resourceNamePlural.toLowerCase()}
            </h3>
            <p className="text-sm text-muted-foreground mb-4">
              {error instanceof Error
                ? error.message
                : `An error occurred while fetching ${resourceNamePlural.toLowerCase()}.`}
            </p>
            <Button onClick={() => refetch()} variant="outline">
              <RotateCcw className="h-4 w-4 mr-2" />
              Retry
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // Empty state — no items at all
  if (items.length === 0) {
    return (
      <div className="flex-1 flex flex-col bg-[var(--background)]">
        <PageHeader
          title={resourceNamePlural}
          subtitle={`0 ${resourceNamePlural.toLowerCase()}`}
          actions={
            <Button
              className="h-9 px-4 bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-white"
              onClick={() => setShowCreateModal(true)}
            >
              <Plus className="w-4 h-4 mr-2" />
              New {resourceName}
            </Button>
          }
        />
        <div className="flex-1 flex items-center justify-center p-8">
          <EmptyState
            icon={Icon}
            title={emptyTitle || `No ${resourceNamePlural.toLowerCase()} found`}
            description={emptyDescription || `Create your first ${resourceName.toLowerCase()} to get started.`}
            action={{
              label: `Create ${resourceName}`,
              onClick: () => setShowCreateModal(true),
            }}
          />
        </div>
        <CreateModal open={showCreateModal} onClose={() => setShowCreateModal(false)} />
      </div>
    );
  }

  const hasSearchResults = filteredItems.length > 0;

  return (
    <div className="flex-1 flex flex-col bg-[var(--background)]">
      <PageHeader
        title={resourceNamePlural}
        subtitle={`${totalCount} ${resourceName.toLowerCase()}${totalCount !== 1 ? "s" : ""}`}
        actions={
          <Button
            className="h-9 px-4 bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-white"
            onClick={() => setShowCreateModal(true)}
          >
            <Plus className="w-4 h-4 mr-2" />
            New {resourceName}
          </Button>
        }
      />

      {/* Search bar */}
      <div className="h-14 border-b border-[var(--border)] flex items-center gap-3 px-4 bg-[var(--card)]">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            placeholder={`Search ${resourceNamePlural.toLowerCase()}...`}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label={`Search ${resourceNamePlural.toLowerCase()}`}
            className="h-9 pl-9 bg-[var(--background)] border-[var(--border)] rounded-md text-sm text-foreground placeholder:text-[var(--muted-subtle)] focus:border-[var(--primary)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0"
          />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {!hasSearchResults ? (
          <div className="flex items-center justify-center h-full">
            <EmptyState
              icon={Search}
              title={`No ${resourceNamePlural.toLowerCase()} match your search`}
              description={`No results found for "${searchQuery}". Try adjusting your search.`}
              action={{
                label: "Clear search",
                onClick: () => setSearchQuery(""),
              }}
            />
          </div>
        ) : (
          <DataTable
            columns={columns}
            data={filteredItems.map((item) => item as Record<string, unknown>)}
            className="bg-[var(--card)] border border-[var(--border)] rounded-lg overflow-hidden"
            onRowClick={(row) => setItemToEdit(row as T)}
          />
        )}
      </div>

      {/* Delete confirmation */}
      <DeleteConfirmDialog
        open={!!itemToDelete}
        onClose={() => setItemToDelete(null)}
        onConfirm={handleDelete}
        isPending={deleteMutation.isPending}
        resourceName={resourceName}
        itemName={itemToDelete ? getItemName(itemToDelete) : undefined}
      />

      {/* Create modal */}
      <CreateModal open={showCreateModal} onClose={() => setShowCreateModal(false)} />

      {/* Edit modal */}
      <EditModal item={itemToEdit} open={!!itemToEdit} onClose={() => setItemToEdit(null)} />
    </div>
  );
}
