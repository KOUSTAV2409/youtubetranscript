const VERDICT_COPY = {
  worth_it: "Worth watching",
  mixed: "Mixed — proceed carefully",
  skip: "Probably skip",
};

const LABEL_COPY = {
  real_value: "Real value",
  clickbait: "Clickbait risk",
  rage_bait: "Rage bait",
  mixed_signals: "Mixed signals",
};

export default function ResultCard({ result, loading, onReanalyze }) {
  const metaBits = [
    result.channel,
    result.duration_hint ? `Duration ${result.duration_hint}` : null,
    `Confidence: ${result.confidence}`,
    result.cached ? "cached" : null,
  ].filter(Boolean);

  return (
    <section className={`result verdict-${result.verdict}`} aria-live="polite">
      <div className="result-top">
        <div>
          <p className="verdict-label">{VERDICT_COPY[result.verdict]}</p>
          <h2>{result.title || `Video ${result.video_id}`}</h2>
          <p className="meta">{metaBits.join(" · ")}</p>
        </div>
        <div className="score" aria-label={`Worth score ${result.worth_score} out of 100`}>
          <span className="score-num">{result.worth_score}</span>
          <span className="score-den">/100</span>
        </div>
      </div>

      <ul className="labels">
        {result.labels.map((label) => (
          <li key={label} className={`label label-${label}`}>
            {LABEL_COPY[label] || label}
          </li>
        ))}
      </ul>

      {(result.payoff_around || result.title_content_gap) && (
        <div className="insight-row">
          {result.payoff_around && (
            <div>
              <h3>Payoff around</h3>
              <p>{result.payoff_around}</p>
            </div>
          )}
          {result.title_content_gap && (
            <div>
              <h3>Title vs content</h3>
              <p>{result.title_content_gap}</p>
            </div>
          )}
        </div>
      )}

      <ul className="bullets">
        {result.summary_bullets.map((bullet) => (
          <li key={bullet}>{bullet}</li>
        ))}
      </ul>

      <div className="guidance">
        <div>
          <h3>Watch if</h3>
          <p>{result.watch_if}</p>
        </div>
        <div>
          <h3>Skip if</h3>
          <p>{result.skip_if}</p>
        </div>
      </div>

      <p className="bait">{result.bait_risk}</p>

      {result.evidence_quotes?.length > 0 && (
        <div className="quotes">
          <h3>Evidence from transcript</h3>
          {result.evidence_quotes.map((quote) => (
            <blockquote key={quote}>{quote}</blockquote>
          ))}
        </div>
      )}

      <div className="result-actions">
        <button type="button" className="ghost-btn" disabled={loading} onClick={onReanalyze}>
          {loading ? "Re-analyzing…" : "Re-analyze (skip cache)"}
        </button>
        <a
          className="ghost-link"
          href={`https://www.youtube.com/watch?v=${result.video_id}`}
          target="_blank"
          rel="noreferrer"
        >
          Open on YouTube
        </a>
      </div>
    </section>
  );
}
