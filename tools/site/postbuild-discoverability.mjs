import { copyFile } from "node:fs/promises";
import path from "node:path";

const siteDir = process.cwd();
const distDir = path.join(siteDir, "dist");
const sitemapIndexPath = path.join(distDir, "sitemap-index.xml");
const sitemapAliasPath = path.join(distDir, "sitemap.xml");

try {
	await copyFile(sitemapIndexPath, sitemapAliasPath);
	console.log(`Synced ${path.relative(siteDir, sitemapAliasPath)} from sitemap-index.xml`);
} catch (error) {
	const message = error instanceof Error ? error.message : String(error);
	throw new Error(`Failed to create sitemap.xml alias from sitemap-index.xml: ${message}`);
}
