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
		'/': '/docs/getting-started/quickstart/',
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
