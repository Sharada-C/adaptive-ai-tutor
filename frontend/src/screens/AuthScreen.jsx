import { useState } from "react";

// Sign in or create an account. Public sign-up always creates a learner;
// instructor and admin roles are granted by an admin.

const MIN_PASSWORD = 8;

export default function AuthScreen({ onSignIn, onRegister }) {
  const [mode, setMode] = useState("signin");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const registering = mode === "register";

  const switchMode = (next) => {
    setMode(next);
    setError("");
    setPassword("");
    setConfirm("");
  };

  const submit = async (event) => {
    event.preventDefault();

    const name = username.trim();

    if (!name || !password) {
      setError("Enter your username and password.");
      return;
    }

    if (registering) {
      if (password.length < MIN_PASSWORD) {
        setError(`Use a password of at least ${MIN_PASSWORD} characters.`);
        return;
      }

      if (password !== confirm) {
        setError("The two passwords do not match.");
        return;
      }
    }

    try {
      setBusy(true);
      setError("");

      await (registering ? onRegister(name, password) : onSignIn(name, password));
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <main className="main-content">
      <section className="hero">
        <div className="hero-badge">WELCOME</div>

        <h2>
          {registering ? "Create your account." : "Welcome back."}
          <br />
          <span>Pick up where you left off.</span>
        </h2>

        <p>
          Your progress is saved to your account, so you can continue on any
          device.
        </p>
      </section>

      <section className="setup-card">
        <div className="auth-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={!registering}
            className={`auth-tab ${!registering ? "selected" : ""}`}
            onClick={() => switchMode("signin")}
          >
            Sign in
          </button>

          <button
            type="button"
            role="tab"
            aria-selected={registering}
            className={`auth-tab ${registering ? "selected" : ""}`}
            onClick={() => switchMode("register")}
          >
            Create account
          </button>
        </div>

        <form className="form-section" onSubmit={submit} noValidate>
          <label htmlFor="auth-username">Username</label>

          <input
            id="auth-username"
            className="text-input"
            type="text"
            maxLength={100}
            autoFocus
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            disabled={busy}
          />

          <label htmlFor="auth-password" style={{ marginTop: "16px" }}>
            Password
          </label>

          <input
            id="auth-password"
            className="text-input"
            type="password"
            maxLength={128}
            autoComplete={registering ? "new-password" : "current-password"}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            disabled={busy}
          />

          {registering && (
            <>
              <label htmlFor="auth-confirm" style={{ marginTop: "16px" }}>
                Confirm password
              </label>

              <input
                id="auth-confirm"
                className="text-input"
                type="password"
                maxLength={128}
                autoComplete="new-password"
                value={confirm}
                onChange={(event) => setConfirm(event.target.value)}
                disabled={busy}
              />

              <p className="hint">
                Usernames are 3-50 letters, numbers, dots, dashes or
                underscores. Passwords need at least {MIN_PASSWORD} characters.
              </p>
            </>
          )}

          {error && (
            <div className="error-message" role="alert">
              {error}
            </div>
          )}

          <button
            type="submit"
            className="start-button"
            disabled={busy}
            style={{ marginTop: "20px" }}
          >
            {busy
              ? registering
                ? "Creating account..."
                : "Signing in..."
              : registering
                ? "Create account"
                : "Sign in"}
            <span>→</span>
          </button>
        </form>
      </section>
    </main>
  );
}
