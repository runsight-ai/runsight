import { readFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

const [mode, target] = process.argv.slice(2);

function assert(condition, message) {
	if (!condition) {
		throw new Error(message);
	}
}

function expectIncludes(haystack, needle, label) {
	assert(haystack.includes(needle), `${label} is missing "${needle}"`);
}

function expectContentType(contentType, expected, label) {
	assert(contentType?.includes(expected), `${label} should have content type including "${expected}"`);
}

async function readDistFile(relativePath) {
	const distDir = path.join(process.cwd(), "dist");
	return readFile(path.join(distDir, relativePath), "utf8");
}

async function fetchText(baseUrl, relativePath) {
	const response = await fetch(new URL(relativePath, baseUrl));
	const text = await response.text();
	return { response, text };
}

async function checkRenderedOutput() {
	const robots = await readDistFile("robots.txt");
	const sitemap = await readDistFile("sitemap.xml");
	const sitemapShard = await readDistFile("sitemap-0.xml");
	const llms = await readDistFile("llms.txt");
	const llmsSmall = await readDistFile("llms-small.txt");
	const llmsFull = await readDistFile("llms-full.txt");
	const skills = await readDistFile("skills.md");
	const feed = await readDistFile("feed.xml");
	const home = await readDistFile("index.html");
	const docsHome = await readDistFile("docs/index.html");

	expectIncludes(robots, "User-agent: OAI-SearchBot", "robots.txt");
	expectIncludes(robots, "User-agent: GPTBot", "robots.txt");
	expectIncludes(robots, "Sitemap: https://runsight.ai/sitemap.xml", "robots.txt");

	expectIncludes(sitemap, "https://runsight.ai/sitemap-0.xml", "sitemap.xml");
	expectIncludes(sitemapShard, "https://runsight.ai/", "sitemap-0.xml");
	expectIncludes(sitemapShard, "https://runsight.ai/docs/", "sitemap-0.xml");

	expectIncludes(llms, "[Homepage](https://runsight.ai/)", "llms.txt");
	expectIncludes(llms, "[Documentation](https://runsight.ai/docs/)", "llms.txt");
	expectIncludes(llms, "[AI integration guide](https://runsight.ai/skills.md)", "llms.txt");
	expectIncludes(llms, "https://runsight.ai/llms-small.txt", "llms.txt");
	expectIncludes(llms, "https://runsight.ai/llms-full.txt", "llms.txt");
	expectIncludes(llmsSmall, "<SYSTEM>This is the abridged developer documentation for Runsight</SYSTEM>", "llms-small.txt");
	expectIncludes(llmsFull, "<SYSTEM>This is the full developer documentation for Runsight</SYSTEM>", "llms-full.txt");
	expectIncludes(skills, "# Runsight AI integration guide", "skills.md");
	expectIncludes(skills, "POST /api/workflows/{workflow_id}/runs", "skills.md");
	expectIncludes(feed, "<rss version=\"2.0\"", "feed.xml");
	expectIncludes(feed, "<atom:link href=\"https://runsight.ai/feed.xml\"", "feed.xml");

	expectIncludes(home, 'rel="canonical" href="https://runsight.ai/"', "index.html");
	expectIncludes(home, 'rel="sitemap" href="/sitemap.xml"', "index.html");
	expectIncludes(home, 'type="application/rss+xml" title="Runsight updates"', "index.html");
	expectIncludes(home, 'type="text/markdown" title="Runsight AI integration guide"', "index.html");
	expectIncludes(home, 'name="author" content="Runsight"', "index.html");
	expectIncludes(home, 'name="article:published_time"', "index.html");
	expectIncludes(home, 'property="og:title"', "index.html");
	expectIncludes(home, 'name="twitter:card"', "index.html");
	expectIncludes(home, 'type="application/ld+json"', "index.html");
	expectIncludes(home, "https://runsight.ai/social/runsight-preview.svg", "index.html");
	expectIncludes(home, 'loading="eager" fetchpriority="high"', "index.html");
	expectIncludes(home, 'rel="preload" href="https://api.fontshare.com/v2/css?f[]=satoshi@300,400,500,600,700,900&display=swap"', "index.html");
	expectIncludes(home, 'rel="preload" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap"', "index.html");
	assert(!home.includes('rel="stylesheet" href="/_astro/index'), "index.html should inline landing page CSS instead of linking render-blocking local CSS");
	expectIncludes(home, "How do canvas and YAML stay in sync?", "index.html");
	expectIncludes(docsHome, 'rel="sitemap" href="/sitemap.xml"', "docs/index.html");
	expectIncludes(docsHome, 'type="application/rss+xml" title="Runsight updates"', "docs/index.html");

	console.log("Rendered discoverability checks passed.");
}

async function checkLiveSite(baseUrl) {
	assert(baseUrl, 'Live checks require a base URL, e.g. "https://runsight.ai".');

	const robots = await fetchText(baseUrl, "/robots.txt");
	assert(robots.response.ok, `/robots.txt should return 200, got ${robots.response.status}`);
	expectContentType(robots.response.headers.get("content-type"), "text/plain", "/robots.txt");
	expectIncludes(robots.text, "Sitemap: https://runsight.ai/sitemap.xml", "/robots.txt");

	const sitemap = await fetchText(baseUrl, "/sitemap.xml");
	assert(sitemap.response.ok, `/sitemap.xml should return 200, got ${sitemap.response.status}`);
	expectContentType(sitemap.response.headers.get("content-type"), "xml", "/sitemap.xml");
	expectIncludes(sitemap.text, "https://runsight.ai/sitemap-0.xml", "/sitemap.xml");

	const sitemapShard = await fetchText(baseUrl, "/sitemap-0.xml");
	assert(sitemapShard.response.ok, `/sitemap-0.xml should return 200, got ${sitemapShard.response.status}`);
	expectContentType(sitemapShard.response.headers.get("content-type"), "xml", "/sitemap-0.xml");
	expectIncludes(sitemapShard.text, "https://runsight.ai/", "/sitemap-0.xml");
	expectIncludes(sitemapShard.text, "https://runsight.ai/docs/", "/sitemap-0.xml");

	const llms = await fetchText(baseUrl, "/llms.txt");
	assert(llms.response.ok, `/llms.txt should return 200, got ${llms.response.status}`);
	expectContentType(llms.response.headers.get("content-type"), "text/plain", "/llms.txt");
	expectIncludes(llms.text, "[Homepage](https://runsight.ai/)", "/llms.txt");
	expectIncludes(llms.text, "[AI integration guide](https://runsight.ai/skills.md)", "/llms.txt");
	expectIncludes(llms.text, "https://runsight.ai/llms-small.txt", "/llms.txt");
	expectIncludes(llms.text, "https://runsight.ai/llms-full.txt", "/llms.txt");

	const skills = await fetchText(baseUrl, "/skills.md");
	assert(skills.response.ok, `/skills.md should return 200, got ${skills.response.status}`);
	expectIncludes(skills.text, "# Runsight AI integration guide", "/skills.md");
	expectIncludes(skills.text, "POST /api/workflows/{workflow_id}/runs", "/skills.md");

	const feed = await fetchText(baseUrl, "/feed.xml");
	assert(feed.response.ok, `/feed.xml should return 200, got ${feed.response.status}`);
	expectContentType(feed.response.headers.get("content-type"), "xml", "/feed.xml");
	expectIncludes(feed.text, "<rss version=\"2.0\"", "/feed.xml");

	for (const [pathname, marker] of [
		["/llms-small.txt", "<SYSTEM>This is the abridged developer documentation for Runsight</SYSTEM>"],
		["/llms-full.txt", "<SYSTEM>This is the full developer documentation for Runsight</SYSTEM>"],
	]) {
		const result = await fetchText(baseUrl, pathname);
		assert(result.response.ok, `${pathname} should return 200, got ${result.response.status}`);
		expectContentType(result.response.headers.get("content-type"), "text/plain", pathname);
		expectIncludes(result.text, marker, pathname);
	}

	const homepage = await fetchText(baseUrl, "/");
	assert(homepage.response.ok, `/ should return 200, got ${homepage.response.status}`);
	expectContentType(homepage.response.headers.get("content-type"), "text/html", "/");
	expectIncludes(homepage.text, 'rel="canonical" href="https://runsight.ai/"', "/");
	expectIncludes(homepage.text, 'property="og:title"', "/");
	expectIncludes(homepage.text, 'name="twitter:card"', "/");
	expectIncludes(homepage.text, 'type="application/ld+json"', "/");
	expectIncludes(homepage.text, 'name="author" content="Runsight"', "/");
	expectIncludes(homepage.text, 'loading="eager" fetchpriority="high"', "/");

	console.log(`Live discoverability checks passed for ${baseUrl}`);
}

if (mode === "dist") {
	await checkRenderedOutput();
} else if (mode === "live") {
	await checkLiveSite(target);
} else {
	throw new Error('Usage: node tools/site/check-discoverability.mjs <dist|live> [base-url]');
}
