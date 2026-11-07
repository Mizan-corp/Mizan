# Mizan — Marketing Website & Documentation Portal Master Prompt
Source: ChatGPT Main chat, messages [33] + [35], Nov 2026 (gpt-6)
Full master prompt for building the complete SaaS marketing website + docs portal.

---

## Role
Act as a senior product designer, SaaS branding specialist, UX architect, and full-stack frontend engineer.

Build a complete, production-quality official website for Mizan — a modular, multi-tenant ERP SaaS platform.

---

## Website Scope

Must include:
1. High-converting marketing landing page
2. Complete official marketing website
3. Product, feature, and industry pages
4. Pricing and plan comparison
5. Developer and user documentation portal
6. Consistent visual identity and reusable component system

---

## Design Inspiration

Reference: [Landingfolio SaaS gallery](https://www.landingfolio.com/inspiration/landing-page/saas)

Study: clear hero sections, strong typography, product screenshots/mockups, modern SaaS navigation, feature grids, product storytelling, pricing presentation, social proof, thoughtful spacing, conversion-focused CTAs.

Do NOT copy any specific website. Create a distinct visual identity for Mizan.

**The result should feel like a mature, premium software company — not a generic template, basic admin dashboard, or AI-generated collection of repetitive cards.**

---

## Design Characteristics

**Use:**
- Strong typography with a clear type scale
- Spacious layouts with intentional whitespace
- Carefully balanced content density
- Subtle borders, shadows, gradients
- Refined hover and focus states
- Elegant transitions and micro-interactions
- Consistent spacing system
- Responsive layouts for desktop, tablet, mobile
- Authentic product-interface mockups and diagrams

**Avoid:**
- Excessive gradients
- Random decorative elements
- Too many rounded cards
- Generic stock photography
- Repetitive feature-card layouts
- Fake testimonials and fabricated customer logos
- Unsupported claims ("fastest ERP", "trusted by thousands")
- Unnecessary animations that reduce usability

---

## Information Architecture

### Main marketing website

**Home — /**
- Announcement bar (if appropriate)
- Responsive navigation
- Hero: value proposition + primary CTA ("Get Started") + secondary CTA ("Explore Platform") + product visual
- Business problem and solution section
- Platform overview
- Modular architecture presentation
- Key feature sections
- Industry and business-type coverage
- Integration and extensibility section
- Deployment and security overview
- Product screenshots or interactive mockups
- Pricing preview
- FAQ section
- Final conversion section
- Comprehensive footer

Hero must immediately answer:
1. What is the product?
2. Who is it for?
3. What business problem does it solve?
4. Why should a business explore it?

> AVOID: vague messaging like "Transform your business with innovation."

**Product — /product**
- Platform as a unified business management system
- How modules work together
- How businesses activate modules
- Visual architecture / product ecosystem diagram

**Features — /features**
- Feature overview with navigation to individual pages
- Each feature page: introduction, business problem, how it works, key capabilities, workflow, product visual, related modules, CTA

**Industries — /industries**
- Industry overview + individual industry pages
- Potential industries: Retail, Wholesale/Distribution, Manufacturing, Professional Services, Construction, Healthcare Administration, E-commerce, Logistics
- Describe how platform supports each industry
- Avoid regulatory/compliance claims without evidence

**Pricing — /pricing**
- Monthly and annual billing toggle
- Clearly defined plan tiers with feature comparison
- Included modules / usage limits
- CTA per plan
- FAQ
- Enterprise/contact-sales option
- Clearly marked placeholder pricing if actual prices not provided
- Do NOT invent live subscription system unless implemented

**About — /about**
- Product vision, company mission, product principles
- Team section with placeholders
- CTA
- Do NOT invent founder bios, company history, or achievements

**Contact — /contact**
- Contact form (sales inquiry + support inquiry)
- Clear contact details (placeholders OK)
- Validation + success/error states
- Do NOT create fake email addresses or pretend the form sends

**Blog — /blog**
- Blog index: featured article, category filters, search, article cards
- Individual article template + related articles
- Clearly identified sample content

**Auth entry points: /login, /signup**
- Clean, consistent pages or placeholders
- If not connected to backend, make this explicit

---

## Documentation Portal — /docs

Must feel like a professional software documentation product, not a marketing page.

### Desktop layout
- Left sidebar with expandable navigation
- Main documentation content
- Optional right-side table of contents
- Search interface
- Breadcrumbs
- Previous/next page navigation

### Mobile layout
- Collapsible documentation navigation
- Comfortable reading width
- Accessible search
- No horizontal overflow

### Documentation homepage
- Welcome message
- Documentation search
- Getting-started cards
- Popular pages
- Module documentation
- API documentation entry point
- Deployment guides

### Documentation structure
**Getting Started:** Introduction, Platform Overview, Create Account, Create Company, Workspace Setup, First Steps

**User Guide:** Dashboard, Navigation, Users/Roles, Company Settings, Notifications, Search/Filters

**Modules:** Accounting, Sales, CRM, Inventory, Purchasing, HR, Projects, Reporting

**Administration:** Company Management, User Management, Roles/Permissions, Module Configuration, Tenant Settings, Data Import/Export

**Developer Documentation:** Architecture Overview, API Introduction, Authentication, API Requests/Responses, Error Handling, Webhooks, Pagination, Rate Limits, SDKs

**Deployment:** SaaS Deployment, Self-Hosted, Environment Config, Database Config, Backup/Restore, Monitoring, Troubleshooting

**Support:** FAQ, Common Issues, Contact Support, Release Notes

> Only write definitive instructions for features that actually exist. Use clearly marked placeholders for unknown details.

### Documentation UX
- Search with useful results
- Sidebar active-state highlighting
- Expandable sections
- TOC from headings
- Copy buttons for code snippets
- Syntax-highlighted code blocks
- Callout styles (notes, warnings, tips)
- Breadcrumb navigation
- Previous and next links
- Responsive reading layout

---

## Content and Copywriting

Voice: clear, confident, helpful, business-oriented, technically credible, free from exaggerated marketing.

Focus on business outcomes:
- Reduce disconnected workflows
- Improve visibility across operations
- Centralize business data
- Support consistent processes
- Make it easier to manage growing operations

Do NOT fill with lorem ipsum. Write realistic content based on known product context, clearly marking unconfirmed features.

---

## Technical Implementation

Before writing any code:
1. Inspect the existing project
2. Identify: framework, routing, existing components, styling, build tooling, current assets, existing functionality
3. Preserve the current stack unless there is a clear technical reason to change

### Requirements
- Reusable components
- Consistent design tokens
- Clean component hierarchy
- Maintainable route structure
- Responsive layouts
- Accessible semantic HTML
- Keyboard navigation
- Appropriate ARIA attributes
- SEO metadata
- Open Graph metadata
- Optimized images and assets
- Proper loading/empty/success/error states
- No unnecessary dependencies
- No duplicated page implementations

### Shared components to create
`Header, Footer, Navigation, MobileNavigation, Button, FeatureSection, FeatureCard, PricingCard, FAQAccordion, TestimonialComponent, DocumentationSidebar, DocumentationSearch, TableOfContents, CodeBlock, Breadcrumbs, Callout, ArticleLayout`

Design tokens: colors, typography, spacing, borders, radii, shadows

---

## Interaction Requirements

All visible interactive elements must work:
- Responsive navigation + mobile menu
- Dropdown menus
- FAQ accordion
- Pricing billing toggle
- Search interface
- Documentation navigation
- Form validation
- Copy-to-clipboard controls
- Functional internal links
- Clear hover/focus/active/disabled states

**Do NOT use `href="#"` for unfinished links.**

If a backend-dependent feature is unavailable: use a clear placeholder or disabled state, NOT a simulated success.

---

## Design Quality Review

After implementation, check:
- Does the hero communicate the product clearly?
- Is the visual hierarchy strong?
- Are pages visually consistent?
- Does the design feel premium and original?
- Are there enough meaningful product visuals?
- Does the documentation feel like a real developer portal?
- Are all routes connected?
- Do all visible interactions work?
- Does the layout work on mobile?
- Are there console errors?
- Are there broken links?
- Is the content accessible and readable?
- Are there unsupported claims?

**Do NOT stop after creating the homepage. Implement the complete website and documentation structure.**

---

## Deliverables

- Complete website implementation
- Landing page and all requested marketing pages
- Documentation portal and navigation structure
- Reusable components and design tokens
- Responsive behavior
- Functional frontend interactions
- Clear placeholders for missing business/product information
- Summary of files and routes created
- Any remaining backend integrations or implementation limitations

---

## Premium Motion Design Section (from message [35])

Add to your implementation brief:

### Motion architecture
- Motion for React + CSS transitions for most of the website
- GSAP only for signature hero and complex scroll sequences
- Do NOT install five animation libraries that compete

### Hero choreography
- Carefully choreographed page-load entrance
- Headline text revealing in staggered sequence
- Supporting text fading in after headline
- CTA buttons entering with subtle movement
- Large ERP mockup appearing with depth and perspective
- Layered floating interface elements
- Subtle ambient background motion
- Gentle scroll-linked transition to next section

### Scroll experience
- Scroll-triggered reveals for section headings
- Staggered entrances for feature items
- Image and text sections with complementary motion
- Product mockups that subtly move/scale as they enter
- Animated diagrams explaining modular ERP architecture

### Interactive product showcase
- Dashboard mockup with animated charts
- Interactive module navigation
- Smooth transitions between product views
- Animated data visualizations
- Hover states on interface elements
- Contextual tooltips
- When clicking "Inventory" → transitions to inventory interface; "Accounting" → accounting interface

### Motion timing system
| Interaction | Duration |
|---|---|
| Micro-interactions | 150–250ms |
| Button/hover transitions | 180–300ms |
| Navigation/modal transitions | 250–450ms |
| Scroll-triggered reveals | 400–700ms |
| Hero choreography | ~700–1,200ms |

### Accessibility
- Respect `prefers-reduced-motion`
- Provide reduced-motion alternatives
- Do not make essential information dependent on animation
- Avoid flashing effects, forced scrolling
- Ensure all interactions work with keyboard
- Keep animations smooth on mid-range mobile
- Keep website usable when JS is unavailable

---

## Before Using This Prompt

Replace:
- Product name with Mizan / ميزان
- Add real logo and brand colors (from `08-brand-identity-full.md`)
- Specify your framework (React + Vite)
- Confirm which modules are actually implemented
- Specify actual pricing if available
