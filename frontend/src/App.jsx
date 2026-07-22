import { useState } from "react";
import ResultCard from "./ResultCard.jsx";

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
      <div className="atmosphere" aria-hidden="true" />
      <main className="shell">
        <header className="brand-block">
          <p className="brand">WorthWatch</p>
          <h1>Paste a YouTube link. Find out if it&apos;s worth your time.</h1>
          <p className="lede">
            We read the transcript and flag real value vs clickbait vs rage bait —
            before you hit play.
          </p>
        </header>

        <form className="paste-form" onSubmit={onSubmit}>
          <label htmlFor="yt-url" className="sr-only">
            YouTube URL
          </label>
          <input
            id="yt-url"
            type="url"
            required
            placeholder="https://www.youtube.com/watch?v=..."
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            disabled={loading}
          />
          <button type="submit" disabled={loading || !url.trim()}>
            {loading ? "Analyzing…" : "Is it worth it?"}
          </button>
        </form>

        {loading && (
          <p className="status" role="status">
            Pulling metadata, transcript, and scoring the video…
          </p>
        )}

        {error && (
          <div className="error" role="alert">
            <p>{error}</p>
            <button
              type="button"
              className="retry-btn"
              disabled={loading || !url.trim()}
              onClick={() => analyze(true)}
            >
              Retry / Re-analyze
            </button>
          </div>
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
