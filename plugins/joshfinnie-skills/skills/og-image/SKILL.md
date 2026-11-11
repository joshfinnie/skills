---
name: og-image
description: Builds a code-generated Open Graph share image (the 1200x630 card that shows up when a link is pasted into Slack, Bluesky, iMessage, LinkedIn, Discord, or X), using the site's real brand colors and fonts and a mock of what the product actually does. Wires up the meta tags for Next.js, Astro, or any static site, then renders the PNG and checks it by eye and with a bundled tag checker. Use whenever the user asks for an "OG image", "share image", "social card", "link preview", "unfurl image", "Twitter card", or says links to their site look bad when shared. Not for favicons, app icons, or general marketing graphics.
license: MIT
metadata:
  author: Josh Finnie
---

A share card has one job: someone scrolling a feed should get what the product does in about a second. The cards that work show the product doing its thing, like a signed proposal, a reminder a client can confirm, or an offer price, instead of a logo floating on a gradient. Generate the card from code so it stays in sync with the brand and can be changed later without a design tool.

## 1. Gather the brand before writing code

Read, in this order, whatever exists: design docs (`DESIGN.md`, `PRODUCT.md`, a style guide), CSS tokens (`globals.css`, a Tailwind `@theme`, CSS custom properties), the landing page's headline and subline, and the logo (an SVG component or file). Use the actual hex values and the actual display and body fonts. A card in a different typeface from the site reads as off-brand.

Look for an existing setup (`opengraph-image.*`, `og.png.*`, `og:image` in a layout) and extend it rather than adding a second one.

Then decide what the mock on the card shows. Ask what a customer holds in their hand after using the product (an invoice, a confirmation email, a dashboard tile, a receipt) and draw that. If it isn't obvious, propose one in a sentence and carry on unless the user objects.

## 2. Compose the card

Start from this layout unless the user or an existing card says otherwise. It reads well at the small sizes feeds display it at.

| Region | Contents |
|---|---|
| Canvas | 1200x630. Brand background, flat or with a soft radial gradient toward the mock. |
| Left column, about 620 to 660px wide, padded about `60px 0 60px 72px`, spaced with `justify-content: space-between` | Top: logo mark plus wordmark at 34 to 38px. Middle: the headline at 64 to 76px with tight line height (0.98 to 1.08) and slightly negative letter spacing. Bottom: one muted subline at 26 to 28px. |
| Right side | The product mock in brand colors with realistic data. Tilt it 2 to 4 degrees, put an accent-colored backing card behind it tilted the other way, and give it a soft shadow such as `0 24px 48px -20px rgba(0,0,0,0.35)`. |

Small touches that help: a stamp or badge on the mock ("Paid", "Confirmed"), a slip overlapping the mock's corner with one key number, faint background linework at low opacity.

Copy:

- The headline is the product's promise, ideally the same line the landing page leads with. Specific beats clever.
- Mock data is concrete and believable (`$1,510.00`, `38 cards`, a plausible customer name). Placeholder text like lorem ipsum or `$XX` makes the product look unfinished.
- Highlighting one phrase of the headline in the accent color can help. More than one dilutes it.
- Keep text large. Feeds often show the card at a third of its size, so anything under about 18px disappears.

## 3. Render it

Use [Satori](https://github.com/vercel/satori), which turns a JSX-like tree into SVG, then rasterize to PNG. Next.js ships this as `next/og`. Elsewhere, pair `satori` with `@resvg/resvg-js`. For per-framework wiring (Next.js App Router, Astro, and a plain build script for any other static site), read [references/frameworks.md](references/frameworks.md).

Satori supports only a subset of CSS, and these limits cause most failures:

- Fonts must be real TTF, OTF, or WOFF files passed in at render time. WOFF2 doesn't work and there is no system font fallback. Load only the two or three weights you use. [references/frameworks.md](references/frameworks.md) covers where to get the files.
- Any element with more than one child needs `display: "flex"`. Satori throws otherwise, so default every box to flex.
- No CSS grid, no CSS variables, no `calc()`. Put literal colors in a small map at the top of the file (`const C = { ink: "#1c2128", ... }`).
- Text wraps on its own. Watch for a single word alone on the last line and for text running into the mock. Fix it by splitting lines explicitly (a column of spans) or by adjusting width and size. `whiteSpace: "nowrap"` plus `flexShrink: 0` keeps prices and line items on one line.
- `position: "absolute"` works inside a relative flex parent. Use it for the backing card, stamps, and slips.
- Inline SVG paths render well, so reuse the logo's SVG path rather than embedding an image of it. Local raster images go in as base64 data URIs.

## 4. Alt text and tags

Write `og:image:alt` to describe what the image actually shows, in the form "Brand: what the mock shows, and the headline." For example: "Acme Invoices: an invoice for $1,510.00 stamped Paid, next to the line: Get paid before you leave the job site."

The page needs, with absolute URLs: `og:title`, `og:description`, `og:image`, `og:image:width` (1200), `og:image:height` (630), `og:image:alt`, `twitter:card` set to `summary_large_image`, and `twitter:image`. A relative `og:image` is the most common reason a card doesn't show up, because most unfurlers won't resolve it.

## 5. Verify by looking at it

Don't call the card done until you've looked at the PNG.

1. Start the dev server, fetch the image, and open it in an image viewer, or with your file-reading tool if it displays images.
2. Look hard at: orphaned words, text touching the mock, shadows clipped at the canvas edge, uneven padding, a fallback font (it looks obviously wrong), and low-contrast sublines. Fix them and render again until it's clean.
3. Check the tags and the image together:

   ```sh
   python3 scripts/check_og.py http://localhost:3000/ --out /tmp/og-check.png
   ```

   It lists every OG and Twitter tag, fetches the image, confirms it's 1200x630 and under 5MB, flags relative URLs and the wrong card type, and exits 1 on any problem. Open the saved PNG to confirm it's the image you expect.
4. Run the production build to make sure the image still generates there.
5. After deploy, run the checker against the live URL. Tell the user that Slack, LinkedIn, and others cache unfurls, so links shared before the change may keep the old card for a while. LinkedIn's Post Inspector forces a refresh.

When finished, give the user the PNG's path and one short paragraph describing the layout and what the mock shows.
