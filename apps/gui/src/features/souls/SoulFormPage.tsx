import { useEffect } from "react";
import {
  useBlocker,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router";

import { PageHeader } from "@/components/shared/PageHeader";
import { useSoul } from "@/queries/souls";
import { Button } from "@runsight/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from "@runsight/ui/dialog";

import { SoulFormBody } from "./SoulFormBody";
import { SoulFormFooter } from "./SoulFormFooter";
import { useSoulForm } from "./useSoulForm";

function buildBreadcrumbLabel(mode: "create" | "edit", role?: string | null) {
  if (mode === "create") {
    return "Souls > New Soul";
  }

  return `Souls > ${role ?? "Soul"} > Edit`;
}

export function Component() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const returnUrl = searchParams.get("return");
  const mode = id ? "edit" : "create";
  const soulQuery = useSoul(id ?? "");

  const form = useSoulForm({
    mode,
    soulId: id,
    initial: soulQuery.data,
    onSuccess: () => {
      if (returnUrl) {
        navigate(returnUrl);
        return;
      }

      navigate("/souls");
    },
  });

  useEffect(() => {
    if (mode === "edit" && soulQuery.data) {
      form.reset(soulQuery.data);
    }
  }, [form, mode, soulQuery.data]);

  const blocker = useBlocker(form.isDirty && !form.isSubmitting);
  const isValid =
    form.values.name.trim().length > 0 && form.values.systemPrompt.trim().length > 0;

  if (mode === "edit" && soulQuery.isLoading) {
    return <div className="p-6 text-sm text-muted">Loading soul…</div>;
  }

  if (mode === "edit" && soulQuery.isError) {
    return (
      <div className="flex h-full flex-col">
        <PageHeader
          title="Soul not found"
          breadcrumbs="Souls > Edit"
          backHref="/souls"
        />
        <div className="px-6 text-sm text-muted">
          We could not load this soul.
        </div>
      </div>
    );
  }

  const pageTitle = mode === "create" ? "New Soul" : "Edit Soul";
  const breadcrumb = buildBreadcrumbLabel(mode, soulQuery.data?.role);

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title={pageTitle}
        breadcrumbs={breadcrumb}
        backHref={returnUrl ?? "/souls"}
      />

      <div className="flex-1 overflow-y-auto pb-24">
        <div className="mx-auto flex max-w-2xl flex-col gap-4 px-6 pb-8">
          <SoulFormBody values={form.values} setField={form.setField} />
        </div>
      </div>

      <SoulFormFooter
        mode={mode}
        returnUrl={returnUrl}
        isDirty={form.isDirty}
        isSubmitting={form.isSubmitting}
        isValid={isValid}
        onCancel={() => navigate(returnUrl ?? "/souls")}
        onSubmit={() => {
          void form.submit();
        }}
      />

      <Dialog open={blocker.state === "blocked"}>
        <DialogContent>
          <DialogTitle>Unsaved changes</DialogTitle>
          <p className="px-5 py-4 text-sm text-muted">
            You have unsaved changes that will be lost if you leave this page.
          </p>
          <DialogFooter>
            <Button variant="ghost" onClick={() => blocker.reset?.()}>
              Keep editing
            </Button>
            <Button variant="secondary" onClick={() => blocker.proceed?.()}>
              Discard changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
