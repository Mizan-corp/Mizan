# Mizan — Full Motion & Animation Engineering Prompt
Source: ChatGPT Main chat, messages [35] + [53], Nov 2026 (gpt-6 / gpt-6-mini)
Target quality: $9,000–$15,000 custom SaaS website motion engineering.

---

## Role
Act as a world-class motion designer, creative developer, interaction designer, and senior frontend engineer specializing in award-winning digital experiences.

Transform the existing Mizan website into an exceptionally polished, motion-rich, premium SaaS experience.

**IMPORTANT:** Do not redesign or destroy the existing Mizan brand identity. Enhance it through motion.

---

## Motion Art Direction

Follow the Warm Editorial Luxury identity. Motion should feel:
- Cinematic but restrained
- Editorial and sophisticated
- Fluid and natural
- Tactile and responsive
- Precise and intentional
- Premium without becoming theatrical

Think: carefully choreographed editorial websites, high-end architecture portfolios, sophisticated SaaS product experiences.

**AVOID:** Generic animation presets and repetitive fade-up effects. Every major section must have its own motion treatment while maintaining one coherent visual language.

---

## Technology Stack

Inspect the existing project first. Identify framework, routing, existing animation libraries, component hierarchy, page layouts, styling conventions, interactive elements, performance bottlenecks.

For React/Next.js:
- **Motion for React** — component animation, layout transitions, gestures, shared layout animations
- **GSAP + ScrollTrigger** — sophisticated scroll choreography and complex timelines
- **CSS transitions** — lightweight interactions
- **SVG animations** — diagrams and graphical details
- **Lottie/Rive** — only when a custom animation genuinely benefits
- **Three.js/WebGL** — ONLY when a genuinely valuable visual concept exists (not decorative)

Do NOT install every animation library. Select smallest appropriate technology per interaction.

Create reusable animation utilities and centralized motion configuration. Avoid duplicating animation logic.

---

## Motion System (Centralized)

### Timing tokens
| Name | Duration |
|---|---|
| Micro | 120–200ms |
| Fast | 180–280ms |
| Normal | 300–450ms |
| Expressive | 500–800ms |
| Cinematic | 800–1,400ms |

Do NOT make all animations use the same duration.

### Easing
Use carefully tuned cubic-bezier curves and natural spring configurations. Prefer smooth, natural deceleration over linear movement.

### Performance rules
- GPU-friendly transforms and opacity
- Efficient IntersectionObserver usage
- Lazy-load below-the-fold visuals
- Cleanup animation timelines properly
- No excessive simultaneous animations
- No layout thrashing

---

## Signature Hero Experience

The first viewport must immediately communicate quality.

### Initial page entrance (choreograph in sequence)
1. Background composition appears
2. Navigation enters smoothly
3. Small eyebrow label reveals
4. Main headline reveals with sophisticated text choreography (clip-path or mask)
5. Supporting paragraph enters
6. CTA buttons appear with staggered timing
7. Main product visual reveals with layered depth
8. Supporting decorative elements settle

Use clip-path reveals, masked text transitions, opacity, and carefully controlled transforms.

Do NOT make users wait before they can interact.

### Hero product visualization
The ERP dashboard mockup should feel like a real object:
- Subtle perspective and depth
- Layered interface panels entering from different directions
- Animated chart drawing (lines animate to their values)
- Small notification entrances
- Refined shadow transitions
- Scroll-linked perspective changes
- Gentle floating on selected elements

**One memorable signature visual interaction that makes Mizan distinctive.**

Do NOT use: random floating cards, excessive parallax, exaggerated bouncing.

---

## Scroll Storytelling

Transform the entire landing page into a connected visual narrative. Use DIFFERENT techniques per section.

### Techniques by section type
| Content type | Animation approach |
|---|---|
| Section headings | Fade-up reveals, word-by-word or line-by-line clips |
| Feature items | Staggered entrances |
| Image + text | Complementary motion, clip-path reveals, masked reveals |
| Product mockups | Subtle scale/move as they enter |
| Architecture diagrams | Animated SVG paths, module connections |
| Major transitions | Full-width image reveals, background color transitions |

### GSAP ScrollTrigger (selective use only)
- Pinned product presentations
- Sequential product storytelling
- Animated architectural diagrams
- Layered visual compositions
- Controlled horizontal storytelling sections
- Scroll-linked image transformations

> Pinned sections must NEVER interfere with normal navigation or create frustrating scrolling behavior.

### Editorial typography animations
- Word-by-word headline reveals
- Line-by-line clipping reveals
- Staggered paragraph entrances
- Subtle text emphasis transitions
- Animated underlines

> Do NOT animate every paragraph or every individual letter. Use only for high-impact moments.

---

## Page-by-Page Motion Specification

### HOME — /
Strongest motion on the website.
- Signature hero choreography
- Animated dashboard mockup
- Editorial headline reveals
- Scroll-based storytelling
- Interactive module previews
- Animated architecture diagrams
- Staggered feature sections
- Product showcase transitions
- Animated statistics
- Refined pricing interactions
- Cinematic final CTA reveal

Must feel like one continuous experience, not disconnected sections.

### PRODUCT — /product
Interactive explanation of the Mizan ecosystem.
- Animated modular architecture diagram
- Connected module diagrams with animated connection paths
- Interactive module selection — when clicked, transition visual AND content together
- Layered dashboard presentations
- Progressive visual storytelling

### FEATURES — /features
Interactive feature discovery.
- Animated feature grids
- Hover-driven visual previews
- Staggered content entrances
- Feature illustrations with subtle movement
- Interactive comparisons
- Smooth category navigation

### INDUSTRIES — /industries
More visual and editorial.
- Large image reveals
- Subtle image parallax
- Industry-specific visual transitions
- Interactive industry selection
- Animated workflow diagrams
- Each industry has own visual personality within Mizan's system

### PRICING — /pricing
Clear and conversion-focused.
- Smooth monthly/annual pricing transitions
- Animated price changes
- Elegant plan-selection states
- Subtle feature comparison reveals
- Hover interactions on plan options
- Refined CTA feedback

> Do NOT use aggressive movement around pricing or hide important information behind animations.

### ABOUT — /about
Strong editorial storytelling.
- Large typographic statements
- Image reveal choreography
- Timeline animations (if real timeline exists)
- Layered visual compositions
- Subtle parallax

### CONTACT — /contact
Functional and reassuring.
- Animated form focus states
- Smooth validation feedback
- Clear loading and success states
- Subtle button interactions
- Refined form entrance

### BLOG — /blog
- Staggered article entrances
- Refined image reveals
- Hover-driven article previews
- Smooth category filtering
- Search-result transitions

### BLOG ARTICLE — /blog/[slug]
Prioritize reading comfort.
- Editorial title entrance
- Author/metadata reveal
- Featured image reveal
- Reading progress indicator
- Subtle TOC active-state transitions
- Related article transitions

### LOGIN / SIGNUP
Do NOT animate in ways that delay user input.
- Smooth page entrance
- Form focus transitions
- Password visibility transitions
- Validation feedback
- Loading indicators
- Clear success and error states

### DOCUMENTATION — /docs
Documentation must remain practical and fast.
- Animated sidebar expansion
- Smooth active navigation transitions
- Search interface transitions
- Result highlighting
- Accordion animations
- Code-copy feedback
- TOC active-state changes
- Subtle content entrances
- Previous/next navigation transitions
- Reading progress indicator

> Do NOT animate every paragraph during reading. Documentation must prioritize accessibility and performance over visual spectacle.

---

## Premium Micro-Interactions

### Navigation
- Elegant dropdown entrances
- Smooth active indicators
- Subtle underline animations
- Refined mobile menu transitions
- Navigation background transitions on scroll

### Buttons
- Smooth background transitions
- Directional arrow movement (subtle)
- Subtle elevation on hover
- Pressed states
- Magnetic movement only where appropriate
- Avoid excessive cursor-following effects

### Cards
- Subtle image scaling
- Border transitions
- Soft shadow changes
- Controlled hover elevation
- Small directional movements
- Interactive visual previews

### Images
- Clip-path reveals
- Masked image transitions
- Subtle zoom
- Layered image movement
- Scroll-linked transformations

### Forms
- Animated focus borders
- Label transitions
- Validation feedback
- Loading states
- Success transitions

---

## Cursor and Pointer Experience (desktop only)

Optional premium pointer:
- Subtle custom cursor on selected interactive areas
- Contextual pointer states
- Gentle magnetic CTA interactions
- Hover-driven visual previews

Rules:
- Do NOT replace native cursor globally
- Never compromise accessibility, text selection, or normal pointer behavior
- Disable on touch devices and when reduced motion is enabled

---

## Page Transitions and Routing

- Smooth route transitions with coordinated outgoing/incoming content
- Subtle opacity and transform choreography
- Consistent navigation continuity
- Correct scroll restoration
- Correct browser back/forward behavior
- Use shared layout transitions for elements appearing across routes

> Never use full-screen transition effects that delay navigation.
> Every page must be directly accessible through its URL.
> Do NOT break SEO, routing, browser history, or deep links.

---

## Interactive Product Showcases (critical for Mizan)

The product must NOT look like a collection of static screenshots.

### Dashboard showcase
- Animated charts
- Changing dashboard views
- Interactive navigation
- Smooth panel transitions
- Contextual notifications
- Animated metric changes

### Module showcase
When users select Accounting / Inventory / Sales / CRM / HR / Projects:
- Transition the product mockup to the corresponding interface
- Animate the transition between modules

### Architecture showcase
Interactive diagram of the modular ERP ecosystem:
- Module connections with animated paths
- Data-flow paths
- Selected module states
- Relationship highlighting
- Layered architecture components

> All mockup data must be clearly understood as demonstration content.

---

## Advanced Visual Techniques (selective)

- SVG path drawing
- Animated gradients
- Clip-path reveals
- Text masking
- Image masking
- Subtle noise overlays
- Perspective transforms
- Layered parallax
- Animated borders
- Scroll-linked transforms
- Morphing graphical elements
- Animated data visualizations
- Shared layout transitions

Use WebGL/Three.js ONLY for a genuinely valuable visual concept. Do NOT add heavy 3D to look expensive.

---

## Arabic and RTL Motion Support

All animations must work correctly in BOTH LTR and RTL layouts:
- Respect text direction
- Reverse directional movements where appropriate
- Mirror directional navigation animations
- Preserve Arabic text shaping
- Avoid per-letter animation that breaks Arabic ligatures
- Use word-level or line-level Arabic text animation
- Keep Arabic typography readable during transitions
- Ensure menus, sidebars, and diagrams behave correctly in RTL
- Use actual HTML text with established Arabic fonts
- Never use generated images containing Arabic text as replacement content

---

## Responsive Motion System

### Desktop
Rich choreography, interactive hover effects, carefully controlled parallax

### Tablet
Reduce layered movement, simplify complex interactions

### Mobile
- Fast transitions
- Simple reveals
- Touch-friendly interactions
- Lightweight animations
- NO custom cursor
- NO unnecessary pinned sections
- NO heavy parallax

> Do NOT simply scale desktop animations down. Create device-appropriate motion behavior.

---

## Accessibility — Reduced Motion

When `prefers-reduced-motion` is enabled:
- Remove parallax
- Disable unnecessary auto-playing movement
- Replace complex transitions with simple state changes
- Preserve all content and interactions
- Never sacrifice usability for visual effects

---

## Final Quality Checklist (every page)

Before completing, inspect every page:
- [ ] Page has a deliberate entrance experience
- [ ] Important content has purposeful motion
- [ ] Interactive elements provide feedback
- [ ] Navigation works correctly
- [ ] Route transitions work
- [ ] Scroll behavior remains natural
- [ ] Arabic and RTL animations work
- [ ] Mobile behavior is appropriate
- [ ] Reduced-motion mode works
- [ ] No animation-related console errors
- [ ] No broken interactions
- [ ] Performance remains acceptable
- [ ] Tested at desktop + tablet + mobile
- [ ] Checked in both Arabic and English
- [ ] Removed generic, repetitive, distracting, or unnecessary animations

---

## Three Strongest Recommendations

1. **Signature hero** — the Mizan dashboard should reveal itself in layers, with animated charts, depth, and carefully choreographed typography.

2. **Scroll storytelling** — use a few memorable pinned product demonstrations and architectural diagrams instead of dozens of identical fade-up animations.

3. **Shared page transitions** — make navigation between Home, Product, Features, Pricing, and About feel like moving through one connected experience.

> "Don't let your coding agent interpret 'premium motion' as 'animate absolutely everything.' Restraint and timing are what make expensive-looking motion work."
