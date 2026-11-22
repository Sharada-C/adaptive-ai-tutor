// The reteach screen used a different, unstyled layout from every other
// screen (and its CSS classes did not exist). It now uses the shared
// card layout.

export default function ReteachScreen({ reteach, busy, onContinue }) {
  return (
    <main className="main-content">
      <section className="diagnostic-card">
        <div className="hero-badge">LET'S CLEAR THIS UP</div>

        <h2 className="diagnostic-title">
          Let's take another look
          <br />
          <span>at {reteach.concept}.</span>
        </h2>

        {reteach.misconceptions && reteach.misconceptions.length > 0 && (
          <div className="misconception-box">
            <strong>What needs correction</strong>

            <ul>
              {reteach.misconceptions.map((misconception, index) => (
                <li key={index}>{misconception}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="feedback-box lesson-content">
          <strong>Reteaching</strong>
          <p>{reteach.explanation}</p>
          {reteach.mode === "extractive" && (
            <small className="mode-note">
              Shown directly from your study material. The AI's own wording
              could not be verified against it.
            </small>
          )}
        </div>

        <button
          type="button"
          className="start-button"
          onClick={onContinue}
          disabled={busy}
        >
          {busy ? "Preparing..." : "Continue Learning"}
          <span>→</span>
        </button>
      </section>
    </main>
  );
}
