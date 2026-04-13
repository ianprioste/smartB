/**
 * Cloudflare Worker — Bling Token Proxy
 *
 * Forwards POST requests to Bling's OAuth token endpoint transparently.
 * Deployed on Cloudflare's edge network so the IP is never a blocked datacenter range.
 *
 * Deploy steps:
 *   1. Go to https://dash.cloudflare.com/ → Workers & Pages → Create Worker
 *   2. Paste this script and deploy (free plan is enough: 100k req/day)
 *   3. Copy the worker URL (e.g. https://bling-token-proxy.YOUR-SUBDOMAIN.workers.dev)
 *   4. Add GitHub secret: BLING_TOKEN_PROXY_URL = <worker URL>
 *   5. Trigger a redeploy so the VPS picks up the new env var
 */

const BLING_TOKEN_URL = "https://www.bling.com.br/Api/v3/oauth/token";

export default {
  async fetch(request) {
    // Only allow POST
    if (request.method !== "POST") {
      return new Response("Method Not Allowed", { status: 405 });
    }

    // Forward all headers and body to Bling
    const body = await request.text();

    const headers = new Headers();
    for (const [key, value] of request.headers.entries()) {
      // Skip host header to avoid Cloudflare-to-Bling host mismatch
      if (key.toLowerCase() === "host") continue;
      headers.set(key, value);
    }

    const blingResponse = await fetch(BLING_TOKEN_URL, {
      method: "POST",
      headers,
      body,
    });

    const responseBody = await blingResponse.text();

    return new Response(responseBody, {
      status: blingResponse.status,
      headers: {
        "Content-Type": blingResponse.headers.get("Content-Type") || "application/json",
        "Access-Control-Allow-Origin": "*",
      },
    });
  },
};
