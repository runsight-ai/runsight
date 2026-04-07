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
					],
				},
				{
					label: 'Souls',
					items: [
						{ label: 'Overview', slug: 'souls/overview' },
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
					label: 'Evaluation',
					items: [
						{ label: 'Assertions', slug: 'evaluation/assertions' },
						{ label: 'Transform Hooks', slug: 'evaluation/transform-hooks' },
						{ label: 'Eval Test Harness', slug: 'evaluation/eval-test-harness' },
						{ label: 'Regressions', slug: 'evaluation/regressions' },
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
