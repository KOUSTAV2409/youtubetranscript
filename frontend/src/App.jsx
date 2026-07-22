import { useState } from "react";
import ResultCard from "./ResultCard.jsx";
import SpringIn from "./SpringIn.jsx";

const API_BASE = import.meta.env.VITE_API_BASE || "/api";

function formatApiError(data, fallback = "Analysis failed") {
  const detail = data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || JSON.stringify(item)).join(" ");
  }
  return data?.error || fallback;
}

export default function App() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [pressed, setPressed] = useState(false);

  async function analyze(force = false) {
    setError("");
    if (!force) setResult(null);
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, force }),
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(formatApiError(data));
      }

      setResult(data.result);
    } catch (err) {
      setError(err.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(event) {
    event.preventDefault();
    analyze(false);
  }

  return (
    <div className="page">
      <header className="topbar">
        <div className="topbar-inner">
          <a className="logo" href="/">
            Worth<span>Watch</span>
          </a>
          <span className="topbar-meta">pre-watch filter</span>
        </div>
        <div className="topbar-edge" aria-hidden="true" />
      </header>

      <main className="shell">
        <section className="hero">
          <p className="eyebrow">Judgment before play</p>
          <h1>
            Is this YouTube video
            <em> worth </em>
            your time?
          </h1>
          <p className="lede">
            Paste a link. We read the transcript and flag real value, clickbait, and rage bait
            before you hit play.
          </p>
        </section>

        <form className="paste-form" onSubmit={onSubmit}>
          <label className="field-label" htmlFor="yt-url">
            YouTube URL
          </label>
          <div className="input-group">
            <input
              id="yt-url"
              type="url"
              required
              placeholder="https://youtube.com/watch?v=..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={loading}
            />
            <button
              className={`btn btn-primary ${pressed ? "is-pressed" : ""}`}
              type="submit"
              disabled={loading || !url.trim()}
              onPointerDown={() => setPressed(true)}
              onPointerUp={() => setPressed(false)}
              onPointerCancel={() => setPressed(false)}
              onPointerLeave={() => setPressed(false)}
            >
              {loading ? "Analyzing…" : "Analyze"}
            </button>
          </div>
          {loading && (
            <div className="progress-track" aria-hidden="true">
              <div className="progress-fill" />
            </div>
          )}
        </form>

        {loading && (
          <p className="status" role="status">
            fetching transcript · scoring substance
          </p>
        )}

        {error && (
          <SpringIn className="alert" as="div" role="alert">
            <p className="alert-title">Couldn’t analyze</p>
            <p className="alert-body">{error}</p>
            <button
              type="button"
              className="btn btn-ghost"
              disabled={loading || !url.trim()}
              onClick={() => analyze(true)}
            >
              Retry
            </button>
          </SpringIn>
        )}

        {result && (
          <ResultCard
            result={result}
            loading={loading}
            onReanalyze={() => analyze(true)}
          />
        )}
      </main>
    </div>
  );
}
