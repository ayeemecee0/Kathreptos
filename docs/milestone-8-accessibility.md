# Milestone 8 — Public experience and accessibility improvements
Implemented engineering work October 23, 2026.

## Scope delivered
- `a11y.css` supplies visible keyboard focus cues, offscreen-until-focused skip-navigation links, motion reduction and narrow-screen touch targets.
- Eight core pages now have one explicit `main#main-content` landmark, an operable skip link, English page language, shared keyboard style and unique element IDs.
- The government accountability tab interface supports Arrow Left/Right plus Home/End; the selected tab controls keyboard focus and accessible selection state.
- The evidence analytics page provides labeled headings, a real table with numeric cells rather than color-only bars, text equivalents for each timeline bar, screen-reader status announcements, small-screen layouts and clear data-coverage uncertainty.
- `scripts/test_public_accessibility.py` performs no-dependency markup and uncertainty-label regressions.
- `scripts/smoke_accessibility.cjs` adds Chromium keyboard and viewport tests to the existing release workflow.

## Verification performed
Static repository checks confirm all eight relevant pages have matching skip links, correct main landmarks, linked accessible stylesheets, English language and no duplicate IDs. The keyboard/mobile browser regression completed successfully in [Browser release smoke #91](https://github.com/ayeemecee0/Katoptron/actions/runs/40063928164), following the documented desktop navigation overflow repair. [Validation #407](https://github.com/ayeemecee0/Katoptron/actions/runs/40063928191) also passed. These automated checks do not substitute for real assistive-technology tests.

## Independent acceptance gates
Static checks and browser smoke tests cannot establish full WCAG 2.2 AA conformance. Before calling the complete public experience accessible: conduct voice navigation and screen-reader reviews (NVDA/JAWS/VoiceOver), 200% zoom, touch interaction, color contrast checks, external Leaflet/map keyboard use, form error flows and actual mobile-browser observations. Fix any confirmed defects. Do not claim these tests passed without observation.

## October 23 release extension

- `scripts/smoke_zoom_accessibility.cjs` checks keyboard bypass, labeled community forms, and zoom-equivalent reflow at a 640 CSS-pixel viewport. The failed initial attempt used a CSS zoom property that does **not** reproduce a real browser zoom's responsive breakpoints; the corrected test passed in [Browser smoke #106](https://github.com/ayeemecee0/Katoptron/actions/runs/40066397323).
- Exact-version browser Supabase SDK pinning and public-asset credential checks run in [Validation #436](https://github.com/ayeemecee0/Katoptron/actions/runs/40066347410).
- Manual NVDA/VoiceOver, 200% browser zoom using a real browser, high-contrast modes and touch devices remain independent signoff requirements.
