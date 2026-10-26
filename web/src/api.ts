import type { CheckResponse, Health, SampleAd } from "./types";

// The API is served from the same origin as this page, so there is no CORS
// configuration and no second container.
async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      /* non-JSON error body */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const getHealth = () => json<Health>("/health");
export const getSamples = () => json<SampleAd[]>("/samples");

export interface CheckInput {
  text: string;
  advertiser: {
    name: string;
    type: string;
    fdic_insured: boolean;
    ncua_insured: boolean;
  };
  channel: string;
  context: string;
  use_llm: boolean;
}

export const postCheck = (input: CheckInput) =>
  json<CheckResponse>("/check", { method: "POST", body: JSON.stringify(input) });
