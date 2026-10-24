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
Static repository checks confirm all eight relevant pages have matching skip links, correct main landmarks, linked accessible stylesheets, English language and no duplicate IDs. The new browser tests are committed but their actual GitHub Actions conclusions remain unverified.

## Independent acceptance gates
Static checks and browser smoke tests cannot establish full WCAG 2.2 AA conformance. Before calling the complete public experience accessible: conduct voice navigation and screen-reader reviews (NVDA/JAWS/VoiceOver), 200% zoom, touch interaction, color contrast checks, external Leaflet/map keyboard use, form error flows and actual mobile-browser observations. Fix any confirmed defects. Do not claim these tests passed without observation.
