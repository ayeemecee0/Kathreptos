// Public browser-safe configuration. Do not add secret or service-role keys.
window.KATOPTRON_CONFIG = Object.freeze({
  supabaseUrl: 'https://bpvkapswslmgfazbzpsv.supabase.co',
  supabasePublishableKey: 'sb_publishable_JdCkRi7LLLnzBVeEY3WVPQ_3zou_rrW',
  // These PUBLIC, no-secret endpoints may be replaced with compatible,
  // managed Photon and OSRM services. Never embed provider API secrets here.
  geocodingServiceBase: 'https://photon.komoot.io',
  routingServiceBase: 'https://router.project-osrm.org',
  // Geoapify BROWSER-PUBLIC key: no secret is intended here.
  // Its origin/referrer restrictions are NOT independently confirmed. Verify
  // account-side key restrictions and quotas before any production launch.
  // Never add a secret or unrestricted private server key to this file.
  locationProvider: 'geoapify',
  geoapifyPublicKey: '8c54de2386764931baa0f9aef9033ef3'
});
