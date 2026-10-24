# Katoptron: zero-dollar routing and geocoding plan
**Planning checkpoint: October 23, 2026. No paid infrastructure authorized.**

## Choice

Keep existing OSRM and Photon *low-volume, best-effort public demos* during development. Prepare **Geoapify's $0 free account** as the first optional upgrade, not paid Render infrastructure. The adapter is committed but **disabled by default**. No key or paid instance was provisioned.

As checked on October 23, 2026, Geoapify's official pricing includes:
- **Free: 3,000 API credits per day**, up to five requests/second and no credit card required.
- Commercial production use on the free plan is explicitly permitted within quota/feature restrictions **with attribution**.
- Each typical text geocoding query costs ~1 credit; a simple two-point driving route costs ~1 credit for distances under 500 km. Routes over 500 km use additional credits; route details, toll avoidance, etc., can increase costs.
- The optional client requests two genuine driving strategies (**balanced** and **shortest**) for route comparisons, normally requiring **two** routing requests per itinerary, plus up to two separate geocoding lookups. A simple short journey therefore uses approximately 4 credits; the theoretical 750 journeys/day is **not a service guarantee** and ignores map tiles, extra lookups, long trips, and retries.
- A public/browser API key is inherently visible. Create a **separate, limited-scope, origin-restricted** key for `https://ayeemecee0.github.io` and check the provider's current allowed-origin and CORS policy. Never place a secret key or unrestricted account credential in `config.js`. Inspect vendor terms and privacy policy for transmission of route points and addresses.

Official pages: https://www.geoapify.com/pricing/ and https://apidocs.geoapify.com/docs/routing/ .

## Activating after free-account setup

1. Sign up at https://myprojects.geoapify.com/ under the free plan; **do not enter payment details or enable automatic paid upgrades**.
2. Create a separate web API key restricted to the Katoptron GitHub Pages origin and read-only Routing/Geocoding API where provider controls permit.
3. Test the restricted key and review Geoapify's privacy/retention disclosures for addresses and routes.
4. Change only the public browser-safe fields of `config.js`:
```js
locationProvider: 'geoapify',
geoapifyPublicKey: 'PUBLIC_ORIGIN_RESTRICTED_GEOAPIFY_KEY'
```
5. Verify required attribution is visible. CI contains `scripts/test_geoapify_adapter.js` and an end-to-end Chromium smoke test with a **fake key and mocked Geoapify responses**, so it generates no billable calls. Run real end-to-end trials with an authorized provider key before announcing availability.
6. Monitor account credits and rate limits; if the free quota is reached, show provider unavailable instead of silently falling back to another host or requiring a paid subscription.

## Alternatives / costs

- **Mapbox** currently lists **100,000 free monthly Directions requests and 100,000 free monthly temporary geocoding requests**. Mapbox supports route alternatives and can serve public websites, but its URL-restricted tokens require a compatible Referer policy. Katoptron currently uses `no-referrer` for route privacy, so adopting Mapbox requires a reviewed integration rather than a same-endpoint swap.
- **OpenRouteService** offers free API access and alternative routing; its public API imposes a **100 km maximum for routes requesting alternatives**, making it a poor full-U.S. alternative comparison default.
- **Self-hosted OSRM plus Photon** uses free/open software, **not free national compute and storage**. Leave the Render paid-gateway blueprint unactivated until required for traffic, contracts, or funded infrastructure.
- **Existing demos:** No account expense, but no guaranteed availability and use must stay reasonable; outages are part of the beta UX.

## Milestone sequencing

Engineering effort can proceed with $0 hosted new spend: finish adapter acceptance tests, then move the primary focus to **Milestone 5: evidence-backed community submissions** while preserving the current evidence verification and privacy protections. Do not delay all features pending a paid routing provider. Dedicated routing service contracts and throughput load tests are a later funded release gate.

**Important:** The new optional free provider is NOT ACTIVE until an authorized public API key is set. A $0 plan does not itself prove an SLA, perfect route coverage, or complete Flock camera data.
