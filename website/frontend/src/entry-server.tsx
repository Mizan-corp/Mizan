/**
 * Build-time rendering of the public pages (ADR-016), run by scripts/prerender.mjs on the bundle
 * `vite build --ssr src/entry-server.tsx` makes. Never runs in production: nginx serves the files.
 */
import { PassThrough } from "node:stream";
import { prerenderToNodeStream } from "react-dom/static";
import { StaticRouter } from "react-router-dom";
import type { ReactNode } from "react";
import { Root, makeQueryClient } from "./Root";

export { prerenderPages, notFoundPages, SITE_URL } from "./seo/pages";
export { renderHead } from "./seo/head";
export { robotsTxt } from "./seo/robots";

/** The HTML inside <div id="root"> for a path, with every lazy page loaded. */
export async function render(url: string): Promise<string> {
  const Router = ({ children }: { children: ReactNode }) => <StaticRouter location={url}>{children}</StaticRouter>;
  const { prelude } = await prerenderToNodeStream(<Root router={Router} queryClient={makeQueryClient()} />, {
    onError(error) {
      throw error;
    },
  });
  const out = new PassThrough();
  prelude.pipe(out);
  let html = "";
  for await (const chunk of out) html += chunk.toString();
  return html;
}
