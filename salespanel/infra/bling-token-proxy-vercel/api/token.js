const BLING_TOKEN_URL = "https://www.bling.com.br/Api/v3/oauth/token";

export default async function handler(req, res) {
  if (req.method === "OPTIONS") {
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization, Accept, User-Agent");
    return res.status(204).end();
  }

  if (req.method !== "POST") {
    res.setHeader("Allow", "POST, OPTIONS");
    return res.status(405).send("Method Not Allowed");
  }

  const body = typeof req.body === "string" ? req.body : new URLSearchParams(req.body ?? {}).toString();

  const headers = new Headers();
  for (const [key, value] of Object.entries(req.headers)) {
    if (!value) {
      continue;
    }
    if (key.toLowerCase() === "host" || key.toLowerCase() === "content-length") {
      continue;
    }
    headers.set(key, Array.isArray(value) ? value.join(", ") : value);
  }

  const blingResponse = await fetch(BLING_TOKEN_URL, {
    method: "POST",
    headers,
    body,
  });

  const responseBody = await blingResponse.text();

  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Content-Type", blingResponse.headers.get("content-type") || "application/json");
  return res.status(blingResponse.status).send(responseBody);
}