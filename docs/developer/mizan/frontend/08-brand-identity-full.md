# Mizan — Full Brand Identity & Design System
Source: ChatGPT Main chat, messages [37–49], Nov 2026 (gpt-6 / gpt-6-mini)
This is the complete, final brand identity specification.

---

## Brand Positioning

**ميزان (Mizan)** = balance, structure, precision, control.

Mizan helps businesses bring financial, administrative, and operational activities into one integrated ecosystem.

### Brand must communicate
- Business clarity and operational control
- Sophisticated technology
- Reliability and precision
- Flexibility and modularity
- Professionalism and long-term growth

### Brand personality
- Sophisticated, not extravagant
- Modern, not futuristic for appearance's sake
- Confident, not aggressive
- Intelligent, not complicated
- Premium, but approachable
- Distinctive, without sacrificing usability

### What Mizan is NOT
- A generic ERP template
- A cryptocurrency platform
- A banking application
- A luxury fashion store

---

## Art Direction: Warm Editorial Luxury

Visual language inspired by:
- Contemporary editorial design
- Premium architectural publications
- Sophisticated financial and business journals
- Modern enterprise software
- Minimalist Swiss-inspired layouts
- High-end digital product experiences

Use: asymmetrical compositions, intentional whitespace, strong typography, precise grids, architectural imagery, subtle textures, restrained visual effects.

---

## Official Color Palette

### Primary brand colors
| Color name | Hex | Purpose |
|---|---|---|
| Oxblood Burgundy | `#651E2C` | Signature brand color |
| Deep Merlot | `#35151D` | Dark hero sections and footer |
| Muted Rose | `#B86B76` | Secondary accents and highlights |
| Warm Ivory | `#F5EBDD` | Main light background |
| Soft Sand | `#E7D6C1` | Secondary surfaces and borders |
| Charcoal | `#262321` | Primary text and interface elements |

### Supporting colors
| Purpose | Hex |
|---|---|
| Pure White | `#FFFFFF` |
| Muted Text | `#77716E` |
| Light Border | `#E6DCD2` |
| Success | `#27835C` |
| Warning | `#C58A35` |
| Error | `#C14E50` |
| Information | `#557DA1` |

### Application rules
- Warm Ivory = dominant marketing website background
- Deep Merlot = primary hero and selected dark sections
- Oxblood Burgundy = primary CTAs, selected states, signature highlights
- Charcoal = readable text
- Soft Sand = subtle separation and visual structure
- Muted Rose = sparingly
- Do NOT use burgundy for every button, icon, chart, or decorative element
- Avoid excessive gradients — where used: subtle, atmospheric, sophisticated

---

## Typography System

### English fonts
| Font | Use |
|---|---|
| **Cormorant Garamond** | Display headlines — large marketing headlines, editorial section titles, brand storytelling |
| **Manrope** | Body and interface — navigation, buttons, body text, product interface, documentation |

### Arabic fonts
| Font | Use |
|---|---|
| **Noto Naskh Arabic** | Arabic display headlines — large marketing headlines, editorial section headings, brand statements |
| **IBM Plex Sans Arabic** | Arabic interface and body — navigation, buttons, body paragraphs, dashboard, tables, forms, documentation |

### Typography scale
| Element | Desktop size |
|---|---|
| Main hero headline | 64–76px |
| Major section heading | 44–56px |
| Page title | 40–48px |
| Feature heading | 24–30px |
| Card heading | 19–23px |
| Body text | 16–18px |
| UI labels | 13–14px |

### Arabic typography rules (CRITICAL)
- Never use decorative Arabic fonts for interface content
- Never artificially stretch Arabic letters
- Preserve proper Arabic letter connections and shaping
- Use correct Arabic punctuation and text direction
- Numerals and currency remain consistent and readable
- Avoid excessive boldness in Arabic headlines
- Use appropriate line heights for Arabic
- Do NOT mix too many typefaces

### CRITICAL Arabic rendering rule
> **NEVER use AI-generated images containing Arabic text as actual website content.**
> All Arabic text must be rendered through real HTML text elements using the specified fonts.
> AI images = for visual concepts, architectural backgrounds, decorative elements, composition references ONLY.
> All visible text must be editable, searchable, selectable, accessible, and correctly shaped by the browser.

### Suggested Arabic hero copy
- أدر أعمالك بتوازن.
- نظام واحد. رؤية أوضح. نمو أكثر ذكاءً.
- منصة ميزان لإدارة أعمالك، تجمع العمليات المالية والإدارية والتشغيلية في منظومة واحدة متكاملة.
- Primary CTA: اكتشف ميزان
- Secondary CTA: استكشف المنصة

---

## Bilingual / RTL Experience

### Languages
Arabic (primary) + English

### Arabic requirements
- Full RTL layout
- Correct navigation alignment
- Properly mirrored directional icons
- Correct breadcrumb direction
- Correct sidebar positioning
- Appropriate form alignment
- Correct table direction
- Correct handling of mixed Arabic + English text
- Appropriate currency and number formatting
- Consistent language switching

---

## Logo and Brand Mark

### Concept
Abstract geometric design exploring balance. Potential directions:
- Symmetrical geometric symbol
- Abstract letter M
- Balanced architectural forms
- Negative-space geometry
- Minimal symbol inspired by equilibrium

### Avoid
- Generic accounting icons
- Literal weighing scales
- Complicated illustrations
- Excessive ornamental Arabic calligraphy

### Must work in
- English wordmark: Mizan
- Arabic wordmark: ميزان
- Standalone icon
- Browser favicon
- Mobile app icon
- Dark and light backgrounds
- Small ERP sidebar placements

> Must be a proper vector asset, NOT a text-based approximation.

---

## Marketing Website Visual Language

### Hero section
- Deep Merlot or Oxblood Burgundy hero with Warm Ivory typography
- Premium navigation
- Clear product positioning
- Strong editorial headline + concise supporting copy
- Primary and secondary CTAs
- Large realistic ERP dashboard mockup
- Carefully layered background elements
- Subtle architectural references

### Dashboard mockup requirements
- A CONVINCING representation of actual ERP software
- NOT a random collection of charts
- Shows: business overview, financial analytics, inventory, sales, purchasing, HR, reporting, modular architecture
- Realistic UI layouts, believable sample values, consistent spacing, coherent component design
- Clearly understood as demonstration content

### Section composition variety
- Full-width editorial sections
- Split image-and-text layouts
- Asymmetrical feature presentations
- Product-interface showcases
- Architecture diagrams
- Refined pricing sections
- Spacious content sections

**AVOID:** Repeating identical card grids throughout the website.

---

## ERP Product Interface (separate from marketing)

The marketing website and ERP must share brand identity WITHOUT sharing visual density.

### ERP visual principles
- Clear information hierarchy
- Readable tables
- Efficient forms
- Consistent navigation
- Compact but comfortable spacing
- Accessible contrast
- Predictable interaction patterns
- Clear status indicators

### ERP colors
Charcoal, Warm Ivory, White, and Burgundy as primary interface colors

### ERP typography
- IBM Plex Sans Arabic for Arabic UI
- Manrope for English UI
- Do NOT apply decorative editorial typography to tables, forms, financial figures, or operational interface components

### Themes
Support both light and dark themes.

---

## Documentation Portal

Same brand identity, prioritize readability:
- Warm Ivory or White backgrounds
- Charcoal text
- Burgundy active navigation states
- Manrope for English documentation
- IBM Plex Sans Arabic for Arabic documentation
- Restrained and professional — NOT expressive editorial

---

## Premium Motion Design

(See also: `09-motion-engineering-prompt.md` for full motion spec)

### Motion timing system
| Interaction | Duration |
|---|---|
| Micro-interactions | 150–250ms |
| Hover transitions | 180–300ms |
| Navigation transitions | 250–450ms |
| Scroll reveals | 400–700ms |
| Hero choreography | 700–1,200ms |

### Motion technology
- **Motion for React** — component-level animations, layout transitions, gestures
- **GSAP + ScrollTrigger** — selected advanced scroll sequences, complex timelines
- **CSS transitions** — simple hover/focus effects
- **SVG animations** — diagrams and graphical details
- **Lottie/Rive** — only when genuine custom animation is needed
- **Three.js/WebGL** — only for justified flagship visual, NOT decorative default

### Performance and accessibility
- Respect `prefers-reduced-motion`
- Avoid scroll-jacking
- Avoid unnecessary infinite animations
- Keep animations smooth on mid-range mobile
- Prioritize `transform` and `opacity` animations (GPU-friendly)

---

## Quality Standards

### Brand quality check
- Does Mizan have a recognizable identity?
- Does the brand feel premium and distinctive?
- Is the color palette consistent?
- Is typography carefully composed?

### Arabic quality check
- Is Arabic shaping correct?
- Are Arabic fonts rendered properly?
- Is RTL behavior correct throughout?
- Is Arabic copy natural and professionally written?
- Are mixed-language elements handled correctly?

### Motion quality check
- Are transitions coordinated?
- Does the hero feel distinctive?
- Is motion restrained and purposeful?
- Is the experience smooth on mobile?

### Product quality check
- Does the dashboard look believable?
- Is the interface practical?
- Is the documentation readable?
- Are all visible interactions functional?

---

## Final Design Principle

> Mizan should look like a serious, premium, internationally competitive SaaS company with its own recognizable identity.
>
> The marketing website should be expressive and memorable.
> The ERP should be efficient, precise, and comfortable for everyday business operations.
> The documentation should be clear, accessible, and technically credible.
>
> **The defining characteristic of Mizan should be the balance between exceptional design and practical business software.**
