// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import starlightLlmsTxt from 'starlight-llms-txt';
import starlightVersions from 'starlight-versions';

// https://astro.build/config
export default defineConfig({
	site: 'https://runsight.ai',
	base: '/docs',
	redirects: {
		'/': '/docs/',
	},
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
						{ label: 'Quickstart', slug: 'getting-started/quickstart' },
						{ label: 'Installation', slug: 'getting-started/installation' },
						{ label: 'Key Concepts', slug: 'getting-started/key-concepts' },
					],
				},
				{
					label: 'Workflows',
					items: [
						{ label: 'YAML Schema', slug: 'workflows/yaml-schema' },
						{ label: 'Block Types', slug: 'workflows/block-types' },
						{ label: 'Transitions & Routing', slug: 'workflows/transitions-and-routing' },
						{ label: 'Sub-Workflows', slug: 'workflows/sub-workflows' },
						{ label: 'Loops', slug: 'workflows/loops' },
						{ label: 'YAML DX Shortcuts', slug: 'workflows/yaml-dx-shortcuts' },
					],
				},
				{
					label: 'Souls',
					items: [
						{ label: 'Overview', slug: 'souls/overview' },
						{ label: 'Soul Files', slug: 'souls/soul-files' },
						{ label: 'Inline Souls', slug: 'souls/inline-souls' },
						{ label: 'Soul Library', slug: 'souls/soul-library' },
					],
				},
				{
					label: 'Tools',
					items: [
						{ label: 'Overview', slug: 'tools/overview' },
						{ label: 'Custom Tools', slug: 'tools/custom-tools' },
						{ label: 'Built-in Tools', slug: 'tools/built-in-tools' },
						{ label: 'Dispatch & Delegate', slug: 'tools/dispatch-and-delegate' },
					],
				},
				{
					label: 'Visual Builder',
					items: [
						{ label: 'Canvas Overview', slug: 'visual-builder/canvas-overview' },
						{ label: 'Canvas Modes', slug: 'visual-builder/canvas-modes' },
						{ label: 'YAML Editor', slug: 'visual-builder/yaml-editor' },
						{ label: 'Run Detail View', slug: 'visual-builder/run-detail-view' },
					],
				},
				{
					label: 'Configuration',
					items: [
						{ label: 'First-Time Setup', slug: 'configuration/first-time-setup' },
						{ label: 'Providers', slug: 'configuration/providers' },
						{ label: 'Fallback Model', slug: 'configuration/fallback' },
						{ label: 'Settings', slug: 'configuration/settings' },
					],
				},
				{
					label: 'Evaluation',
					items: [
						{ label: 'Assertions', slug: 'evaluation/assertions' },
						{ label: 'Transform Hooks', slug: 'evaluation/transform-hooks' },
						{ label: 'Eval Test Harness', slug: 'evaluation/eval-test-harness' },
						{ label: 'Regressions', slug: 'evaluation/regressions' },
					],
				},
				{
					label: 'Reference',
					items: [
						{ label: 'YAML Schema Reference', slug: 'reference/yaml-schema-reference' },
						{ label: 'Block Type Reference', slug: 'reference/block-type-reference' },
						{ label: 'Assertion Reference', slug: 'reference/assertion-reference' },
						{ label: 'CLI Reference', slug: 'reference/cli-reference' },
					],
				},
			],
			customCss: ['./src/styles/custom.css'],
			plugins: [
				starlightLlmsTxt(),
				starlightVersions({
					versions: [{ slug: '0.x' }],
				}),
			],
		}),
	],
});
