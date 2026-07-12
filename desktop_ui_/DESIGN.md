---
name: SentiNews AI
colors:
  surface: '#11131a'
  surface-dim: '#11131a'
  surface-bright: '#363940'
  surface-container-lowest: '#0b0e15'
  surface-container-low: '#191b22'
  surface-container: '#1d2026'
  surface-container-high: '#272a31'
  surface-container-highest: '#32353c'
  on-surface: '#e1e2eb'
  on-surface-variant: '#c2c6d5'
  inverse-surface: '#e1e2eb'
  inverse-on-surface: '#2e3038'
  outline: '#8c909f'
  outline-variant: '#424753'
  surface-tint: '#adc6ff'
  primary: '#adc6ff'
  on-primary: '#002e69'
  primary-container: '#4d8efe'
  on-primary-container: '#00285c'
  inverse-primary: '#005ac1'
  secondary: '#6ddd81'
  on-secondary: '#003914'
  secondary-container: '#30a550'
  on-secondary-container: '#003210'
  tertiary: '#fbbc06'
  on-tertiary: '#402d00'
  tertiary-container: '#b88900'
  on-tertiary-container: '#372700'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#d8e2ff'
  primary-fixed-dim: '#adc6ff'
  on-primary-fixed: '#001a41'
  on-primary-fixed-variant: '#004494'
  secondary-fixed: '#89fa9b'
  secondary-fixed-dim: '#6ddd81'
  on-secondary-fixed: '#002108'
  on-secondary-fixed-variant: '#005320'
  tertiary-fixed: '#ffdea0'
  tertiary-fixed-dim: '#fbbc06'
  on-tertiary-fixed: '#261a00'
  on-tertiary-fixed-variant: '#5c4300'
  background: '#11131a'
  on-background: '#e1e2eb'
  surface-variant: '#32353c'
typography:
  headline-lg:
    fontFamily: Hanken Grotesk
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Hanken Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-md:
    fontFamily: Hanken Grotesk
    fontSize: 24px
    fontWeight: '500'
    lineHeight: 32px
  title-lg:
    fontFamily: Hanken Grotesk
    fontSize: 20px
    fontWeight: '500'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-lg:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.1px
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.5px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 8px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 64px
  max-width: 1280px
---

## Brand & Style
The design system moves away from cinematic high-fidelity visuals toward a **Corporate Modern** aesthetic deeply rooted in Material Design 3 principles. The goal is to establish an institutional-grade AI platform that feels dependable, intelligent, and authoritative.

The brand personality is **Professional, Analytical, and Approachable**. By leveraging large amounts of whitespace, geometric precision, and a restrained color palette, the UI transitions from an entertainment-focused news app to a high-end enterprise sentiment analysis tool. The emotional response should be one of "systematic clarity"—users should feel that the AI's complexity is contained within a safe, organized, and familiar environment.

## Colors
The color strategy employs a **Refined Dark Mode** foundation. Instead of pure black, the system uses deep charcoals and muted navies to reduce eye strain and provide better depth for layering.

- **Primary (Google Blue):** Used for primary actions, active states, and brand-critical touchpoints.
- **Surface Palette:** Employs Material 3 dark surface tones (#1F1F1F) to distinguish between the background and interactive containers.
- **Semantic Accents:** Red, yellow, and green are strictly reserved for data visualization—specifically sentiment indicators (Negative, Neutral, Positive) and trend volatility. They should never be used for purely decorative purposes.

## Typography
The system utilizes a dual-font approach to balance character with utility. **Hanken Grotesk** provides a modern, geometric feel for headlines that mirrors the "Google Sans" spirit, while **Inter** is used for all body and functional text to ensure maximum legibility and a technical, systematic feel.

Hierarchy is maintained through deliberate weight shifts rather than dramatic size changes. Titles and headlines should use a tighter letter-spacing to appear more cohesive, while labels use slightly expanded tracking to ensure readability at small sizes.

## Layout & Spacing
This design system follows a **Fixed-Fluid Hybrid** grid model. On desktop, the content is centered within a 1280px container to maintain readability for data-heavy dashboards.

- **Grid:** A 12-column system is used for desktop, 8-column for tablet, and 4-column for mobile.
- **Rhythm:** All spacing is based on an 8px base unit. 
- **Margins:** Generous margins are used to evoke an "Enterprise" feel—avoiding the cluttered look of consumer news apps. Use 24px gutters consistently to allow the UI to "breathe."

## Elevation & Depth
Depth is expressed through **Tonal Layering** rather than traditional drop shadows. In this dark mode environment, higher elevation levels are represented by lighter surface container colors.

- **Level 0 (Background):** #121212 - The base canvas.
- **Level 1 (Cards/Sidebar):** #1F1F1F - Standard elevation for grouped content.
- **Level 2 (Modals/Popovers):** #2C2C2C - Uses a subtle 1px border (#3C3C3C) to define edges against lower layers.
- **Overlays:** Use a 60% opacity black scrim for backdrop blurs behind modals to maintain focus without losing context.

## Shapes
Following Material 3 standards, the design system utilizes a **Large Radius** philosophy. 

- **Standard Elements:** Buttons, input fields, and chips use a 0.5rem (8px) radius.
- **Containers:** Large cards and surface areas use 1.5rem (24px) for a soft, approachable container feel.
- **Selection:** Active states in navigation or toggle buttons should use fully rounded (pill-shaped) indicators to clearly denote "Selected" versus "Unselected."

## Components

- **Buttons:** Use "Filled" for primary actions (#4285F4) and "Outlined" for secondary actions. Use a consistent 12px horizontal padding and 8px vertical padding for standard sizes.
- **Sentiment Chips:** Small, low-contrast pills. For example, a "Positive" chip uses a #34A853 background at 15% opacity with solid #34A853 text.
- **Cards:** No shadows. Use Tonal Surface #1F1F1F. Content within cards should follow the 8px grid (16px or 24px internal padding).
- **Inputs:** Transition from cinematic glows to the "M3 Filled Input" style—darker background than the surface, with a high-contrast bottom stroke and clear #4285F4 focus ring.
- **Data Indicators:** Use Material Symbols (Rounded) for iconography. Keep icons at a standard 20px or 24px size with a "Regular" weight.
- **Navigation:** Use a vertical rail for desktop and a bottom navigation bar for mobile, following the M3 spec for active state indicators (pill-shaped highlight).