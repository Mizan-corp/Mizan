/**
 * The developer documentation in English (the platform's default language). Same articles and
 * slugs as the Arabic set in devDocs.ts; keep both true to the code.
 */
import type { DocSection } from "@app/features/docs/docsData";
import { DOCS_UPDATED as UPDATED, EXT_API as EXT, SDK_URL } from "./sdk";

const MANIFEST = `{
  "id": "acme.visits",
  "name": "الزيارات",
  "name_en": "Visits",
  "version": "1.0.0",
  "kind": "community",
  "icon": "CalendarCheck",
  "description": "Track customer visits.",
  "entities": ["visit"],
  "permissions": [
    {"id": "acme.visits.view", "name": "عرض الزيارات", "name_en": "View visits"}
  ],
  "menu": [
    {"entity": "visit", "label": "الزيارات", "icon": "CalendarCheck", "permission": "acme.visits.view"}
  ],
  "scopes": ["customers:read", "events:sale.confirmed"],
  "webhooks": {"url": "https://acme.example/mizan", "events": ["sale.confirmed"]}
}`;

const ENTITY = `{
  "id": "visit",
  "name": "زيارة",
  "name_en": "Visit",
  "title": "customer",
  "fields": [
    {"key": "customer", "type": "reference", "to": "customers", "label": "العميل", "required": true},
    {"key": "on", "type": "date", "label": "التاريخ"},
    {"key": "fee", "type": "money", "label": "الرسوم"},
    {"key": "state", "type": "select", "options": ["مجدولة", "تمت"], "label": "الحالة"}
  ],
  "list": ["on", "customer", "state"],
  "form": {"sections": [{"id": "main", "label": "الزيارة", "fields": ["customer", "on", "fee", "state"]}]}
}`;

const PAYLOAD = `{
  "id": "<delivery id>",
  "event": "sale.confirmed",
  "created_at": "2026-11-13T09:50:00+00:00",
  "workspace": {"id": "<workspace id>"},
  "module": "acme.visits",
  "data": {"id": "...", "invoice_number": "INV-1042", "customer_id": "...", "branch_id": "...",
           "total": "250.00", "net_total": "250.00", "is_credit": false,
           "lines": [{"product_id": "...", "qty": "1", "unit_price": "250.00", "discount": "0"}]}
}`;

const THEME = `{
  "id": "acme.sunrise",
  "name": "شروق",
  "name_en": "Sunrise",
  "version": "1.0.0",
  "kind": "theme",
  "description": "Warm orange, rounded corners, calm motion.",
  "colors": {
    "light": {"background": "#FAF6F0", "foreground": "#262321", "primary": "oklch(0.55 0.17 40)", "...": "..."},
    "dark":  {"background": "#270F16", "foreground": "#FAF6F0", "primary": "oklch(0.72 0.15 50)", "...": "..."}
  },
  "fonts": {
    "body": "Sunrise Sans",
    "files": [{"family": "Sunrise Sans", "src": "assets/sunrise-sans.woff2", "weight": "100 900"}]
  },
  "radius": "1.25rem",
  "shadows": "raised",
  "motion": "reduced"
}`;

const ACTIVITY_LAYOUT = `acme.laundry/
  manifest.json          kind "activity": family, modules, menus, roles, terms, theme
  modules/
    acme.laundry_orders/ its own modules (manifest.json + entities/)
  variants/
    pos/variant.json     how it adapts Mizan's POS: extra fields, terms, settings
  themes/
    fresh/theme.json     its themes
  seed/orders.json       demo records`;

const ACTIVITY_MANIFEST = `{
  "id": "acme.laundry",
  "name": "مغسلة",
  "name_en": "Laundry",
  "version": "1.0.0",
  "kind": "activity",
  "family": "services",
  "modules": ["pos", "inventory", "sales", "finance", "hr", "acme.laundry_orders"],
  "optional": [],
  "terms": {"item": "قطعة"},
  "home": "/pos",
  "theme": "acme.laundry_fresh",
  "positions": [{"code": "counter_clerk", "name": "موظف الاستقبال", "name_en": "Counter clerk", "suggested_roles": ["cashier"]}],
  "menu": [{"id": "orders", "label": "الطلبات", "items": [
    {"screen": "acme.laundry_orders/order", "label": "طلبات العملاء"},
    {"screen": "pos.pos", "label": "الكاشير"}
  ]}],
  "dashboard": ["pos.recent_sales"],
  "roles": {"cashier": {"home": "pos.pos", "menu": [], "dashboard": ["pos.recent_sales"]}}
}`;

export const EN: DocSection[] = [
  {
    id: "start",
    title: "Getting started",
    titleEn: "Getting started",
    items: [
      {
        slug: "introduction",
        title: "What community modules are",
        titleEn: "What community modules are",
        description: "What your module can add to Mizan today, and how it reaches businesses.",
        category: "Getting started",
        lastUpdated: UPDATED,
        content: {
          overview:
            "A community module adds new kinds of records (entities) to a Mizan workspace, with their screens: a list with search, an add and edit form, and permissions the business owner grants to their staff's roles. Its screens appear in the app's menu under “وحدات إضافية” (more modules). When it needs logic of its own, it talks to your server: reading and writing through the extension API (/ext/v1) and receiving signed webhooks when things happen.",
          sections: [
            {
              id: "declarative",
              title: "Declarative modules, for now",
              body:
                "Today a module is JSON files only: a manifest.json and one file per entity under entities/. No outside code runs on Mizan's servers; that's what makes installing your module safe for the business. Your code runs on your server and reaches the business's data only through the scopes its owner approved.\n\nModules with code running inside Mizan (in isolated containers) will come when the platform moves to its own servers.",
              callout: { type: "note", text: "Two ways to reach workspaces: publish to the marketplace (the Mizan team reviews it, then any workspace installs it from its store), or hand the owner the signed file (.mzm) privately. Paid listings come later; today they are free." },
            },
            {
              id: "pieces",
              title: "The pieces",
              body:
                "• The developer portal (dev.allmizan.live/portal): your account, teams, signing keys and CLI tokens.\n• The mizan command (the mizan-sdk Python package): create, check and sign modules.\n• The package, a .mzm file: the business owner uploads it in the module centre (وحدات المطورين → تثبيت من ملف, “Developer modules → Install from file”).\n• The /ext/v1 API and webhooks, for your server.",
              callout: { type: "tip", text: "Mizan's app is in Arabic. Give your module, entities, fields and menu items Arabic labels (name_en is for listings and the docs)." },
            },
          ],
        },
      },
      {
        slug: "quickstart",
        title: "Quickstart",
        titleEn: "Quickstart",
        description: "From a new account to a module installed in a workspace, in minutes.",
        category: "Getting started",
        lastUpdated: UPDATED,
        content: {
          overview: "You need Python 3.10 or newer. The steps: an account and a team in the portal, then the CLI, then your module.",
          sections: [
            {
              id: "account",
              title: "1. Account and team",
              body:
                "Create an account in the portal, then a team. The team's handle (such as acme) is the first part of every module id of yours (acme.visits) and can't change. Then create a token for your machine under “CLI tokens”.",
            },
            {
              id: "install",
              title: "2. Install the CLI and sign in",
              body: "Install mizan-sdk, then sign in with the token (it starts with mzd_).",
              codeBlock: { language: "bash", code: `pip install ${SDK_URL}\nmizan login\nmizan whoami` },
            },
            {
              id: "module",
              title: "3. Your module",
              body:
                "Create a module from the template, edit it, and check it against the platform's own rules. Then create a signing key for your team (registered, with its certificate saved, automatically) and sign the package.",
              codeBlock: {
                language: "bash",
                code: "mizan module new acme.visits\nmizan check acme.visits\nmizan keys new --team acme\nmizan package acme.visits      # acme.visits-0.1.0.mzm",
              },
            },
            {
              id: "try",
              title: "4. Install it in a workspace",
              body:
                "In a workspace you own: the module centre → وحدات المطورين (developer modules) → تثبيت من ملف (install from file). Choose the package, review what it can access and approve. Its screens appear in the menu under “وحدات إضافية”.",
              callout: { type: "tip", text: "Create a trial workspace at allmizan.live/signup to try your modules without touching real data." },
            },
          ],
        },
      },
    ],
  },
  {
    id: "build",
    title: "Building",
    titleEn: "Building",
    items: [
      {
        slug: "manifest",
        title: "The manifest (manifest.json)",
        titleEn: "The manifest",
        description: "The module's id, version, entities, permissions, menu and scopes.",
        category: "Building",
        lastUpdated: UPDATED,
        content: {
          overview: "At the root of the package. These are all its fields; anything else is refused.",
          sections: [
            { id: "example", title: "A complete example", body: "", codeBlock: { language: "json", filename: "manifest.json", code: MANIFEST } },
            {
              id: "rules",
              title: "Rules",
              body:
                "• id: “<team>.<module>” in lower-case letters, digits and _; the first part must be the handle of the team whose key signs it.\n• version: MAJOR.MINOR.PATCH. Installing a higher version over an older one updates the module and keeps its records.\n• kind: always \"community\".\n• icon: a lucide icon name (such as CalendarCheck).\n• entities: up to 20, each with a file entities/<id>.json.\n• permissions: their ids start with the module id. A menu item that names a permission is shown only to users whose role holds it; without one, every user of the workspace sees it. The workspace's admin holds them all, and the owner grants them to other roles on the roles screen.\n• menu: one item for each entity screen you want in the menu.\n• scopes and webhooks: see “Scopes” and “Webhooks”.\n• Not allowed: router, models, frontend, category, activity.",
            },
            {
              id: "package",
              title: "What a package contains",
              body:
                "manifest.json, README.md and CHANGELOG.md at the root, and entities/, i18n/ and assets/ (json, png, svg, webp, jpg, md and txt files). Up to 4 MB.",
            },
          ],
        },
      },
      {
        slug: "entities",
        title: "Entities and screens",
        titleEn: "Entities and screens",
        description: "Fields and their types, references to the business's records, list columns and form sections.",
        category: "Building",
        lastUpdated: UPDATED,
        content: {
          overview:
            "An entity is a new kind of record. Mizan draws its screen from the definition: a table with the columns you choose, search and pages, an add and edit form with your sections, and delete. Values are validated on the server every time, whether they come from the screen or the API.",
          sections: [
            { id: "example", title: "Example", body: "", codeBlock: { language: "json", filename: "entities/visit.json", code: ENTITY } },
            {
              id: "types",
              title: "Field types",
              body:
                "• text: text (up to 2000 characters).\n• number: a number.\n• money: an amount with two decimals (stored as a string such as \"150.50\").\n• date: YYYY-MM-DD.\n• boolean: yes or no.\n• select: one of options.\n• reference: the id of another record; to is one of your module's entities, or customers, suppliers, products, employees or branches (each needs its read scope, such as customers:read). Mizan checks the record exists in the same workspace.\n\nUp to 60 fields per entity. required makes a field mandatory.",
            },
            {
              id: "screens",
              title: "Title, list and form",
              body:
                "• title: the field that names a record when it's referred to (in pickers and tables). If it is itself a reference, the referenced record's name is shown.\n• list: the table's columns (by default the first four fields).\n• form.sections: the form's sections and the order of their fields (by default one section with every field).\n• Search covers text and select fields.",
            },
          ],
        },
      },
      {
        slug: "scopes",
        title: "Scopes (what a module can access)",
        titleEn: "Scopes",
        description: "What the business owner approves before installing, and what each scope allows.",
        category: "Building",
        lastUpdated: UPDATED,
        content: {
          overview:
            "Your module's own records need no scope. Anything else from the business's data is asked for in scopes, and Mizan shows it to the owner in plain words before installing; on updates, new scopes are marked. Nothing installs until every scope is approved.",
          sections: [
            {
              id: "data",
              title: "Data scopes",
              body:
                "• customers:read: read customers\n• customers:write: add customers\n• suppliers:read: read suppliers\n• products:read: read products and prices\n• stock:read: read stock levels\n• sales:read: read sales invoices and their lines\n• employees:read: read employees\n• branches:read: read branches",
            },
            {
              id: "events",
              title: "Event scopes",
              body:
                "• events:sale.confirmed: when a sale is confirmed\n• events:sale.returned: when a sale is returned (fully or partly)\n• events:customer.created: when a customer is added\n• events:product.updated: when a product changes\n\nrecord.created and record.updated (your module's records) need no scope.",
              callout: { type: "tip", text: "Ask for as little as you need: every extra scope is a reason for an owner to hesitate." },
            },
          ],
        },
      },
      {
        slug: "themes",
        title: "Theme packs",
        titleEn: "Theme packs",
        description: "Colours, fonts, corners, shadows and motion for a whole workspace.",
        category: "Building",
        lastUpdated: UPDATED,
        content: {
          overview:
            "A theme pack changes how all of Mizan looks in a workspace: its colours in light and dark mode, its fonts, corner radius, shadows and motion. Its admin installs it and makes it the workspace's theme; everyone in the workspace sees it, printed documents included. A theme has no code and reaches no data.",
          sections: [
            { id: "example", title: "manifest.json", body: "A theme package is a manifest.json with kind \"theme\", plus its font files under assets/. Start from Mizan's own theme with mizan theme new acme.sunrise.", codeBlock: { language: "json", filename: "manifest.json", code: THEME } },
            {
              id: "colors",
              title: "Colours",
              body:
                "colors.light and colors.dark set the app's design tokens. Required: background, foreground, card, card-foreground, primary, primary-foreground, secondary, secondary-foreground, muted, muted-foreground, accent, accent-foreground, border, input, ring, sidebar, sidebar-foreground, sidebar-primary, sidebar-primary-foreground, sidebar-accent, sidebar-accent-foreground, sidebar-border, sidebar-ring. Optional: popover, popover-foreground, destructive, success, warning (each with -foreground), chart-1 … chart-5.\n\nValues are #hex, rgb() or oklch(). Text must stay readable: foreground on background, card-foreground on card and sidebar-foreground on sidebar need a contrast of 4.5; the others 3. mizan check tells you which pair fails.",
            },
            {
              id: "fonts",
              title: "Fonts, corners, shadows and motion",
              body:
                "• fonts.body, fonts.display, fonts.mono: font family names. Ship the files in assets/ and list them in fonts.files ({family, src, weight: \"400\" or a range \"100 900\", style}); Mizan serves them itself, so themes work on on-site servers without internet. A family without files must be one the device has.\n• radius: the base corner radius, e.g. 0.75rem.\n• shadows: flat, soft or raised.\n• motion: full, reduced or none (for busy tills and accessibility).\n• density: comfortable or compact, a default each user can change on their device.",
              callout: { type: "tip", text: "Mizan's app is mostly Arabic: pick fonts with Arabic letters, or Arabic text falls back to the default font." },
            },
            { id: "ship", title: "Shipping a theme", body: "mizan check and mizan package work as for modules; the owner installs it from the module centre → المظاهر (themes) → install a theme from file, and chooses it. Installing doesn't change the current theme. Activities can also ship themes of their own (activities/<activity>/themes/)." },
          ],
        },
      },
      {
        slug: "activities",
        title: "Business activities",
        titleEn: "Business activities",
        description: "A whole line of business for Mizan: modules, adaptations, menus, roles, themes and demo data.",
        category: "Building",
        lastUpdated: UPDATED,
        content: {
          overview:
            "Every business Mizan serves runs on an activity: retail, pharmacy, restaurant… An activity decides which modules a workspace gets, how they're adapted to the trade, its words, menus and dashboards for each role, its positions, its look and its demo data. Mizan's own activities are built exactly this way, one folder each, and you can build one for a trade Mizan doesn't cover yet with the same framework.",
          sections: [
            { id: "layout", title: "The layout", body: "Create one with mizan activity new acme.laundry: a small, complete activity to start from.", codeBlock: { language: "text", code: ACTIVITY_LAYOUT } },
            { id: "manifest", title: "manifest.json", body: "", codeBlock: { language: "json", filename: "manifest.json", code: ACTIVITY_MANIFEST } },
            {
              id: "rules",
              title: "What goes in it",
              body:
                "• family: general, commerce, food_hospitality, health, education, services, logistics, industry, projects or institutions.\n• modules and optional: Mizan's modules (pos, inventory, sales, finance, hr, …) and its own (<team>.<module>, each a community module in modules/).\n• menu, dashboard, roles: menu groups of screens. Mizan's screens are <module>.<screen> (pos.pos, inventory.products); your entities' screens are <module>/<entity>. Dashboards list widgets (pos.recent_sales). roles gives a role (cashier, …) its own home, menu and dashboard.\n• terms: the trade's words (\"item\": \"قطعة\").\n• positions: job titles and the roles they suggest.\n• theme: one of its themes (themes/) or Mizan's.\n• variants/<module>/variant.json: extra fields on Mizan's records (fields.sale, fields.product…), terms and settings defaults.\n• seed/*.json: demo records for its own entities.\n\nmizan check verifies the shape; Mizan checks every reference (modules, screens, widgets, records, themes) when it receives the package.",
              callout: { type: "note", text: "Activity packages are declarative, like community modules: no code in variants yet (Mizan's own activities add rules in hooks.py). Publish it (mizan publish); once the Mizan team approves it, owners can change an existing workspace to it from the owner panel (the team approves each change too). Its own modules install with the scopes they declare, its themes install, and its menus, terms, variants and positions apply. Approved updates reach every workspace running it: new modules join, nothing leaves. Seed records aren't added to a live workspace, and new workspaces can't start from a developer's activity yet." },
            },
          ],
        },
      },
    ],
  },
  {
    id: "connect",
    title: "Your server",
    titleEn: "Your server",
    items: [
      {
        slug: "api",
        title: "The extension API (/ext/v1)",
        titleEn: "The extension API",
        description: "The installation token, your records, and the business's data by scope.",
        category: "Your server",
        lastUpdated: UPDATED,
        content: {
          overview: `Each installation of your module has a token (starting with mzx_) that the business owner gives you from the module centre (وحدات المطورين → رمز الربط, “connection token”). A token sees that one workspace, and only the scopes its owner approved. Base address: ${EXT}`,
          sections: [
            {
              id: "auth",
              title: "Authentication and limits",
              body:
                "Send the token in the Authorization header. Up to 240 requests a minute. Creating a new token stops the old one at once, and so does uninstalling the module.\n\nErrors: 401 missing or revoked token, 403 scope not granted or workspace suspended, 404 not found, 422 invalid value (the message is in detail).",
              codeBlock: { language: "bash", code: `curl ${EXT}/me -H "Authorization: Bearer mzx_..."` },
            },
            {
              id: "records",
              title: "Your module's records",
              body:
                "• GET /records/{entity}?q=&page=: a page of 50: {items, total, page, pages, labels}\n• POST /records/{entity}: create (values keyed by field)\n• GET /records/{entity}/{id}\n• PATCH /records/{entity}/{id}: partial update\n• DELETE /records/{entity}/{id}",
              codeBlock: {
                language: "python",
                filename: "server.py",
                code: `from mizan_sdk import MizanClient\n\nclient = MizanClient("mzx_...")\nprint(client.me())          # the workspace, module and scopes\nvisits = client.records("visit")\nv = visits.create({"customer": "<customer id>", "on": "2026-11-15", "state": "مجدولة"})\nvisits.update(v["id"], {"state": "تمت"})`,
              },
            },
            {
              id: "builtin",
              title: "The business's data",
              body:
                "Lists take limit (up to 200) and offset and return {items, total}.\n• GET /customers?q= (customers:read) and POST /customers {name, phone, address} (customers:write)\n• GET /suppliers (suppliers:read)\n• GET /products?q= (products:read): by name, code or barcode\n• GET /stock?product_id= (stock:read)\n• GET /sales?since=<ISO time> (sales:read): confirmed sales, newest first, with their lines\n• GET /employees (employees:read)\n• GET /branches (branches:read)\n\nAmounts are decimal strings (\"150.50\"); times are ISO 8601.",
            },
          ],
        },
      },
      {
        slug: "webhooks",
        title: "Webhooks",
        titleEn: "Webhooks",
        description: "Signed events to your server, retried, with a log the business owner can see.",
        category: "Your server",
        lastUpdated: UPDATED,
        content: {
          overview:
            "Set your server's address and the events in manifest.json (webhooks.url and webhooks.events). Every event is recorded together with the change itself, so none is lost, and sent at once; if that fails it is retried after 1, 5 and 30 minutes, then 2, 6 and 12 hours, then given up. The business owner sees the log under “الإشعارات” (notifications).",
          sections: [
            {
              id: "request",
              title: "The request",
              body:
                "A POST with a JSON body to a public HTTPS address (no local or private addresses), with the headers Mizan-Event, Mizan-Delivery, Mizan-Timestamp and Mizan-Signature. Answer with any 2xx within 5 seconds.",
              codeBlock: { language: "json", code: PAYLOAD },
            },
            {
              id: "verify",
              title: "Verifying the signature",
              body:
                "Mizan-Signature is sha256=<HMAC-SHA256 of \"<timestamp>.<raw body>\" with the webhook secret>. The secret is shown with the connection token. Reject anything older than five minutes, and use Mizan-Delivery to ignore repeats.",
              codeBlock: {
                language: "python",
                code: `from mizan_sdk import WebhookError, verify_webhook\n\ndef handle(request):\n    try:\n        event = verify_webhook(SECRET, request.body,\n                               request.headers["Mizan-Timestamp"], request.headers["Mizan-Signature"])\n    except WebhookError:\n        return 400\n    ...`,
              },
              callout: { type: "warning", text: "Always verify the signature on the raw body, before re-encoding it; any change to it breaks the signature." },
            },
            {
              id: "events",
              title: "Events and their data",
              body:
                "• sale.confirmed: the sale and its lines (as in the example).\n• sale.returned: the original sale with return {total} (plus the return's id and number for a partial return).\n• customer.created: {id, name, phone}\n• product.updated: {id, code, name, retail_price, is_active}\n• record.created / record.updated: {entity, id, data} for your module's records.",
            },
          ],
        },
      },
    ],
  },
  {
    id: "ship",
    title: "Signing and shipping",
    titleEn: "Signing and shipping",
    items: [
      {
        slug: "signing",
        title: "Signing keys and certificates",
        titleEn: "Signing keys",
        description: "Why packages are signed, how Mizan certifies your key, and revoking a key.",
        category: "Signing and shipping",
        lastUpdated: UPDATED,
        content: {
          overview:
            "Every package is signed with a private Ed25519 key that stays on your machine. You register its public half for your team in the portal, and Mizan issues a certificate for it (starting with MZD1). When installing, Mizan checks, even on on-site servers without internet, that the certificate is Mizan's, that the signature is from the certified key, that no file changed, and that the module id starts with the team's handle.",
          sections: [
            {
              id: "keys",
              title: "Keys",
              body:
                "mizan keys new --team <handle> creates the key in ~/.mizan, registers it and saves its certificate. Or copy the public key it prints into “Keys” on the team's page and save the certificate as ~/.mizan/default.cert. A team has up to 10 active keys; any member can register one, and only owners revoke them.",
              callout: { type: "warning", text: "The private key signs in your team's name: don't share it or commit it to a repository. If it leaks, revoke it in the portal and create another." },
            },
            {
              id: "revoke",
              title: "Revoking",
              body:
                "Once a key is revoked, Mizan's cloud refuses to install any package signed with it (modules already installed stay). Sign a new version with another key.",
            },
          ],
        },
      },
      {
        slug: "installing",
        title: "Installing, updating and removing",
        titleEn: "Installing",
        description: "What the business owner sees, and what happens to the records.",
        category: "Signing and shipping",
        lastUpdated: UPDATED,
        content: {
          overview:
            "Modules are installed by someone holding the “install and remove developer modules” permission (the workspace's admin), from the module centre → وحدات المطورين → تثبيت من ملف. They see its name, its developer, what it adds, its scopes and where it sends webhooks, and the install button stays disabled until they agree.",
          sections: [
            {
              id: "update",
              title: "Updating",
              body: "Upload a newer version with the same id: the definitions are replaced and the records stay. New scopes are marked “new” for the owner to approve.",
            },
            {
              id: "remove",
              title: "Removing",
              body:
                "The owner chooses: remove and keep the records (they come back if the module is installed again), or remove and delete the records for good. Either way the connection token stops at once.",
            },
          ],
        },
      },
      {
        slug: "publishing",
        title: "Publishing to the marketplace",
        titleEn: "Publishing",
        description: "Sending a module or theme for review, what the review checks, and updates.",
        category: "Signing and shipping",
        lastUpdated: UPDATED,
        content: {
          overview:
            "Published modules and themes appear in the store inside every workspace's module centre (المتجر). Send a signed package with mizan publish, or with “Send a package” on your team's page in the portal. The Mizan team reviews it; once approved, Mizan countersigns that exact package and lists it. Activities are published the same way; workspaces don't install them from the store but change to them (see Business activities). Listings are free for now; paid listings come later.",
          sections: [
            {
              id: "send",
              title: "Sending",
              body: "mizan publish packages the folder and sends it to the team named by the id's prefix (acme.visits → acme). It can also send a .mzm you built before. Your team's page lists every version you sent with its status: in review, approved, rejected (with the reviewer's note) or withdrawn. You can withdraw a version while it's in review.",
              codeBlock: { language: "bash", code: "mizan publish acme.visits          # package, then send\nmizan publish acme.visits-1.2.0.mzm" },
            },
            {
              id: "review",
              title: "What the review checks",
              body: "The same checks as an install from file run first: the signature, Mizan's certificate for your key, the key not revoked, the id in your team's namespace and the manifest rules. Then a person looks at what it adds, the scopes it asks for (new scopes in an update are marked), where it sends webhooks, and its files. Ask only for the scopes you use and describe the module plainly in Arabic.",
            },
            {
              id: "updates",
              title: "Updates",
              body: "Raise the version (1.0.0 → 1.1.0) and publish again; a version can be sent only once, and it must be newer than the listed one. The listed version stays in the store until the new one is approved. Workspaces that installed the module see “update available” and approve any new scopes.",
            },
            {
              id: "delist",
              title: "Removal from the store",
              body: "The Mizan team can delist a module or theme (for example after a security report) with a reason you see on your team's page. It can no longer be installed; workspaces that have it keep it. Revoking your signing key also stops new installs of everything it signed.",
            },
          ],
        },
      },
      {
        slug: "cli",
        title: "The mizan CLI",
        titleEn: "The CLI",
        description: "Every command.",
        category: "Signing and shipping",
        lastUpdated: UPDATED,
        content: {
          overview: `Install it with pip install ${SDK_URL}. Its files live in ~/.mizan (or MIZAN_HOME).`,
          sections: [
            {
              id: "commands",
              title: "Commands",
              body: "",
              codeBlock: {
                language: "bash",
                code: `mizan login [--token mzd_...]     # a token from the portal (or MIZAN_TOKEN)
mizan whoami                      # your account and teams
mizan logout
mizan module new acme.visits      # a module from the template
mizan theme new acme.sunrise      # a theme pack from Mizan's own
mizan activity new acme.laundry   # a whole business activity
mizan check [folder]              # the platform's own checks
mizan keys new [--team acme] [--name laptop]
mizan package [folder] [--key ...] [--certificate ...] [--out ...]
mizan publish [folder|file.mzm] [--team acme]   # send it to the marketplace for review`,
              },
            },
          ],
        },
      },
    ],
  },
];
