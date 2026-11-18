// The top bar, previously copy-pasted into every screen.

export default function Header({
  status,
  statusState = "ok",
  onShowProgress,
  onRestart,
}) {
  return (
    <header className="navbar">
      <div className="brand">
        <div className="brand-icon">AI</div>

        <div>
          <h1>Adaptive AI Tutor</h1>
          <span>Learn at your own pace</span>
        </div>
      </div>

      <div className="navbar-actions">
        {onShowProgress && (
          <button
            type="button"
            className="nav-button"
            onClick={onShowProgress}
          >
            Progress
          </button>
        )}

        {onRestart && (
          <button type="button" className="nav-button" onClick={onRestart}>
            Start over
          </button>
        )}

        <div className="status" role="status">
          <span className={`status-dot status-dot-${statusState}`}></span>
          {status}
        </div>
      </div>
    </header>
  );
}
