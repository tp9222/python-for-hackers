# Debug Information

A single-file, zero-dependency browser diagnostics & recon panel. Open it in a
page context and it profiles the runtime — client details, response and security
headers, cookies, forms, storage, resources, framework fingerprints (including
**Salesforce Commerce Cloud / Demandware**), and a set of heuristic security
findings — all in one searchable, copy-friendly UI.

![single file](https://img.shields.io/badge/build-single--file-blue)
![dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)
![vanilla JS](https://img.shields.io/badge/vanilla-JS-yellow)
![license](https://img.shields.io/badge/license-MIT-lightgrey)

> **Authorized use only.** This is a diagnostic / reconnaissance aid for pages
> you own or are explicitly permitted to test. It only reads what the browser
> already exposes to JavaScript on the current page — it does not exploit,
> modify, or attack anything. Use it responsibly and legally.

---

## Table of contents

- [Features](#features)
- [Screenshots](#screenshots)
- [Usage](#usage)
- [Salesforce Commerce Cloud detection](#salesforce-commerce-cloud-detection)
- [Export & copy](#export--copy)
- [How it works](#how-it-works)
- [Limitations & caveats](#limitations--caveats)
- [Privacy](#privacy)
- [License](#license)

---

## Features

| Section | What it surfaces |
| --- | --- |
| **Client Information** | URL/origin/host/path, referrer, secure-context, UA, platform, languages, timezone, screen/viewport, DPR, CPU cores, device memory, online status, DNT, storage key counts |
| **Interesting Findings** | Heuristic security flags — mixed content, plaintext HTTP, password fields posting over `http://` or cross-origin, sensitive HTML comments, missing/weak security headers, software disclosure |
| **Technology** | Server-side platform guess (from `Server` / `X-Powered-By`), HTTP status, content type |
| **Response Headers** | Every response header readable from a same-origin `fetch` |
| **Security Headers** | Presence check for HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, COOP, CORP |
| **Salesforce Commerce Cloud (SFCC)** | Dedicated Demandware storefront fingerprint — see [below](#salesforce-commerce-cloud-detection) |
| **Detected Frameworks & Libraries** | Client-side detection (React/Next, Vue/Nuxt, Angular, Svelte, jQuery, Bootstrap, WordPress, Shopify, GA/GTM, SFCC, …) with versions where readable |
| **Browser Capabilities** | WebGL GPU vendor/renderer, touch points, plugins, network type/downlink/RTT, WebRTC/WASM/ServiceWorker/Notification support |
| **Performance Timing** | Navigation Timing — DNS, TCP, TLS, TTFB, download, DOM interactive/loaded, transfer size, protocol |
| **Meta Tags** | All `<meta>` name/property/http-equiv values |
| **Cookies** | JavaScript-accessible cookies (non-`HttpOnly`) |
| **Web Storage** | Full `localStorage` + `sessionStorage` key/value dump |
| **Forms & Hidden Fields** | Every form's action/method and its fields (hidden field values shown) |
| **Links** | All anchors, split into internal / external |
| **Images / Iframes** | Source lists |
| **JavaScript / CSS Files** | External script and stylesheet URLs |
| **URLs Found** | Absolute URLs harvested from element attributes and page markup |
| **Endpoint Candidates** | Path/API strings scraped from inline scripts (`/api`, `/graphql`, SFCC controllers, OCAPI, SCAPI, …) |
| **Email Addresses** | Email addresses found in the page |
| **Service Workers** | Registered service-worker script URLs |
| **HTML Comments** | All non-empty HTML comments |

**UI niceties**

- 🔎 **Live search** across every section
- 📋 **Copy** per value, per section, or the whole dataset
- 💾 **Export JSON** (timestamped)
- ▾ **Collapsible sections** + Collapse All / Expand All
- 🌗 **Light / dark theme** (persisted)
- 📱 Responsive layout, no external fonts or scripts

---

## Screenshots

> _Add screenshots here, e.g._ `docs/screenshot-dark.png`

---

## Usage

The tool inspects **the page it is loaded in**. There is nothing to install and
no build step — it is one HTML file with inline CSS/JS.

### 1. Standalone

Open `debug-info.html` directly in a browser. It will profile itself — useful
for a quick look at the UI and your browser/runtime details.

### 2. Served alongside a target (authorized testing)

Place `debug-info.html` on the same origin you are assessing (e.g. drop it into
a test build's web root) and open it. Same-origin requests, cookies, and headers
are then reported for that origin.

### 3. As a bookmarklet / injected snippet

Because it reports on its own document, to point the collectors at an *arbitrary*
page you run them **in that page's context** (via a bookmarklet or a DevTools
snippet that injects the panel). The detection logic (`detectSFCC`,
`collectClient`, `collectEndpoints`, …) is written to be portable for exactly
this. See the source for the collector functions.

> No frameworks, no network calls except a single same-origin `GET` of the
> current URL (to read response headers). Everything else is read from the DOM
> and Web APIs already available to the page.

---

## Salesforce Commerce Cloud detection

A dedicated **Salesforce Commerce Cloud (SFCC / Demandware)** section
fingerprints storefronts and extracts intel. It reports a
`detected · N signals` badge (or `not detected`) and pulls out:

- **Site ID** and **Locale** from `Sites-<id>-Site/<locale>/`
- **Current controller** (e.g. `Product-Show`, `Cart-AddProduct`)
- **Architecture** guess — SiteGenesis (`window.SitePreferences`) vs SFRA
  (`.page[data-action][data-querystring]`)
- **Page namespace** (`window.pageContext.ns`)
- **Instance host / type** (Development / Staging / Production from the hostname)

**Signals it fingerprints on**

| Category | Examples |
| --- | --- |
| URL / host | `/on/demandware.store/`, `*.demandware.net`, `*.commercecloud.salesforce.com` |
| Assets | `demandware.static`, `edgesuite.net` (Akamai) — matched on real DOM elements |
| JS globals | `window.dw`, `dwAnalytics`, `Demandware`, `CQuotient` (Einstein), `SitePreferences`, `pageContext` |
| APIs | OCAPI (`/dw/shop|data|meta/vNN`), SCAPI (`/s/<site>/dw/`, `api.commercecloud.salesforce.com`) |
| Cookies | `dwsid`, `dwanonymous_`, `dwac_`, `__cq_dnt`, … |
| Edge | Akamai response headers |

SFCC is also folded into **Detected Frameworks** and the **Endpoint Candidates**
scanner (controller / OCAPI / SCAPI paths).

> **Note:** `dwsid` / `dwsecuretoken` are typically `HttpOnly`, so JavaScript
> cannot read them — cookie detection is best-effort and leans on the other
> signals. Detection reads `location`, real DOM element attributes, and *other*
> page scripts (never the tool's own markup), so it does not self-match when
> injected into a page.

---

## Export & copy

- **Copy** — every value and every section header has a copy button; copy falls
  back to a legacy path on non-secure (`http://` / `file://`) origins.
- **Copy All** — copies the full collected dataset as pretty-printed JSON.
- **Export JSON** — downloads `debug-information-<timestamp>.json` containing
  `client`, `headers`, `security`, `sfcc`, `frameworks`, `capabilities`,
  `performance`, `storage`, `cookies`, `forms`, `links`, resource lists,
  `endpoints`, `emails`, `findings`, and more.

---

## How it works

- **Client / capabilities** — `navigator`, `screen`, `location`, `performance`,
  WebGL, `Intl`, and feature detection.
- **Headers & technology** — a single same-origin `fetch(location.href, {cache:"no-store"})`;
  response headers readable to JS are shown (`Set-Cookie` is never exposed by the
  browser).
- **DOM harvesting** — forms, scripts, stylesheets, images, iframes, meta tags,
  links, and comments (via a `NodeIterator`).
- **Heuristics** — framework/SFCC fingerprints and the findings list are
  best-effort signals, not guarantees.
- **Safety of rendering** — all page-derived values are HTML-escaped, and copy
  buttons use event delegation with indexed data attributes (page content is
  never interpolated into executable markup).

Every fragile read (`document.cookie`, storage, `navigator.*`) is wrapped so a
single unsupported API can't abort the report.

---

## Limitations & caveats

- It reports on **its own document** — to profile another page, run the
  collectors in that page's context (bookmarklet / injected snippet).
- **Endpoint Candidates** and **URLs Found** are regex-based heuristics — expect
  some noise; treat them as leads, not a definitive map.
- The same-origin `fetch` reflects a fresh `GET` of the current URL, which can
  differ from the original navigation (e.g. POST-only routes, edge caching).
- Framework/SFCC detection can miss heavily customized or proxied deployments.
- `HttpOnly` cookies and headers the browser withholds are, by design, invisible.

---

## Privacy

- No analytics, no telemetry, no third-party requests.
- The only network request is a same-origin `GET` of the current page.
- Exported JSON stays on your machine unless you share it. It can contain
  sensitive data (cookies, storage, hidden form values) — handle exports
  accordingly.

---

## License

MIT — see [`LICENSE`](LICENSE). If no license file is present, add one before
publishing.
