import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const settingsSource = readFileSync(new URL("../settings.ts", import.meta.url), "utf8");

type CanonicalImportBindings = {
  named: Map<string, string[]>;
  namespaces: string[];
};

type LocalSchemaConstruction = {
  binding: string;
  body: string;
  statement: string;
};

function escapeForRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function collectCanonicalImportBindings(source: string, modulePath: string): CanonicalImportBindings {
  const bindings: CanonicalImportBindings = {
    named: new Map(),
    namespaces: [],
  };
  const importPattern =
    /import\s+(?:type\s+)?(?:(\*\s+as\s+([A-Za-z_$][\w$]*))|{([\s\S]*?)})\s+from\s+["']([^"']+)["']/g;

  for (const match of source.matchAll(importPattern)) {
    const [, namespaceClause, namespaceName, namedClause, importedPath] = match;

    if (importedPath !== modulePath) {
      continue;
    }

    if (namespaceClause && namespaceName) {
      bindings.namespaces.push(namespaceName);
      continue;
    }

    if (!namedClause) {
      continue;
    }

    for (const rawSpecifier of namedClause.split(",")) {
      const specifier = rawSpecifier.trim();

      if (!specifier) {
        continue;
      }

      const [exportedName, localName = exportedName] = specifier
        .split(/\s+as\s+/)
        .map((part) => part.trim());

      if (!bindings.named.has(exportedName)) {
        bindings.named.set(exportedName, []);
      }

      bindings.named.get(exportedName)!.push(localName);
    }
  }

  return bindings;
}

function getCanonicalSchemaReferences(
  importBindings: CanonicalImportBindings,
  exportedSchemaName: string,
) {
  return [
    ...(importBindings.named.get(exportedSchemaName) ?? []),
    ...importBindings.namespaces.map((namespace) => `${namespace}.${exportedSchemaName}`),
  ];
}

function extractParseTarget(source: string, methodName: string) {
  const methodPattern = new RegExp(
    `${escapeForRegExp(methodName)}\\s*:\\s*async\\s*\\([^)]*\\)\\s*(?::[^=]+)?=>\\s*{([\\s\\S]*?)(?=\\n\\s{2}[A-Za-z_$][\\w$]*\\s*:|\\n};)`,
  );
  const body = source.match(methodPattern)?.[1] ?? "";
  const parseMatch =
    body.match(/return\s+([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)?)\.parse\s*\(/) ??
    body.match(/([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)?)\.parse\s*\(/);

  return parseMatch?.[1];
}

function collectLocalZObjectConstructions(source: string): LocalSchemaConstruction[] {
  const constructions: LocalSchemaConstruction[] = [];
  const declarationPattern =
    /const\s+([A-Za-z_$][\w$]*)\s*=\s*z\.object\s*\(([\s\S]*?)\)\s*;/g;

  for (const match of source.matchAll(declarationPattern)) {
    constructions.push({
      binding: match[1],
      body: match[2],
      statement: match[0],
    });
  }

  return constructions;
}

function matchesAllPatterns(body: string, patterns: RegExp[]) {
  return patterns.every((pattern) => pattern.test(body));
}

function collectLocalConcernBindings(source: string) {
  const localSchemas = collectLocalZObjectConstructions(source);
  const concerns = [
    {
      concern: "provider",
      patterns: [/\bapi_key_preview\b/, /\bcreated_at\b/, /\bupdated_at\b/],
    },
    {
      concern: "fallback",
      patterns: [/\bprovider_id\b/, /\bfallback_provider_id\b/, /\bfallback_model_id\b/],
    },
    {
      concern: "app-settings",
      patterns: [/\bonboarding_completed\b/, /\bfallback_enabled\b/],
    },
    {
      concern: "provider-test",
      patterns: [/\blatency_ms\b/, /\bmodel_count\b/],
    },
  ];

  return localSchemas.flatMap((schema) =>
    concerns
      .filter(({ patterns }) => matchesAllPatterns(schema.body, patterns))
      .map(({ concern }) => ({ ...schema, concern })),
  );
}

describe("settings API shared schema governance", () => {
  it("sources settings-surface parse calls from the canonical @runsight/shared/zod path", () => {
    const importBindings = collectCanonicalImportBindings(settingsSource, "@runsight/shared/zod");
    const parseExpectations = [
      { methodName: "listProviders", exportedSchemaName: "SettingsProviderListResponseSchema" },
      { methodName: "getProvider", exportedSchemaName: "SettingsProviderResponseSchema" },
      { methodName: "createProvider", exportedSchemaName: "SettingsProviderResponseSchema" },
      { methodName: "updateProvider", exportedSchemaName: "SettingsProviderResponseSchema" },
      { methodName: "listFallbackTargets", exportedSchemaName: "SettingsFallbackListResponseSchema" },
      { methodName: "updateFallbackTarget", exportedSchemaName: "SettingsFallbackResponseSchema" },
      { methodName: "getAppSettings", exportedSchemaName: "AppSettingsOutSchema" },
      { methodName: "updateAppSettings", exportedSchemaName: "AppSettingsOutSchema" },
      { methodName: "testProviderConnection", exportedSchemaName: "ProviderTestOutSchema" },
      { methodName: "testProviderCredentials", exportedSchemaName: "ProviderTestOutSchema" },
    ];

    expect(
      importBindings.named.size > 0 || importBindings.namespaces.length > 0,
      "Expected apps/gui/src/api/settings.ts to value-import settings schemas from @runsight/shared/zod",
    ).toBe(true);

    for (const { methodName, exportedSchemaName } of parseExpectations) {
      const canonicalReferences = getCanonicalSchemaReferences(importBindings, exportedSchemaName);
      const parseTarget = extractParseTarget(settingsSource, methodName);

      expect(
        canonicalReferences.length,
        `Expected ${exportedSchemaName} to be sourced from @runsight/shared/zod using a named, aliased, or namespace import in apps/gui/src/api/settings.ts`,
      ).toBeGreaterThan(0);
      expect(
        canonicalReferences,
        `Expected ${methodName} to parse with a symbol originating from @runsight/shared/zod`,
      ).toContain(parseTarget);
    }
  });

  it("does not locally construct or parse settings transport schemas in settings.ts", () => {
    const localConcernBindings = collectLocalConcernBindings(settingsSource);
    const parseTargetsByMethod = [
      "listProviders",
      "getProvider",
      "createProvider",
      "updateProvider",
      "listFallbackTargets",
      "updateFallbackTarget",
      "getAppSettings",
      "updateAppSettings",
      "testProviderConnection",
      "testProviderCredentials",
    ].map((methodName) => ({
      methodName,
      parseTarget: extractParseTarget(settingsSource, methodName),
    }));

    expect(
      localConcernBindings,
      [
        "Expected apps/gui/src/api/settings.ts to stop locally constructing provider/fallback/app-settings transport schemas.",
        `Found local constructions: ${localConcernBindings.map(({ binding, concern }) => `${binding} (${concern})`).join(", ") || "(none)"}`,
      ].join("\n"),
    ).toEqual([]);

    for (const { methodName, parseTarget } of parseTargetsByMethod) {
      expect(
        localConcernBindings.map(({ binding }) => binding),
        `Expected ${methodName} to avoid parsing through a locally constructed settings transport schema`,
      ).not.toContain(parseTarget);
    }
  });
});
