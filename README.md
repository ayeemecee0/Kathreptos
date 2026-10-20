# Katoptron (Κάτοπτρον)

A nationwide public-records accountability project focused exclusively on Flock Safety and automated license plate recognition (ALPR).

## What works now
- [Standalone browser simulator](./index.html) with synthetic vehicles and camera observations.
- [Supabase database migration](./supabase/migrations/001_init.sql) for agencies, officials, contracts, actions, deployments, sources and an unpublished discovery queue.
- [Public-news lead discovery](./scripts/discover.py). Leads are **unverified** until reviewed against primary sources.

## Preview the simulator
Open `index.html` in a browser, or deploy this static file through GitHub Pages. External map and routing services require an internet connection. No Supabase project is required for the simulator.

## Configure the database
1. Create a separate Supabase project for Katoptron.
2. In Supabase SQL Editor, run `supabase/migrations/001_init.sql`.
3. Keep the project URL and service-role key in server-side secrets only. **Never commit the service-role key or put it in the HTML file.**
4. Locally, install dependencies: `python -m pip install -r requirements.txt`.
5. Run `python scripts/discover.py --output candidates.json` to save unverified public news leads.
6. To send leads to the private review queue, set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` on a trusted server and run the script again.

## Verification policy
Record exact dated decisions and link to original sources. A news mention does not prove an official's support. Do not publish private plate numbers, personal movement histories, private addresses, or targeted tracking. The simulator and real public records must remain separate.

## Not yet deployed
The Supabase project has not been created, the SQL has not been executed, the discovery script has not been run, and the simulator is not connected to Supabase. GitHub Pages is not yet enabled.
