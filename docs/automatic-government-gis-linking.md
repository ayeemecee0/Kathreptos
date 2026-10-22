# Automatic official-government GIS source linking

## What this milestone delivers

The new provenance stage separates **government-authority verification** from
**camera-coordinate verification**:

1. The independently examined El Paso County government GIS host and an exact
   Sheriff's Department ArcGIS layer path are pinned in
   \`gis_government_host_authorities\` (migration 023).
2. \`scripts/auto_link_gov_gis.py\` independently checks the current county GIS
   disclosure page, the exact Sheriff service metadata, the
   \`Flock_Cameras\` point layer name and schema, and its bounded live
   coordinate inventory.
3. Only after those checks, the limited service role may call the narrow
   \`promote_owner_bound_gis_source\` database function. The function rejects
   every non-owner-pinned hostname, government proof mismatch, source status
   mismatch, or changed jurisdiction/bounds. Unreviewed ArcGIS candidates can
   NEVER promote themselves. The original hashes are retained in
   \`official_gis_authority_receipts\`.
4. The independent \`auto_verify_camera_gis.py\` worker re-checks the Flock
   metadata before each import, requires named bounded point features, and
   publishes exact coordinates only to the separately verified camera table.
5. Source revocation withdraws the published camera records automatically
   through the earlier migration 021 authority chain.

## Evidence provenance

- County GIS server: https://gisservices.elpasoco.com/arcgis2/rest/services/Sheriff/NeighborhoodWatchGroups_FlockCCTVCameras_GISMap3_WFL1/MapServer
- Exact camera layer: https://gisservices.elpasoco.com/arcgis2/rest/services/Sheriff/NeighborhoodWatchGroups_FlockCCTVCameras_GISMap3_WFL1/MapServer/1
- County GIS program evidence: https://admin.elpasoco.com/digital-strategy-and-technology/licensed-gis-data/

A public original government point layer is evidence of **documented camera
location**, not proof that the camera is operational, connected to a Flock
network, currently reading license plates or tracking any person.

The layer contains **16 explicitly named Flock-camera points** in the first
successful live run. Previously published **18 Monroe WA** records remain
separate, making 34 verified public GIS camera point records in two regions.

## Threat model and limits

This is owner-anchored auto-verification, **not generic unsupervised
trust-building across every city**. Anyone can publish a layer called
"Flock Cameras" on shared ArcGIS hosting; those layers remain in the private
candidate queue until a corresponding government-controlled URL can be
authenticated to its actual municipality. Passing a procurement-only
government record does not authenticate a hosted camera-location dataset.

A compromised workflow service-role credential is still a critical threat:
it can access the private candidate database and try to post evidence; the
RLS and guarded RPC greatly narrow approval scope but are not cryptographic
remote attestation. Future scaling should isolate the verifier credential
and add automatic discovery of cross-linked GIS services from independently
approved local government disclosure directories.

CI tests prevent synthetic cameras or uncertain third-party map contents
from entering the official GIS source registry.
