import type { ProviderDef } from "./types";

export const HERO_PROVIDERS: ProviderDef[] = [
  { id: "openai", name: "OpenAI", desc: "GPT, GPT Codex, o-series", families: "GPT, GPT Codex", emoji: "🤖", apiKeyEnv: "OPENAI_API_KEY" },
  { id: "anthropic", name: "Anthropic", desc: "Haiku, Sonnet, Opus", families: "Haiku, Sonnet, Opus", emoji: "🧠", apiKeyEnv: "ANTHROPIC_API_KEY" },
];

export const DROPDOWN_PROVIDERS: ProviderDef[] = [
  { id: "google", name: "Google", desc: "Gemini Pro, Gemini Flash", families: "Gemini", emoji: "🔷", apiKeyEnv: "GOOGLE_API_KEY" },
  { id: "azure_openai", name: "Azure OpenAI", desc: "OpenAI models via Azure", families: "GPT (Azure)", emoji: "☁️", apiKeyEnv: "AZURE_OPENAI_API_KEY" },
  { id: "aws_bedrock", name: "AWS Bedrock", desc: "Claude, Titan via AWS", families: "Multi-provider", emoji: "🟠", apiKeyEnv: "AWS_ACCESS_KEY_ID" },
  { id: "mistral", name: "Mistral", desc: "Mistral Large, Codestral", families: "Mistral", emoji: "🌪️", apiKeyEnv: "MISTRAL_API_KEY" },
  { id: "cohere", name: "Cohere", desc: "Command R+, Embed", families: "Command", emoji: "💬", apiKeyEnv: "COHERE_API_KEY" },
  { id: "groq", name: "Groq", desc: "LLaMA, Mixtral (fast)", families: "LLaMA, Mixtral", emoji: "⚡", apiKeyEnv: "GROQ_API_KEY" },
  { id: "together", name: "Together AI", desc: "Open-source models", families: "Open-source", emoji: "🔗", apiKeyEnv: "TOGETHER_API_KEY" },
  { id: "ollama", name: "Ollama", desc: "Run models locally", families: "Local models", emoji: "🦙", apiKeyEnv: "OLLAMA_API_BASE", isBaseUrlOnly: true },
  { id: "custom", name: "Custom", desc: "Any OpenAI-compatible endpoint", families: "Custom", emoji: "⚙️", apiKeyEnv: "CUSTOM_API_KEY", isCustom: true },
];

export const ALL_PROVIDERS = [...HERO_PROVIDERS, ...DROPDOWN_PROVIDERS];
