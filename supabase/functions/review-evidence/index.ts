// Reviewer-only Legistar evidence reader.
// Source: only a registered, private review row may determine tenant and ID.
// Never proxies arbitrary user-provided URLs. No service-role key is sent to a client.
const origin = "https://ayeemecee0.github.io";
const cors = {
  "Access-Control-Allow-Origin": origin,
  "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Content-Type": "application/json; charset=utf-8",
  "Cache-Control": "no-store",
  "Vary": "Origin",
};
function reply(status: number, data: unknown) {
  return new Response(JSON.stringify(data), { status, headers: cors });
}
const uuidRe = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const safeUrl = (raw: unknown): string | null => {
  if (typeof raw !== "string" || raw.length > 1600) return null;
  try {
    const u = new URL(raw);
    return u.protocol === "https:" && !u.username && !u.password &&
      !u.port ? u.href : null;
  } catch { return null; }
};
const short = (value: unknown, max = 1500) =>
  typeof value === "string" ? value.slice(0, max) : value == null ? "" : String(value).slice(0, max);
async function readBoundedJson(url: string, maxBytes: number) {
  const response = await fetch(url, {
    redirect: "error", signal: AbortSignal.timeout(12000),
    headers: { "Accept": "application/json", "User-Agent": "Katoptron-evidence-review/1.0" },
  });
  if (!response.ok) throw Error("Official API HTTP " + response.status);
  const ctype = response.headers.get("content-type") || "";
  if (!ctype.includes("json")) throw Error("Official API returned a non-JSON response");
  const reader = response.body?.getReader();
  if (!reader) throw Error("Official API returned an empty body");
  const pieces: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      total += value.length;
      if (total > maxBytes) throw Error("Official API response too large");
      pieces.push(value);
    }
  } finally {
    await reader.cancel().catch(() => {});
  }
  const merged = new Uint8Array(total);
  let offset = 0;
  for (const part of pieces) { merged.set(part, offset); offset += part.length; }
  return JSON.parse(new TextDecoder().decode(merged));
}
Deno.serve(async (request: Request) => {
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
  if (request.method !== "POST") return reply(405, { error: "POST required" });
  const bearer = request.headers.get("authorization") || "";
  if (!/^Bearer [A-Za-z0-9._~-]+$/i.test(bearer)) return reply(401, { error: "Sign in required" });
  const base = Deno.env.get("SUPABASE_URL");
  const anon = Deno.env.get("SUPABASE_ANON_KEY");
  if (!base || !anon) return reply(503, { error: "Evidence service not configured" });
  try {
    const input = await request.json();
    const id = input?.review_id;
    if (typeof id !== "string" || !uuidRe.test(id)) {
      return reply(400, { error: "Invalid review identifier" });
    }
    // Supabase verifies the user's JWT on this authenticated RPC.
    // Membership is checked within editorial_evidence_ref(), NOT trusted from
    // request metadata or an email address supplied by the browser.
    const rpc = await fetch(base + "/rest/v1/rpc/editorial_evidence_ref", {
      method: "POST", redirect: "error", signal: AbortSignal.timeout(10000),
      headers: {
        "apikey": anon,
        "Authorization": bearer,
        "Content-Type": "application/json",
        "Accept": "application/json",
      },
      body: JSON.stringify({ p_review_id: id }),
    });
    if (!rpc.ok) return reply(rpc.status === 401 ? 401 : 403, {
      error: "Your account is not authorized to inspect this evidence",
    });
    const ref = await rpc.json();
    const tenant = ref?.tenant;
    const matterId = ref?.matter_id;
    if (typeof tenant !== "string" || !/^[a-z0-9-]{3,40}$/.test(tenant) ||
        !Number.isSafeInteger(Number(matterId)) || Number(matterId) <= 0) {
      throw Error("Invalid government matter reference");
    }
    const root = "https://webapi.legistar.com/v1/" + tenant + "/matters/" + matterId;
    if (root !== ref.official_api_url) throw Error("Government matter identity mismatch");
    const matter = await readBoundedJson(root, 700_000);
    if (!matter || Array.isArray(matter) || Number(matter.MatterId) !== Number(matterId)) {
      throw Error("Government API matter mismatch");
    }
    const metadata = {
      matterId: Number(matterId),
      guid: short(matter.MatterGUID, 80),
      file: short(matter.MatterFile, 100),
      title: short(matter.MatterTitle || matter.MatterName, 1600),
      type: short(matter.MatterTypeName, 120),
      status: short(matter.MatterStatusName, 120),
      introDate: short(matter.MatterIntroDate, 100),
      passedDate: short(matter.MatterPassedDate, 100),
      finalActionDate: short(matter.MatterFinalActionDate, 100),
      notes: short(matter.MatterNotes, 9000),
      text: [matter.MatterText1, matter.MatterText2, matter.MatterText3]
        .map(value => short(value, 9000)).filter(Boolean).join("\n"),
      restricted: matter.MatterRestrictViewViaWeb === true,
    };
    if (metadata.restricted) return reply(403, { error: "This matter is restricted from public viewing" });
    const [attResult, historyResult] = await Promise.allSettled([
      readBoundedJson(root + "/attachments", 450_000),
      readBoundedJson(root + "/histories", 450_000),
    ]);
    const attachments = attResult.status === "fulfilled" && Array.isArray(attResult.value) ?
      attResult.value.slice(0, 75).map((a: Record<string, unknown>) => ({
        name: short(a.MatterAttachmentName || a.MatterAttachmentFileName || a.MatterAttachmentTypeName || "Government attachment", 230),
        url: safeUrl(a.MatterAttachmentHyperlink || a.MatterAttachmentUrl || a.MatterAttachmentFileName),
      })).filter(a => a.url) : [];
    const histories = historyResult.status === "fulfilled" && Array.isArray(historyResult.value) ?
      historyResult.value.slice(0, 80).map((h: Record<string, unknown>) => ({
        date: short(h.MatterHistoryActionDate, 100),
        action: short(h.MatterHistoryActionName || h.MatterHistoryActionText, 300),
        body: short(h.MatterHistoryBodyName, 200),
        result: short(h.MatterHistoryResult, 130),
      })) : [];
    return reply(200, {
      matter: metadata,
      attachments,
      histories,
      warnings: [
        ...(attResult.status === "rejected" ? ["Attachments were unavailable; open the official Legistar page."] : []),
        ...(historyResult.status === "rejected" ? ["Action history was unavailable; open the official Legistar page."] : []),
      ],
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Official evidence unavailable";
    return reply(502, { error: short(msg, 240) });
  }
});
