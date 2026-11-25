// The top bar, previously copy-pasted into every screen.

export default function Header({
  status,
  statusState = "ok",
  profileName,
  role,
  onSignOut,
  onShowAdmin,
  onShowProgress,
  onShowLibrary,
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
        {onShowLibrary && (
          <button type="button" className="nav-button" onClick={onShowLibrary}>
            My learning
          </button>
        )}

        {onShowProgress && (
          <button
            type="button"
            className="nav-button"
            onClick={onShowProgress}
          >
            Progress
          </button>
        )}

        {onShowAdmin && (
          <button type="button" className="nav-button" onClick={onShowAdmin}>
            Manage users
          </button>
        )}

        {profileName && (
          <span className="profile-chip" title="Signed in as">
            {profileName}
            {role && role !== "student" && (
              <small className="role-badge">{role}</small>
            )}
          </span>
        )}

        {onSignOut && (
          <button type="button" className="nav-button" onClick={onSignOut}>
            Sign out
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
