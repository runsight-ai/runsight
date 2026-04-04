import * as React from "react"

import { Badge } from "./badge"
import { Input } from "./input"
import { Label } from "./label"
import { cn } from "../../utils/helpers"

interface TagInputProps {
  label: string
  placeholder: string
  tags: string[]
  onChange: (tags: string[]) => void
}

export function TagInput({ label, placeholder, tags, onChange }: TagInputProps) {
  const [inputValue, setInputValue] = React.useState("")

  function addTag(value: string) {
    const trimmed = value.trim()
    if (trimmed && !tags.includes(trimmed)) {
      onChange([...tags, trimmed])
    }
    setInputValue("")
  }

  function removeTag(index: number) {
    onChange(tags.filter((_, i) => i !== index))
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault()
      addTag(inputValue)
    }

    if (e.key === "Backspace" && inputValue === "" && tags.length > 0) {
      removeTag(tags.length - 1)
    }
  }

  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <div
        className={cn(
          "flex flex-wrap gap-1.5 border border-border-default rounded-md px-2 py-1.5",
          "focus-within:ring-2 focus-within:ring-border-focus"
        )}
      >
        {tags.map((tag, i) => (
          <Badge key={tag} variant="neutral">
            <span className="max-w-[200px] truncate">{tag}</span>
            <button
              type="button"
              className="text-muted hover:text-primary transition-colors"
              onClick={() => removeTag(i)}
              aria-label={`Remove ${tag}`}
            >
              ×
            </button>
          </Badge>
        ))}
        <Input
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={tags.length === 0 ? placeholder : ""}
          className="flex-1 min-w-[120px] border-0 bg-transparent px-0 py-0 shadow-none focus-within:border-transparent focus-within:shadow-none"
        />
      </div>
    </div>
  )
}
