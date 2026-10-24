# Katoptron — Milestone 4 routing / geocoding production-readiness gate

## Current mode: PUBLIC BETA (not a production routing provider)

The site uses directly configured `https://router.project-osrm.org` and `https://photon.komoot.io`. Photon explicitly disclaims any uptime guarantee, may throttle high-volume traffic and reserves the right to change the demo; the community OSRM router likewise has no contracted uptime for Katoptron. Neither is under a Katoptron production service contract.

**Do not claim Milestone 4 provider infrastructure is production-ready merely because a health check passes.** Nationwide camera evidence is independently incomplete, regardless of provider availability.

## Completed in this development increment

- `routing-provider.js`: public HTTPS endpoint validation, no URL credentials, browser no-referrer policy, no cookies, disabled redirect forwarding, no-cache responses, 6 MB response cap, deadline-based cancellation, one bounded retry for transient 5xx/network failures, 429 cooldown, and per-provider in-memory circuit breaker. No telemetry of origin/destination and no persisted route history.
- `map.js` cancels a previous geocode/route lookup when a newer trip is requested or reset. It exposes provider degradation and never fabricates straight-line road alternatives when the provider fails.
- Daily `monitor_route_providers.yml` uses *fixed non-user sample locations* to verify Photon-compatible US geocoding and OSRM-compatible route geometry. CI failure can signal service outage, but **passing is not an SLA guarantee**.
- Regresions validate no referrer/cookie forwarding, cancellation, throttling, JSON response bounds, retry behavior and provider output contracts.

## Acceptance requirements before moving to production endpoints

1. **U.S. coverage:** Full continental U.S. routing and geocoding coverage; verify non-contiguous U.S. states separately if the product claims their coverage.
2. **API compatibility:** The routing endpoint must expose OSRM-compatible `GET /route/v1/driving/{lon,lat;lon,lat}?overview=full&geometries=geojson&steps=false&alternatives=true`. The geocoder must expose Photon-compatible `GET /api/?limit=5&lang=en&q={urlencoded-query}`, with a valid `features[].geometry.coordinates` and `features[].properties.countrycode` field. Different providers require **explicit server-side adapters and tests** before adoption; do not assume all products are wire-compatible.
3. **No browser secrets:** If upstream needs a bearer token, put it behind an approved privacy-reviewed gateway with enforced authentication, rate limiting and secure secrets. Never add credentials to `config.js`, HTML, query strings or JS bundles.
4. **Privacy:** A written retention/deletion policy for geocoder searches and route coordinates; disable raw route logs where possible and ensure data-subprocessor terms permit the intended public service. HTTPS + no-referrer is necessary but not a substitute for a vendor privacy agreement.
5. **Operational reliability:** Contracted uptime/support terms, transparent published limits, documented paid costs, monitoring and actionable incident alerts. Run repeatable end-to-end tests during deploys and under representative request volume. Publish an explicit "Routing unavailable" state on outage, not guessed routes or surveillance-free claims.
6. **Rollout:** Provision compatible endpoint domains; run `python scripts/monitor_route_providers.py` and browser smoke on staging; check routes in multiple cities/states; set `routingServiceBase` and `geocodingServiceBase` in public `config.js`; deploy GitHub Pages; verify health monitors and browser tests after the switch.
7. **No silent fallback to another demo:** An undocumented fallback changes the recipient of an address or route and can violate users' privacy expectations. Require explicit provider approval for each origin.

## Remaining external dependency

A dedicated nationwide managed routing/geocoding provider **or** securely operated nationwide OSRM + Photon infrastructure has **not** been purchased/provisioned in the existing connected environments. This requires hosting capacity or provider account/terms. A Supabase Edge Function by itself cannot host the full continental U.S. road graph and nationwide geocoder dataset. Do not promise a production SLA until this dependency is resolved.

## Operating checkpoints

- Automated smoke and code validation: `.github/workflows/browser_smoke.yml`, `.github/workflows/validate.yml`
- Fixed-sample provider checks: `.github/workflows/monitor_route_providers.yml`
- Technical milestone overview: `docs/milestone-4-next-effort.md`
- Existing `README` and public `methodology.html` continue to label simulations as hypothetical and public camera coverage as incomplete.

**Source:** [Photon project demo policy](https://github.com/komoot/photon); [OSRM routing API](https://project-osrm.org/docs/v26.6.1/http).
