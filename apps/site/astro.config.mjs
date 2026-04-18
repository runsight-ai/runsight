// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import starlightLlmsTxt from 'starlight-llms-txt';

// https://astro.build/config
export default defineConfig({
	site: 'https://runsight.ai',
	integrations: [
		starlight({
			title: 'Runsight',
			logo: {
				src: './src/assets/logo.svg',
			},
			description: 'YAML-first workflow engine for AI agents.',
			social: [
				{
					icon: 'github',
					label: 'GitHub',
					href: 'https://github.com/runsight-ai/runsight',
				},
			],
			editLink: {
				baseUrl:
					'https://github.com/runsight-ai/runsight/edit/main/apps/site/',
			},
			defaultLocale: 'root',
			locales: {
				root: { label: 'English', lang: 'en' },
			},
			sidebar: [
				{
					label: 'Getting Started',
					items: [
						{ label: 'Quickstart', slug: 'docs/getting-started/quickstart' },
						{ label: 'Installation', slug: 'docs/getting-started/installation' },
						{ label: 'Key Concepts', slug: 'docs/getting-started/key-concepts' },
					],
				},
				{
					label: 'Workflows',
					items: [
						{ label: 'YAML Schema', slug: 'docs/workflows/yaml-schema' },
						{ label: 'Context Governance', slug: 'docs/workflows/context-governance' },
						{ label: 'Block Types', slug: 'docs/workflows/block-types' },
						{ label: 'Transitions & Routing', slug: 'docs/workflows/transitions-and-routing' },
						{ label: 'Sub-Workflows', slug: 'docs/workflows/sub-workflows' },
						{ label: 'Loops', slug: 'docs/workflows/loops' },
						{ label: 'YAML DX Shortcuts', slug: 'docs/workflows/yaml-dx-shortcuts' },
					],
				},
				{
					label: 'Souls',
					items: [
						{ label: 'Overview', slug: 'docs/souls/overview' },
						{ label: 'Soul Files', slug: 'docs/souls/soul-files' },
						{ label: 'Inline Souls', slug: 'docs/souls/inline-souls' },
						{ label: 'Soul Library', slug: 'docs/souls/soul-library' },
					],
				},
				{
					label: 'Tools',
					items: [
						{ label: 'Overview', slug: 'docs/tools/overview' },
						{ label: 'Custom Tools', slug: 'docs/tools/custom-tools' },
						{ label: 'Built-in Tools', slug: 'docs/tools/built-in-tools' },
						{ label: 'Dispatch & Delegate', slug: 'docs/tools/dispatch-and-delegate' },
					],
				},
				{
					label: 'Execution',
					items: [
						{ label: 'Running Workflows', slug: 'docs/execution/running-workflows' },
						{ label: 'Git Integration', slug: 'docs/execution/git-integration' },
						{ label: 'Fork Recovery', slug: 'docs/execution/fork-recovery' },
						{ label: 'Budget & Limits', slug: 'docs/execution/budget-and-limits' },
						{ label: 'Process Isolation', slug: 'docs/execution/process-isolation' },
						{ label: 'Error Handling', slug: 'docs/execution/error-handling' },
					],
				},
				{
					label: 'Visual Builder',
					items: [
						{ label: 'Canvas Overview', slug: 'docs/visual-builder/canvas-overview' },
						{ label: 'Canvas Modes', slug: 'docs/visual-builder/canvas-modes' },
						{ label: 'YAML Editor', slug: 'docs/visual-builder/yaml-editor' },
						{ label: 'Run Detail View', slug: 'docs/visual-builder/run-detail-view' },
					],
				},
				{
					label: 'Configuration',
					items: [
						{ label: 'First-Time Setup', slug: 'docs/configuration/first-time-setup' },
						{ label: 'Providers', slug: 'docs/configuration/providers' },
						{ label: 'Fallback Model', slug: 'docs/configuration/fallback' },
						{ label: 'Settings', slug: 'docs/configuration/settings' },
					],
				},
				{
					label: 'Evaluation',
					items: [
						{ label: 'Assertions', slug: 'docs/evaluation/assertions' },
						{ label: 'Custom Assertions', slug: 'docs/evaluation/custom-assertions' },
						{ label: 'Transform Hooks', slug: 'docs/evaluation/transform-hooks' },
						{ label: 'Eval Test Harness', slug: 'docs/evaluation/eval-test-harness' },
						{ label: 'Regressions', slug: 'docs/evaluation/regressions' },
					],
				},
				{
					label: 'Reference',
					items: [
						{ label: 'YAML Schema Reference', slug: 'docs/reference/yaml-schema-reference' },
						{ label: 'Block Type Reference', slug: 'docs/reference/block-type-reference' },
						{ label: 'Assertion Reference', slug: 'docs/reference/assertion-reference' },
						{ label: 'CLI Reference', slug: 'docs/reference/cli-reference' },
						{ label: 'Unified Entity Identity', slug: 'docs/reference/unified-entity-identity' },
						{ label: 'Identity ADR', slug: 'docs/reference/unified-entity-identity-adr' },
					],
				},
			],
			customCss: ['./src/styles/custom.css'],
			plugins: [
				starlightLlmsTxt(),
			],
		}),
	],
});
