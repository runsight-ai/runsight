import { Workflow, User } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { NodeBadge } from "@/components/shared/NodeBadge";
import { EmptyState } from "@/components/shared/EmptyState";
import { DataTable, type Column } from "@/components/shared/DataTable";

const tableColumns: Column[] = [
  { key: "name", header: "Name", sortable: true },
  { key: "status", header: "Status", sortable: true },
  { key: "cost", header: "Cost", sortable: true, render: (row) => <span>${Number(row.cost).toFixed(4)}</span> },
  { key: "duration", header: "Duration", sortable: true },
];

const tableData = [
  { name: "Code Review", status: "completed", cost: 0.12, duration: "2m 14s" },
  { name: "Deploy to Prod", status: "running", cost: 0.08, duration: "1m 02s" },
  { name: "Test Suite", status: "failed", cost: 0.05, duration: "0m 45s" },
];

export default function ComponentShowcase() {
  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[var(--foreground)]">Component Showcase</h1>
        <p className="text-[var(--muted-foreground)]">Runsight UI Component Library</p>
      </div>

      {/* Status Badges */}
      <Card>
        <CardHeader><CardTitle>Status Badges</CardTitle></CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <StatusBadge status="success" label="Completed" />
            <StatusBadge status="error" label="Failed" />
            <StatusBadge status="warning" label="Warning" />
            <StatusBadge status="running" label="Running" />
            <StatusBadge status="pending" label="Pending" />
            <StatusBadge status="cancelled" label="Cancelled" />
          </div>
        </CardContent>
      </Card>

      {/* Node Badges */}
      <Card>
        <CardHeader><CardTitle>Node Badges</CardTitle></CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <NodeBadge type="soul" label="Soul" />
            <NodeBadge type="task" label="Task" />
            <NodeBadge type="team" label="Team" />
            <NodeBadge type="branch" label="Branch" />
          </div>
        </CardContent>
      </Card>

      {/* Cost Display Removed from Showcase */}
      <Card>
        <CardHeader><CardTitle>Cost Display (Removed)</CardTitle></CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4">
            <span>$0.0420</span>
            <span>$1.2500*</span>
            <span>$0.0000</span>
          </div>
        </CardContent>
      </Card>

      {/* Form Elements */}
      <Card>
        <CardHeader><CardTitle>Form Elements</CardTitle></CardHeader>
        <CardContent>
          <div className="space-y-4 max-w-sm">
            <div>
              <Label htmlFor="email">Email</Label>
              <Input id="email" placeholder="Enter email" />
            </div>
            <div>
              <Label htmlFor="desc">Description</Label>
              <Textarea id="desc" placeholder="Enter description" />
            </div>
            <div className="flex items-center gap-2">
              <Switch id="notif" />
              <Label htmlFor="notif">Enable notifications</Label>
            </div>
            <div>
              <Select>
                <SelectTrigger>
                  <SelectValue placeholder="Select model" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="claude">Claude 3.5</SelectItem>
                  <SelectItem value="gpt4">GPT-4o</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Buttons */}
      <Card>
        <CardHeader><CardTitle>Buttons</CardTitle></CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <Button>Primary</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="outline">Outline</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="destructive">Destructive</Button>
          </div>
        </CardContent>
      </Card>

      {/* Data Table */}
      <Card>
        <CardHeader><CardTitle>Data Table</CardTitle></CardHeader>
        <CardContent>
          <DataTable
            columns={tableColumns}
            data={tableData}
            searchable
            sortable
            searchPlaceholder="Search runs..."
          />
        </CardContent>
      </Card>

      {/* Empty States */}
      <Card>
        <CardHeader><CardTitle>Empty States</CardTitle></CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2">
            <EmptyState
              icon={Workflow}
              title="No workflows"
              description="Create your first workflow to get started"
              action={{ label: "New Workflow", onClick: () => {} }}
            />
            <EmptyState
              icon={User}
              title="No souls"
              description="Add a soul to begin"
              action={{ label: "New Soul", onClick: () => {} }}
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
