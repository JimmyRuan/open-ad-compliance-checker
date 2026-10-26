import { useEffect, useState } from "react";
import { getHealth, getSamples, postCheck } from "./api";
import type { CheckResponse, Finding, Health, SampleAd } from "./types";

const ADVERTISER_TYPES = [
  { value: "bank", label: "Bank" },
  { value: "credit_union", label: "Credit union" },
  { value: "nonbank", label: "Nonbank lender" },
];

const VERDICT_LABEL: Record<string, string> = {
  violates: "May violate",
  unclear: "Unclear — needs a reviewer",
  meets: "Appears met",
  not_applicable: "Considered, ruled out",
};

function FindingCard({ f, judged }: { f: Finding; judged: boolean }) {
  // With verdicts off nothing was assessed, so showing "considered, ruled out"
  // would assert a judgement the tool never made. Retrieval rank is all we can
  // honestly claim.
  const verdict = judged ? f.verdict : "retrieved";
  return (
    <article className={`card v-${verdict}`}>
      <header>
        <span className={`badge b-${verdict}`}>
          {judged ? VERDICT_LABEL[f.verdict] : "Retrieved"}
        </span>
        {/* Every citation deep-links to its own paragraph on eCFR. */}
        <a className="cite" href={f.url} target="_blank" rel="noreferrer">
          {f.citation}
        </a>
        <span className="reg">
          {f.regulation} · {f.agency}
        </span>
      </header>

      {f.reason && <p className="reason">{f.reason}</p>}
      {f.ad_evidence && <p className="quote">“{f.ad_evidence}”</p>}
      {f.caveat && <p className="caveat">Caveat: {f.caveat}</p>}

      <details>
        <summary>Provision text</summary>
        <p className="provision">{f.provision_text}</p>
        <p className="meta">
          {f.heading} · as of {f.as_of} · retrieved by: {f.why_retrieved.join(", ")}
        </p>
      </details>
    </article>
  );
}

export default function App() {
  const [text, setText] = useState("");
  const [context, setContext] = useState("");
  const [type, setType] = useState("bank");
  const [channel, setChannel] = useState("instagram");
  const [name, setName] = useState("");
  const [fdic, setFdic] = useState(true);
  const [ncua, setNcua] = useState(false);

  // Defaults to on once we know a key is configured, so the common case is one
  // click; turning it off keeps the check entirely local.
  const [useLlm, setUseLlm] = useState(false);

  const [health, setHealth] = useState<Health | null>(null);
  const [samples, setSamples] = useState<SampleAd[]>([]);
  const [result, setResult] = useState<CheckResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    getHealth()
      .then((h) => {
        setHealth(h);
        setUseLlm(h.verdicts_enabled);
      })
      .catch((e) => setError(String(e)));
    getSamples().then(setSamples).catch(() => undefined);
  }, []);

  // A verdict run is one reasoning call and takes tens of seconds. Without a
  // visible clock a working request is indistinguishable from a hung one.
  useEffect(() => {
    if (!busy) return;
    const started = Date.now();
    setElapsed(0);
    const id = window.setInterval(() => setElapsed(Math.round((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(id);
  }, [busy]);

  function loadSample(id: string) {
    const s = samples.find((x) => x.id === id);
    if (!s) return;
    setText(s.text);
    setContext(s.context ?? "");
    setType(s.advertiser.type);
    setChannel(s.channel);
    setName(s.advertiser.name);
    setFdic(Boolean(s.advertiser.fdic_insured));
    setNcua(Boolean(s.advertiser.ncua_insured));
    setResult(null);
  }

  async function run() {
    setBusy(true);
    setError("");
    try {
      setResult(
        await postCheck({
          text,
          context,
          channel,
          advertiser: { name, type, fdic_insured: fdic, ncua_insured: ncua },
          use_llm: useLlm,
        }),
      );
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <h1>Ad compliance check</h1>
      <p className="sub">
        Paste a social-media ad, pick the advertiser type, and get the provisions that may
        apply — each with its citation, the provision text, why it applies, and whether the
        ad appears to meet it. <strong>Advisory only</strong>: it surfaces provisions for a
        human reviewer and does not assert a legal conclusion.
      </p>

      <section className="panel">
        <label>
          Load a sample ad
          <select value="" onChange={(e) => loadSample(e.target.value)}>
            <option value="">— choose —</option>
            {samples.map((s) => (
              <option key={s.id} value={s.id}>
                {s.id} — {s.advertiser.name} ({s.advertiser.type})
              </option>
            ))}
          </select>
        </label>

        <label>
          Ad text
          <textarea
            rows={5}
            value={text}
            placeholder="Paste the ad copy here…"
            onChange={(e) => setText(e.target.value)}
          />
        </label>

        <div className="row">
          <label>
            Advertiser type
            <select value={type} onChange={(e) => setType(e.target.value)}>
              {ADVERTISER_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Channel
            <select value={channel} onChange={(e) => setChannel(e.target.value)}>
              {["instagram", "facebook", "linkedin", "x"].map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>
          <label>
            Advertiser name
            <input value={name} onChange={(e) => setName(e.target.value)} />
          </label>
        </div>

        <div className="row">
          <label className="check">
            <input type="checkbox" checked={fdic} onChange={(e) => setFdic(e.target.checked)} />
            FDIC insured
          </label>
          <label className="check">
            <input type="checkbox" checked={ncua} onChange={(e) => setNcua(e.target.checked)} />
            NCUA insured
          </label>
        </div>

        <label>
          Reviewer context <small>(facts the ad omits — e.g. a fee it doesn’t mention)</small>
          <textarea
            rows={2}
            value={context}
            onChange={(e) => setContext(e.target.value)}
          />
        </label>

        <div className="actions">
          <button className="primary" disabled={!text.trim() || busy} onClick={run}>
            {busy ? `Checking… ${elapsed}s` : "Check this ad"}
          </button>

          {/* The reviewer's own switch over the only outbound call in the
              system. Off is a real tier, not a degraded one: citations,
              provision text and links all still come back. */}
          <label className={`toggle${health?.verdicts_enabled ? "" : " off"}`}>
            <input
              type="checkbox"
              role="switch"
              checked={useLlm}
              disabled={busy || !health?.verdicts_enabled}
              onChange={(e) => setUseLlm(e.target.checked)}
            />
            <span>
              {health?.verdicts_enabled
                ? useLlm
                  ? `Verdicts on — sends the ad to ${health.model}`
                  : "Verdicts off — nothing leaves this machine"
                : "Verdicts unavailable — no OPENAI_API_KEY set"}
            </span>
          </label>
        </div>

        {busy && (
          <p className="working">
            {useLlm
              ? "Retrieval is local and takes under a second; the wait is the model reasoning over every candidate provision."
              : "Searching the local corpus…"}
          </p>
        )}
        {error && <p className="err">{error}</p>}
      </section>

      {health && (
        <p className="scope">
          Scope: {health.provisions} provisions from{" "}
          {health.regulations.map((r) => r.regulation).join(", ")} (as of{" "}
          {health.regulations[0]?.as_of}).{" "}
          {health.verdicts_enabled
            ? `Verdicts generated with ${health.model}.`
            : "Retrieval-only — no OPENAI_API_KEY set, so nothing leaves this machine."}
        </p>
      )}

      {result && (
        <section className="results">
          {result.notices.map((n, i) => (
            <p className="notice" key={i}>
              {n}
            </p>
          ))}
          {result.overall_note && <p className="notice">{result.overall_note}</p>}

          <p className="gate">
            Searched {result.gate.parts_in_scope.join(", ")} ·{" "}
            {result.candidate_count} candidates
            {result.gate.excluded.length > 0 && (
              <>
                {" "}
                · <strong>excluded:</strong> {result.gate.excluded.join("; ")}
              </>
            )}
          </p>

          {result.dropped_findings.length > 0 && (
            <p className="notice">
              {result.dropped_findings.length} model finding(s) were dropped as ungrounded:{" "}
              {result.dropped_findings.map((d) => d.reason).join("; ")}
            </p>
          )}

          {result.findings.length === 0 && <p>No provisions matched this submission.</p>}
          {result.findings.map((f) => (
            <FindingCard key={f.ref} f={f} judged={result.mode === "verdicts"} />
          ))}
        </section>
      )}
    </main>
  );
}
