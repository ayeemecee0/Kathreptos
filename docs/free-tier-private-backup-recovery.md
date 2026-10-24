# Katoptron — Free-plan private-data backup and recovery

Last reviewed 2026-10-24. **The owner created and content-checked three private local application export files on an encrypted Windows drive. A complete Auth/Storage backup and an actual restore test of those files remain unfinished.**

## What the existing automated snapshots cover

GitHub's `snapshot_public_evidence.yml` copies **anonymous-public** government evidence only. It does **not** preserve private submissions, private Storage photos, reviewer notes, user accounts or full Supabase policies. It must never be repurposed to ship private account data into GitHub Actions artifacts.

Supabase recommends that Free-plan projects perform regular offline database exports using `supabase db dump`; managed downloadable daily backups are not included on Free. Database dumps do **not** include file contents from Supabase Storage.

Sources: [Supabase Database Backups](https://supabase.com/docs/guides/platform/backups); [Supabase CLI database dump](https://supabase.com/docs/reference/cli/supabase-db-dump); [Supabase Production Checklist](https://supabase.com/docs/guides/deployment/going-into-prod).

## Privacy-first, $0 ongoing-cost process

1. On your own trusted computer, enable full-disk encryption (Windows BitLocker or equivalent) and prepare an encrypted external drive or a separate encrypted vault. **Never store unencrypted database dumps, Storage evidence, connection strings or private reviewer files in the Katoptron GitHub repository or its Actions artifacts.**
2. Install the current Supabase CLI and Docker and check the supported flags with `supabase db dump --help`. Review official CLI documentation before executing commands.
3. In your project dashboard, use **Connect** to obtain the database connection information directly. Keep the database password on your machine; do **not** paste connection strings or passwords into this chat, GitHub Issues, CI logs or the frontend.
4. Make three independent logical exports on the trusted machine: roles, schema, and data. Reference commands below use PowerShell's already-defined local environment variable `KATOPTRON_DB_URL` and a private output directory. Database URL passwords may be visible to local operating-system process inspection; perform the export only on your own trusted computer. Keep the output location on an encrypted volume and do not display the URL in logs.
5. Move the three files into an independently encrypted archive, backed up offline. Restore-test the archive in a **local disposable** database before relying on it for production recovery. Ensure any test database cannot deliver outbound mail or publish cameras.
6. Back up **actual private Storage object content separately**, through authorized Supabase Storage API access into the same encrypted private archive. Storage SQL metadata alone cannot restore photo bytes, and direct SQL deletion of Storage objects is prohibited. Do not copy user photographs into the source repository.
7. Retain only as long as your privacy policy and recovery requirements justify, rotate encrypted archives, and restrict access to authorized operators. Test both DB restore and Storage file recovery after schema changes.

### Example local commands (PowerShell)

Run in a trusted local PowerShell terminal with a secure local `KATOPTRON_DB_URL` already set and an existing `D:\\PrivateEncryptedBackups\\Katoptron` folder on an encrypted drive. Do not include literal passwords in these commands.

```powershell
supabase db dump --help
supabase db dump --db-url "$env:KATOPTRON_DB_URL" -f "D:\PrivateEncryptedBackups\Katoptron\roles.sql" --role-only
supabase db dump --db-url "$env:KATOPTRON_DB_URL" -f "D:\PrivateEncryptedBackups\Katoptron\schema.sql"
supabase db dump --db-url "$env:KATOPTRON_DB_URL" -f "D:\PrivateEncryptedBackups\Katoptron\data.sql" --use-copy --data-only
```

The example assumes Docker/CLI support, working database access and adequate protected local storage. These commands are **not yet executed or certified**. The schema/data/roles trio follows Supabase's [restore-from-platform guidance](https://supabase.com/docs/guides/self-hosting/restore-from-platform).

## Restore acceptance checklist

- A disposable local PostgreSQL/Supabase-compatible environment accepts role, schema and data restores in the required order and preserves source-review permissions, triggers and RLS.
- An unauthenticated session cannot read private community submissions, review history, screening or private photo metadata.
- An ordinary authenticated user can access only their own reports and is denied reviewer capabilities. The reviewer's allowlist remains restricted.
- Community withdrawals still revoke linked tiered evidence; public camera verification counts reconcile with original government sources.
- One sample private Storage object can be restored into a private local bucket, opened only by its authorized owner or reviewer, and deleted by the permitted Storage API path.
- Encryption recovery keys/passphrases are independently stored; losing a backup key must not require public disclosure of private data.
- Document test date, observed pass/fail checks and a realistic recovery point objective; do **not** mark restore verified on the basis of a file existing.

## Owners and status

Current state: owner generated non-empty roles, schema and data SQL files locally and verified basic content checks; no encrypted off-device archive, complete Auth/Storage backup or restore drill of those files. [CI application restore rehearsal #454](https://github.com/ayeemecee0/Katoptron/actions/runs/40112397254) passed against a disposable synthetic database, not the owner files. These operations require the project owner to handle credentials, access-controlled Storage evidence, encrypted retention and local capacity. Do not create a paid Supabase branch to run restore tests merely for convenience.
