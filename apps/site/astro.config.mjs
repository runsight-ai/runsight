// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import starlightLlmsTxt from 'starlight-llms-txt';
import starlightVersions from 'starlight-versions';

// https://astro.build/config
export default defineConfig({
	site: 'https://runsight.ai',
	base: '/docs',
	integrations: [
		starlight({
			title: 'Runsight',
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
