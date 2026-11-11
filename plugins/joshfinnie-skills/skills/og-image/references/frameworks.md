# Wiring an OG image by framework

How to generate the card and attach it to pages in Next.js, Astro, and any other static site. The design rules live in `SKILL.md`. This file covers only plumbing.

- [Fonts](#fonts)
- [Next.js (App Router)](#nextjs-app-router)
- [Astro](#astro)
- [Any other static site](#any-other-static-site)

## Fonts

Satori needs TTF, OTF, or WOFF data. Pick whichever source fits the project:

- **Fontsource packages.** `pnpm add -D @fontsource/<family>` (or the project's package manager), then read `node_modules/@fontsource/<family>/files/<family>-latin-<weight>-normal.woff`. Use the `.woff` files, not `.woff2`.
- **Google Fonts as files in the repo.** The CSS API returns TTF URLs when the request uses an old user agent:

  ```sh
  curl -s -A "Mozilla/4.0" "https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@400;600;700"
  ```

  Download each `src: url(...)` into something like `assets/og-fonts/`, and commit the font's license (`OFL.txt`, from `github.com/google/fonts/tree/main/ofl/<family>`) alongside it.
- **Fonts the project already ships**, if they're in a supported format.

If the project has a design system that lists allowed fonts and the card needs one it doesn't list, ask the user whether to add it to the design system or treat it as a deliberate exception. Don't decide that silently.

## Next.js (App Router)

**Site-wide card.** Create `app/opengraph-image.tsx`:

```tsx
import { readFile } from "node:fs/promises";
import path from "node:path";
import { ImageResponse } from "next/og";

export const alt = "Acme Invoices: an invoice for $1,510.00 stamped Paid, next to the line: Get paid before you leave the job site.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const C = { bg: "#f4f6f9", ink: "#1c2128", accent: "#2340c9" };

export default async function Image() {
  const font = (file: string) => readFile(path.join(process.cwd(), "assets/og-fonts", file));
  const [regular, bold] = await Promise.all([font("Inter-Regular.ttf"), font("Inter-Bold.ttf")]);

  return new ImageResponse(
    <div style={{ display: "flex", width: "100%", height: "100%", background: C.bg, color: C.ink, fontFamily: "Inter" }}>
      {/* left column and mock */}
    </div>,
    {
      ...size,
      fonts: [
        { name: "Inter", data: regular, weight: 400, style: "normal" },
        { name: "Inter", data: bold, weight: 700, style: "normal" },
      ],
    },
  );
}
```

Next.js adds the `og:image`, width, height, type, and alt tags itself. In the root layout's `metadata`, set:

```ts
metadataBase: new URL(process.env.SITE_URL ?? "https://example.com"),
openGraph: { siteName: "Acme Invoices", type: "website" },
twitter: { card: "summary_large_image" },
```

Without `metadataBase` the image URL comes out relative and most unfurlers drop it. Use whatever env var the project already uses for its public URL.

**Per-page cards (blog posts, products).** Add `app/blog/[slug]/opengraph-image.tsx` with `generateStaticParams` for the slugs and `generateImageMetadata` to return a per-page `alt`. Scale the title's font size down for long titles. Once there are two or more card files, move the color map, font loading, and wordmark into a shared module (for example `app/_og/shared.tsx`) so the cards can't drift apart.

The dev URL is `/opengraph-image`, sometimes with a hash query string. Read the real URL from the page's `og:image` tag.

## Astro

Generate the PNG at build time from an endpoint, `src/pages/og.png.ts`:

```ts
import { readFile } from "node:fs/promises";
import path from "node:path";
import { Resvg } from "@resvg/resvg-js";
import type { APIRoute } from "astro";
import satori from "satori";

export const prerender = true;

type Node = { type: string; props: Record<string, unknown> };
const h = (type: string, props: Record<string, unknown>, ...children: (Node | string)[]): Node => ({
  type,
  props: { ...props, children: children.length === 1 ? children[0] : children },
});
const box = (style: Record<string, string | number>, ...children: (Node | string)[]) =>
  h("div", { style: { display: "flex", ...style } }, ...children);

export const GET: APIRoute = async () => {
  const font = (file: string) => readFile(path.join(process.cwd(), "node_modules/@fontsource/inter/files", file));
  const [regular, bold] = await Promise.all([font("inter-latin-400-normal.woff"), font("inter-latin-700-normal.woff")]);

  const tree = box({ width: "100%", height: "100%", background: "#051122", color: "#e9edf0", fontFamily: "Inter" } /* , ... */);

  const svg = await satori(tree as unknown as Parameters<typeof satori>[0], {
    width: 1200,
    height: 630,
    fonts: [
      { name: "Inter", data: regular, weight: 400, style: "normal" },
      { name: "Inter", data: bold, weight: 700, style: "normal" },
    ],
  });
  const png = new Resvg(svg, { fitTo: { mode: "width", value: 1200 } }).render().asPng();
  return new Response(new Uint8Array(png), { headers: { "Content-Type": "image/png" } });
};
```

Install with `pnpm add -D satori @resvg/resvg-js` plus the Fontsource package. The small `h()` and `box()` helpers avoid needing React just for the card.

- Keep the alt text in its own module (for example `src/lib/og.ts`) and import it from the layout. Importing anything from the endpoint file pulls satori and the native resvg binary into the server bundle on SSR sites.
- Set `site` in `astro.config.mjs` and build the URL with `new URL("/og.png", Astro.site)` so it's absolute.
- Add the tags to the layout's `<head>`: `og:image`, `og:image:type`, `og:image:width`, `og:image:height`, `og:image:alt`, `twitter:card`, `twitter:image`, `twitter:image:alt`.
- After `astro build`, confirm `dist/og.png` exists. On SSR deploys, confirm the server bundle doesn't include satori or resvg.

## Any other static site

Write a small Node script (for example `scripts/og.mjs`) that builds the tree with the same `h()` and `box()` helpers, renders with `satori` and `@resvg/resvg-js`, and writes `public/og.png` (or the framework's static folder). Run it as part of the build script so the card regenerates on every deploy, and add the tags from `SKILL.md` to the site's head template with an absolute URL.
