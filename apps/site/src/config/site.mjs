export const siteIdentity = {
	name: 'Runsight',
	siteUrl: 'https://runsight.ai',
	locale: 'en_US',
	tagline: 'YAML-first workflow engine for AI agents',
	homepageTitle: 'Runsight — YAML-first workflow engine for AI agents',
	homepageDescription:
		'Design agent workflows in YAML. Commit to Git. Track cost per run. Evaluate with built-in assertions. Open source, self-hosted.',
	docsDescription: 'YAML-first workflow engine for AI agents.',
	author: {
		name: 'Cubic',
		url: 'https://www.cubic.dev/',
	},
	datePublished: '2026-04-08T00:00:00Z',
	dateModified: '2026-05-10T00:00:00Z',
	socialImagePath: '/social/runsight-preview.svg',
	socialImageAlt:
		'Runsight social preview card with the tagline YAML-first workflow engine for AI agents.',
	links: {
		homepage: '/',
		docs: '/docs/',
		feed: '/feed.xml',
		quickstart: '/docs/getting-started/quickstart/',
		skills: '/skills.md',
		github: 'https://github.com/runsight-ai/runsight',
	},
	llms: {
		summary:
			'Runsight is an open source, Git-native workflow engine for AI agents. It helps engineers design workflows in YAML, commit them to Git, track cost per run, and evaluate behavior with built-in assertions.',
		details: `Runsight is for engineers who want readable workflow files, local-first control, and a practical way to design, run, and observe AI workflows.

Start here:
- [Homepage](https://runsight.ai/): product overview, positioning, and high-level capabilities.
- [Documentation](https://runsight.ai/docs/): complete product docs.
- [Quickstart](https://runsight.ai/docs/getting-started/quickstart/): fastest path to install and run Runsight.

Use the documentation sets below when an implementation task needs more detail than the homepage summary.`,
	},
};

export function withSiteUrl(pathname = '/') {
	return new URL(pathname, siteIdentity.siteUrl).toString();
}
