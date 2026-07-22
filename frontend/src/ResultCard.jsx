import SpringIn from "./SpringIn.jsx";
import ScoreRing from "./ScoreRing.jsx";

const VERDICT_COPY = {
  worth_it: "Worth watching",
  mixed: "Mixed",
  skip: "Skip",
};

const LABEL_COPY = {
  real_value: "real value",
  clickbait: "clickbait",
  rage_bait: "rage bait",
  mixed_signals: "mixed signals",
};

export default function ResultCard({ result, loading, onReanalyze }) {
  return (
    <div className={`result-stack verdict-${result.verdict}`} aria-live="polite">
      <SpringIn as="header" className="result-head" delay={0}>
        <div className="result-copy">
          <p className={`verdict-kicker verdict-kicker-${result.verdict}`}>
            {VERDICT_COPY[result.verdict]}
          </p>
          <h2 className="result-title">{result.title || `Video ${result.video_id}`}</h2>
          <p className="meta">
            {result.channel && <span className="meta-channel">{result.channel}</span>}
            {result.duration_hint && <span>{result.duration_hint}</span>}
            <span>confidence {result.confidence}</span>
            {result.cached && <span>cached</span>}
          </p>
          <p className="label-line">
            {result.labels.map((label, i) => (
              <span key={label}>
                {i > 0 && <span className="label-sep">·</span>}
                <span className={`label-text label-${label}`}>{LABEL_COPY[label] || label}</span>
              </span>
            ))}
          </p>
        </div>

        <ScoreRing score={result.worth_score} verdict={result.verdict} />
      </SpringIn>

      {(result.payoff_around || result.title_content_gap) && (
        <SpringIn as="section" className="result-section" delay={40}>
          <div className="grid-2">
            {result.payoff_around && (
              <div>
                <h3>Payoff</h3>
                <p className="panel-body panel-body-emphasis">{result.payoff_around}</p>
              </div>
            )}
            {result.title_content_gap && (
              <div>
                <h3>Title vs content</h3>
                <p className="panel-body">{result.title_content_gap}</p>
              </div>
            )}
          </div>
        </SpringIn>
      )}

      <SpringIn as="section" className="result-section" delay={80}>
        <h3 className="section-label">What you actually get</h3>
        <ol className="bullets">
          {result.summary_bullets.map((bullet, index) => (
            <li key={bullet}>
              <span className="bullet-index">{String(index + 1).padStart(2, "0")}</span>
              <span className="bullet-text">{bullet}</span>
            </li>
          ))}
        </ol>
      </SpringIn>

      <SpringIn as="section" className="result-section" delay={120}>
        <div className="grid-2">
          <div>
            <h3 className="watch-label">Watch if</h3>
            <p className="panel-body panel-body-emphasis">{result.watch_if}</p>
          </div>
          <div>
            <h3 className="skip-label">Skip if</h3>
            <p className="panel-body panel-body-emphasis">{result.skip_if}</p>
          </div>
        </div>
      </SpringIn>

      <SpringIn as="section" className="result-section" delay={160}>
        <p className="bait">
          <span className="bait-label">Bait risk</span>
          {result.bait_risk}
        </p>
      </SpringIn>

      {result.evidence_quotes?.length > 0 && (
        <SpringIn as="section" className="result-section" delay={200}>
          <h3 className="section-label">From the transcript</h3>
          {result.evidence_quotes.map((quote) => (
            <blockquote key={quote}>{quote}</blockquote>
          ))}
        </SpringIn>
      )}

      <SpringIn as="footer" className="result-actions" delay={240}>
        <button
          type="button"
          className="btn btn-secondary"
          disabled={loading}
          onClick={onReanalyze}
        >
          {loading ? "Re-analyzing…" : "Re-analyze"}
        </button>
        <a
          className="btn btn-ghost"
          href={`https://www.youtube.com/watch?v=${result.video_id}`}
          target="_blank"
          rel="noreferrer"
        >
          Open on YouTube
        </a>
      </SpringIn>
    </div>
  );
}
