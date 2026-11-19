import { useState } from "react";

// Create a profile or continue as an existing one. The backend creates the
// profile when the name is new and returns the existing one otherwise.
// There is no password: profiles are identified by name only.

export default function ProfileScreen({ onSubmit }) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (event) => {
    event.preventDefault();

    const trimmed = name.trim();

    if (!trimmed) {
      setError("Enter a name to continue.");
      return;
    }

    try {
      setBusy(true);
      setError("");

      await onSubmit(trimmed);
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
          Who's learning?
          <br />
          <span>Pick up where you left off.</span>
        </h2>

        <p>
          Enter your name to create a profile, or enter an existing one to
          continue with your saved progress.
        </p>
      </section>

      <section className="setup-card">
        <div className="card-header">
          <div>
            <h3>Your profile</h3>
            <p>New names get a fresh profile automatically.</p>
          </div>
        </div>

        <form className="form-section" onSubmit={submit}>
          <label htmlFor="profile-name">Name</label>

          <input
            id="profile-name"
            className="text-input"
            type="text"
            maxLength={100}
            autoFocus
            autoComplete="username"
            placeholder="e.g. Sharu"
            value={name}
            onChange={(event) => setName(event.target.value)}
            disabled={busy}
          />

          {error && <div className="error-message">{error}</div>}

          <button
            type="submit"
            className="start-button"
            disabled={!name.trim() || busy}
            style={{ marginTop: "20px" }}
          >
            {busy ? "Opening profile..." : "Continue"}
            <span>→</span>
          </button>
        </form>

        <p className="hint">
          Profiles are saved by name on this tutor's server. There is no
          password, so anyone who types the same name opens the same profile.
        </p>
      </section>
    </main>
  );
}
