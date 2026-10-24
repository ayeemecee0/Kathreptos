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

## Hosting options and deployable artifacts (October 23, 2026)

**Railway signup is currently unavailable to the user.** Do not depend on Railway provisioning. A provider-neutral gateway is now tracked at `infra/routing-gateway/`; an optional Render-specific Blueprint is at `render.yaml`, and a service-independent bounded load gate is at `scripts/load_test_route_providers.py`.

- **Render:** Can host the gateway image using its Docker runtime. The Blueprint is **manual opt-in** (`autoDeploy: false`) and requires separately configured `ROUTING_UPSTREAM` and `GEOCODING_UPSTREAM` values. It uses a paid plan when activated, subject to host pricing and explicit account/payment authorization. Render is **not** itself an OSRM road graph or Photon geocoder; production-scale map indexes must live on separately provisioned and reviewed infrastructure.
- **Any compatible VPS or managed provider:** Can host the same containerized gateway with `infra/routing-gateway/docker-compose.yml` and approved private upstreams. Terminate HTTPS through a configured ingress. Keep access logs off for route and location query paths.
- **Photon national indexing capacity:** Official Photon documentation estimates about 95 GB storage and recommends at least 64 GB RAM for its *planet-wide* dataset as of 2026. A smaller U.S.-specific extract may use less but requires benchmarking, not an invented cloud instance size. Do not try to deploy a full index on a small free web instance.
- **Operational safety:** `/healthz` currently proves only that the gateway process is alive. A passing check is **not** proof that both dedicated upstream APIs work; run `scripts/monitor_route_providers.py` against configured URLs and an opt-in short fixture load test instead.

Provider acceptance command after approved private routing and geocoding endpoints exist:

```bash
python scripts/load_test_route_providers.py --routing-base https://routing.approved.example --geocoding-base https://geocoding.approved.example --rounds 2 --workers 2
```

This gate issues at most 64 requests at concurrency ≤4, using fixed sample points; it **refuses** shared Photon/OSRM demos. It measures request success and sample latency, not contracted uptime. Configure and verify a hosted provider **before** changing the public site `config.js`.

## Remaining external dependency

A dedicated nationwide managed routing/geocoding provider **or** securely operated nationwide OSRM + Photon infrastructure has **not** been purchased/provisioned in the existing connected environments. This requires hosting capacity or provider account/terms. A Supabase Edge Function by itself cannot host the full continental U.S. road graph and nationwide geocoder dataset. Do not promise a production SLA until this dependency is resolved.

## Operating checkpoints

- Automated smoke and code validation: `.github/workflows/browser_smoke.yml`, `.github/workflows/validate.yml`
- Fixed-sample provider checks: `.github/workflows/monitor_route_providers.yml`
- Technical milestone overview: `docs/milestone-4-next-effort.md`
- Existing `README` and public `methodology.html` continue to label simulations as hypothetical and public camera coverage as incomplete.

**Source:** [Photon project demo policy](https://github.com/komoot/photon); [OSRM routing API](https://project-osrm.org/docs/v26.6.1/http).
