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

function ScoreRing({ score, verdict }) {
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (Math.min(100, Math.max(0, score)) / 100) * circumference;

  return (
    <div className={`score-ring verdict-${verdict}`} aria-label={`Worth score ${score} out of 100`}>
      <svg viewBox="0 0 100 100" className="score-svg">
        <circle className="score-track" cx="50" cy="50" r={radius} />
        <circle
          className="score-progress"
          cx="50"
          cy="50"
          r={radius}
          style={{
            strokeDasharray: circumference,
            strokeDashoffset: offset,
          }}
        />
      </svg>
      <div className="score-center">
        <span className="score-num">{score}</span>
        <span className="score-den">/100</span>
      </div>
    </div>
  );
}

export default function ResultCard({ result, loading, onReanalyze }) {
  const metaBits = [
    result.channel,
    result.duration_hint,
    result.confidence,
    result.cached ? "cached" : null,
  ].filter(Boolean);

  return (
    <section className={`result verdict-${result.verdict}`} aria-live="polite">
      <div className="result-rule" aria-hidden="true" />

      <div className="result-top">
        <div className="result-copy">
          <p className="verdict-label">{VERDICT_COPY[result.verdict]}</p>
          <h2>{result.title || `Video ${result.video_id}`}</h2>
          <p className="meta">
            {metaBits.map((bit, index) => (
              <span key={bit}>
                {index > 0 && <span className="meta-dot">·</span>}
                {bit}
              </span>
            ))}
          </p>
        </div>
        <ScoreRing score={result.worth_score} verdict={result.verdict} />
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
            <div className="insight">
              <h3>Payoff around</h3>
              <p>{result.payoff_around}</p>
            </div>
          )}
          {result.title_content_gap && (
            <div className="insight">
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
        <div className="guidance-block watch">
          <h3>Watch if</h3>
          <p>{result.watch_if}</p>
        </div>
        <div className="guidance-block skip">
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
          {loading ? "Re-analyzing…" : "Re-analyze"}
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
