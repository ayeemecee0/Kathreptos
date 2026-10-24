// Public browser-safe configuration. Do not add secret or service-role keys.
window.KATOPTRON_CONFIG = Object.freeze({
  supabaseUrl: 'https://bpvkapswslmgfazbzpsv.supabase.co',
  supabasePublishableKey: 'sb_publishable_JdCkRi7LLLnzBVeEY3WVPQ_3zou_rrW',
  // These PUBLIC, no-secret endpoints may be replaced with compatible,
  // managed Photon and OSRM services. Never embed provider API secrets here.
  geocodingServiceBase: 'https://photon.komoot.io',
  routingServiceBase: 'https://router.project-osrm.org',
  // Optional Geoapify free plan; keep disabled until a free account is created,
  // provider privacy/attribution terms are reviewed and the key is strictly
  // origin-restricted. A browser-visible key is NOT a secret credential.
  locationProvider: 'demo',
  geoapifyPublicKey: ''
});
