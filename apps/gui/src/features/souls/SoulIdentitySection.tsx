import { Input } from "@runsight/ui/input";
import { Label } from "@runsight/ui/label";

import { SoulAvatarColorPicker } from "./SoulAvatarColorPicker";
import { SoulFormSection } from "./SoulFormSection";

interface SoulIdentitySectionProps {
  name: string;
  avatarColor: string;
  onNameChange: (value: string) => void;
  onAvatarColorChange: (value: string) => void;
}

export function SoulIdentitySection({
  name,
  avatarColor,
  onNameChange,
  onAvatarColorChange,
}: SoulIdentitySectionProps) {
  return (
    <SoulFormSection title="Identity">
      <div className="space-y-5">
        <div className="space-y-2">
          <Label htmlFor="soul-name">Name</Label>
          <Input
            id="soul-name"
            value={name}
            onChange={(event) => onNameChange(event.currentTarget.value)}
            placeholder="Researcher"
          />
        </div>
        <div className="space-y-2">
          <Label>Avatar Color</Label>
          <SoulAvatarColorPicker value={avatarColor} onChange={onAvatarColorChange} />
        </div>
      </div>
    </SoulFormSection>
  );
}

export type { SoulIdentitySectionProps };
