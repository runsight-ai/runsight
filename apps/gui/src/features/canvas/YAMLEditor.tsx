import { useCallback, useEffect, useRef, useState } from "react";
import Editor from "@monaco-editor/react";
import { editor } from "monaco-editor";
import { Save, Undo, RotateCcw, CheckCircle, XCircle, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/helpers";

interface YAMLEditorProps {
  value: string;
  onChange: (value: string) => void;
  onSave?: () => void;
  isValid: boolean;
  errors: string[];
  nodeCount: number;
  edgeCount: number;
  isDirty: boolean;
  isSynced: boolean;
}

interface StatusBarProps {
  isValid: boolean;
  nodeCount: number;
  edgeCount: number;
  isDirty: boolean;
  isSynced: boolean;
  position: { lineNumber: number; column: number };
}

function StatusBar({
  isValid,
  nodeCount,
  edgeCount,
  isDirty,
  isSynced,
  position,
}: StatusBarProps) {
  return (
    <footer className="h-7 bg-[#16161C] border-t border-[#2D2D35] flex items-center px-4 gap-4 text-xs z-50 flex-shrink-0">
      {/* Validation Status */}
      <div
        className={cn(
          "flex items-center gap-1.5",
          isValid ? "text-[#28A745]" : "text-[#E53935]"
        )}
      >
        {isValid ? (
          <CheckCircle className="w-3.5 h-3.5" />
        ) : (
          <XCircle className="w-3.5 h-3.5" />
        )}
        <span>{isValid ? "Valid YAML" : "Error"}</span>
      </div>

      {/* Separator */}
      <div className="w-px h-3 bg-[#2D2D35]" />

      {/* Node Count */}
      <div className="flex items-center gap-1.5 text-[#9292A0]">
        <svg
          className="w-3.5 h-3.5"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          viewBox="0 0 24 24"
        >
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <path d="M9 3v18M15 3v18" />
        </svg>
        <span>
          {nodeCount} node{nodeCount !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Edge Count */}
      <div className="flex items-center gap-1.5 text-[#9292A0]">
        <svg
          className="w-3.5 h-3.5"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M5 12h14M12 5l7 7-7 7"
          />
        </svg>
        <span>
          {edgeCount} edge{edgeCount !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Sync Indicator */}
      {isSynced && !isDirty && (
        <div className="flex items-center gap-1.5 text-[#28A745]">
          <CheckCircle className="w-3.5 h-3.5" />
          <span>Synced</span>
        </div>
      )}

      {/* Modified Indicator */}
      {isDirty && (
        <div className="flex items-center gap-1.5 text-[#F5A623]">
          <svg
            className="w-3.5 h-3.5"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fillRule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z"
              clipRule="evenodd"
            />
          </svg>
          <span>Modified</span>
        </div>
      )}

      {/* Position */}
      <div className="text-[#5E5E6B] font-mono">
        Ln {position.lineNumber}, Col {position.column}
      </div>

      {/* Encoding */}
      <div className="text-[#5E5E6B]">UTF-8</div>
    </footer>
  );
}

interface ErrorBannerProps {
  errors: string[];
}

function ErrorBanner({ errors }: ErrorBannerProps) {
  if (errors.length === 0) return null;

  return (
    <div className="flex-shrink-0 bg-[rgba(229,57,53,0.1)] border-b border-[#E53935]/30 px-4 py-2">
      <div className="flex items-center gap-2">
        <AlertTriangle className="w-4 h-4 text-[#E53935]" />
        <span className="text-sm text-[#EDEDF0]">
          Fix YAML errors before switching to Visual mode
        </span>
        {errors.length > 0 && (
          <span className="text-xs text-[#9292A0]">
            {errors[0]}
            {errors.length > 1 && ` (+${errors.length - 1} more)`}
          </span>
        )}
      </div>
    </div>
  );
}

export function YAMLEditor({
  value,
  onChange,
  onSave,
  isValid,
  errors,
  nodeCount,
  edgeCount,
  isDirty,
  isSynced,
}: YAMLEditorProps) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const monacoRef = useRef<typeof import("monaco-editor") | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ lineNumber: 1, column: 1 });

  const handleEditorDidMount = useCallback(
    (editor: editor.IStandaloneCodeEditor, monaco: typeof import("monaco-editor")) => {
      editorRef.current = editor;
      monacoRef.current = monaco;

      // Configure Monaco editor options
      editor.updateOptions({
        minimap: { enabled: false },
        folding: true,
        foldingHighlight: true,
        foldingStrategy: "indentation",
        showFoldingControls: "always",
        unfoldOnClickAfterEndOfLine: true,
        lineNumbers: "on",
        lineNumbersMinChars: 3,
        glyphMargin: false,
        scrollbar: {
          vertical: "auto",
          horizontal: "auto",
          useShadows: true,
          verticalHasArrows: false,
          horizontalHasArrows: false,
        },
        overviewRulerLanes: 0,
        overviewRulerBorder: false,
        hideCursorInOverviewRuler: true,
        scrollBeyondLastLine: false,
        renderWhitespace: "selection",
        wordWrap: "on",
        wrappingStrategy: "advanced",
        automaticLayout: true,
        padding: { top: 16, bottom: 16 },
        fontSize: 13,
        fontFamily: "JetBrains Mono, monospace",
        fontLigatures: true,
        tabSize: 2,
        insertSpaces: true,
        detectIndentation: true,
        trimAutoWhitespace: true,
        formatOnPaste: true,
        formatOnType: true,
        quickSuggestions: true,
        suggestOnTriggerCharacters: true,
        acceptSuggestionOnEnter: "on",
        wordBasedSuggestions: "currentDocument",
        parameterHints: { enabled: true },
        hover: { enabled: true },
        links: true,
        contextmenu: true,
        mouseWheelZoom: false,
        cursorStyle: "line",
        cursorWidth: 2,
        cursorBlinking: "blink",
        smoothScrolling: true,
        stickyScroll: { enabled: true, maxLineCount: 5 },
      });

      // Set up keyboard shortcuts
      editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
        onSave?.();
      });

      editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyZ, () => {
        editor.trigger("keyboard", "undo", null);
      });

      // Track cursor position
      editor.onDidChangeCursorPosition((e) => {
        setPosition({
          lineNumber: e.position.lineNumber,
          column: e.position.column,
        });
      });

      // Set initial value
      editor.setValue(value);

      // E2E test hooks: Monaco keyboard input is unreliable in Playwright
      if (containerRef.current) {
        const el = containerRef.current as { __e2eSetValue?: (text: string) => void; __e2eGetValue?: () => string };
        el.__e2eSetValue = (text: string) => {
          editor.setValue(text);
          onChange(text);
        };
        el.__e2eGetValue = () => editor.getValue();
      }
    },
    [onSave, value, onChange]
  );

  const handleFormat = useCallback(() => {
    if (editorRef.current) {
      editorRef.current.trigger("keyboard", "editor.action.formatDocument", null);
    }
  }, []);

  const handleUndo = useCallback(() => {
    if (editorRef.current) {
      editorRef.current.trigger("keyboard", "undo", null);
    }
  }, []);

  const handleSave = useCallback(() => {
    onSave?.();
  }, [onSave]);

  const handleEditorChange = useCallback(
    (newValue: string | undefined) => {
      if (newValue !== undefined) {
        onChange(newValue);
      }
    },
    [onChange]
  );

  return (
    <div
      ref={containerRef}
      className="flex-1 flex flex-col min-h-0 bg-[#0D0D12]"
      data-testid="yaml-editor"
    >
      {/* Toolbar */}
      <div className="h-10 bg-[#16161C] border-b border-[#2D2D35] flex items-center px-4 gap-2 flex-shrink-0">
        <Button
          variant="ghost"
          size="sm"
          onClick={handleSave}
          className="h-7 px-2 text-xs text-[#9292A0] hover:text-[#EDEDF0] hover:bg-[#22222A]"
        >
          <Save className="w-3.5 h-3.5 mr-1.5" />
          Save
          <span className="ml-1.5 text-[10px] text-[#5E5E6B]">⌘S</span>
        </Button>

        <div className="w-px h-5 bg-[#2D2D35] mx-1" />

        <Button
          variant="ghost"
          size="sm"
          onClick={handleUndo}
          className="h-7 px-2 text-xs text-[#9292A0] hover:text-[#EDEDF0] hover:bg-[#22222A]"
        >
          <Undo className="w-3.5 h-3.5 mr-1.5" />
          Undo
          <span className="ml-1.5 text-[10px] text-[#5E5E6B]">⌘Z</span>
        </Button>

        <Button
          variant="ghost"
          size="sm"
          onClick={handleFormat}
          className="h-7 px-2 text-xs text-[#9292A0] hover:text-[#EDEDF0] hover:bg-[#22222A]"
        >
          <RotateCcw className="w-3.5 h-3.5 mr-1.5" />
          Format
        </Button>

        <div className="flex-1" />

        {/* Sync indicator in toolbar */}
        {isSynced && (
          <div className="flex items-center gap-1.5 text-[#28A745] text-xs">
            <CheckCircle className="w-3.5 h-3.5" />
            <span>Synced from Visual</span>
          </div>
        )}
      </div>

      {/* Error Banner */}
      <ErrorBanner errors={errors} />

      {/* Editor Container */}
      <div className="flex-1 relative min-h-0">
        <Editor
          height="100%"
          language="yaml"
          value={value}
          onChange={handleEditorChange}
          onMount={handleEditorDidMount}
          theme="vs-dark"
          options={{
            readOnly: false,
          }}
          loading={
            <div className="flex items-center justify-center h-full text-[#9292A0]">
              <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin mr-2" />
              Loading editor...
            </div>
          }
        />
      </div>

      {/* Status Bar */}
      <StatusBar
        isValid={isValid}
        nodeCount={nodeCount}
        edgeCount={edgeCount}
        isDirty={isDirty}
        isSynced={isSynced}
        position={position}
      />
    </div>
  );
}

// Simple textarea fallback for when Monaco is unavailable
export function YAMLEditorFallback({
  value,
  onChange,
  isValid,
  errors,
  nodeCount,
  edgeCount,
  isDirty,
}: Omit<YAMLEditorProps, "onSave" | "isSynced">) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [lineCount, setLineCount] = useState(1);

  useEffect(() => {
    setLineCount(value.split("\n").length);
  }, [value]);

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-[#0D0D12]">
      {/* Simple Toolbar */}
      <div className="h-10 bg-[#16161C] border-b border-[#2D2D35] flex items-center px-4 gap-2 flex-shrink-0">
        <span className="text-xs text-[#5E5E6B]">Text Editor (Monaco unavailable)</span>
      </div>

      {/* Error Banner */}
      {errors.length > 0 && (
        <div className="flex-shrink-0 bg-[rgba(229,57,53,0.1)] border-b border-[#E53935]/30 px-4 py-2">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-[#E53935]" />
            <span className="text-sm text-[#EDEDF0]">
              Fix YAML errors before switching to Visual mode
            </span>
          </div>
        </div>
      )}

      {/* Editor Area */}
      <div className="flex-1 flex min-h-0 overflow-auto">
        {/* Line Numbers */}
        <div className="flex-shrink-0 bg-[#0D0D12] border-r border-[#2D2D35] py-4 px-2 text-right select-none">
          <div className="font-mono text-[13px] leading-6 text-[#5E5E6B]">
            {Array.from({ length: lineCount }, (_, i) => (
              <div key={i + 1}>{i + 1}</div>
            ))}
          </div>
        </div>

        {/* Textarea */}
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="flex-1 bg-transparent font-mono text-[13px] leading-6 text-[#EDEDF0] p-4 resize-none focus:outline-none whitespace-pre tab-2"
          spellCheck={false}
          style={{ tabSize: 2 }}
        />
      </div>

      {/* Status Bar */}
      <footer className="h-7 bg-[#16161C] border-t border-[#2D2D35] flex items-center px-4 gap-4 text-xs z-50 flex-shrink-0">
        <div
          className={cn(
            "flex items-center gap-1.5",
            isValid ? "text-[#28A745]" : "text-[#E53935]"
          )}
        >
          {isValid ? <CheckCircle className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
          <span>{isValid ? "Valid YAML" : "Error"}</span>
        </div>

        <div className="w-px h-3 bg-[#2D2D35]" />

        <div className="flex items-center gap-1.5 text-[#9292A0]">
          <span>
            {nodeCount} node{nodeCount !== 1 ? "s" : ""}
          </span>
        </div>

        <div className="flex items-center gap-1.5 text-[#9292A0]">
          <span>
            {edgeCount} edge{edgeCount !== 1 ? "s" : ""}
          </span>
        </div>

        <div className="flex-1" />

        {isDirty && (
          <div className="flex items-center gap-1.5 text-[#F5A623]">
            <span>Modified</span>
          </div>
        )}
      </footer>
    </div>
  );
}
