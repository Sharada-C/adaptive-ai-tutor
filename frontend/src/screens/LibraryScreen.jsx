import { useState } from "react";

const percent = (value) => Math.round(value * 100);

const STATUS_LABEL = {
  mastered: "Mastered",
  learning: "In progress",
  not_started: "Not started",
};

function Bar({ value }) {
  return (
    <div className="progress-track" style={{ margin: "8px 0 0" }}>
      <div className="progress-fill" style={{ width: `${value * 100}%` }}></div>
    </div>
  );
}

function formatDate(value) {
  if (!value) {
    return "";
  }

  const date = new Date(value.endsWith("Z") ? value : `${value}Z`);

  return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString();
}

function ConceptEntry({ concept }) {
  return (
    <div className="journal-concept">
      <div className="journal-concept-head">
        <strong>{concept.name}</strong>
        <span className={`status-chip status-chip-${concept.status}`}>
          {STATUS_LABEL[concept.status]}
        </span>
      </div>

      {concept.attempts > 0 && (
        <small className="journal-meta">
          {percent(concept.mastery)}% mastery • {concept.attempts} attempts
          {concept.last_studied
            ? ` • last studied ${formatDate(concept.last_studied)}`
            : ""}
        </small>
      )}

      {concept.takeaways.length > 0 && (
        <div className="journal-block">
          <div className="concept-label">WHAT YOU'VE SHOWN YOU KNOW</div>
          <ul>
            {concept.takeaways.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
        </div>
      )}

      {concept.open_misconceptions.length > 0 && (
        <div className="misconception-box">
          <strong>Still to clear up</strong>
          <ul>
            {concept.open_misconceptions.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
        </div>
      )}

      {concept.history.length > 0 && (
        <details className="journal-history">
          <summary>Your recent answers ({concept.history.length})</summary>
          {concept.history.map((item, index) => (
            <div key={index} className="journal-answer">
              <p>
                <strong>Q:</strong> {item.question}
              </p>
              <p>
                <strong>You:</strong> {item.your_answer}
              </p>
              <small>
                {percent(item.score)}% • {item.result.replace("_", " ")}
              </small>
            </div>
          ))}
        </details>
      )}
    </div>
  );
}

export default function LibraryScreen({
  courses,
  loading,
  error,
  loadJournal,
  onContinue,
  onDelete,
  onNewTopic,
  busy,
}) {
  const [openId, setOpenId] = useState(null);
  const [journals, setJournals] = useState({});
  const [journalLoading, setJournalLoading] = useState(false);
  const [journalError, setJournalError] = useState("");
  const [confirmingId, setConfirmingId] = useState(null);

  const toggleJournal = async (subjectId) => {
    if (openId === subjectId) {
      setOpenId(null);
      return;
    }

    setOpenId(subjectId);
    setJournalError("");
    setJournalLoading(true);

    try {
      const journal = await loadJournal(subjectId);
      setJournals((previous) => ({ ...previous, [subjectId]: journal }));
    } catch (loadError) {
      setJournalError(loadError.message);
    } finally {
      setJournalLoading(false);
    }
  };

  return (
    <main className="main-content">
      <section className="diagnostic-card">
        <div className="hero-badge">MY LEARNING</div>

        <h2 className="diagnostic-title">
          Everything you're
          <br />
          <span>learning.</span>
        </h2>

        <button
          type="button"
          className="start-button"
          onClick={onNewTopic}
          style={{ marginBottom: "24px" }}
        >
          Learn something new
          <span>→</span>
        </button>

        {loading ? (
          <div className="loading-message">Loading your courses...</div>
        ) : error ? (
          <div className="error-message">{error}</div>
        ) : courses.length === 0 ? (
          <div className="loading-message">
            You haven't started any course yet. Pick a topic to begin.
          </div>
        ) : (
          courses.map((course) => (
            <div key={course.subject_id} className="feedback-box library-course">
              <div className="journal-concept-head">
                <strong>
                  {course.name}
                  {course.is_private ? " (my course)" : ""}
                </strong>
                <span>{percent(course.mastery)}%</span>
              </div>

              <Bar value={course.mastery} />

              <small className="journal-meta">
                {course.mastered_concepts} of {course.total_concepts} concepts
                mastered
                {course.last_activity
                  ? ` • last studied ${formatDate(course.last_activity)}`
                  : ""}
              </small>

              <div className="library-actions">
                <button
                  type="button"
                  className="nav-button"
                  disabled={busy}
                  onClick={() => onContinue(course.subject_id)}
                >
                  {course.mastered_concepts >= course.total_concepts &&
                  course.total_concepts > 0
                    ? "Review"
                    : "Continue"}
                </button>

                <button
                  type="button"
                  className="nav-button"
                  onClick={() => toggleJournal(course.subject_id)}
                >
                  {openId === course.subject_id
                    ? "Hide what I've learned"
                    : "What I've learned"}
                </button>

                {course.is_private && confirmingId !== course.subject_id && (
                  <button
                    type="button"
                    className="nav-button nav-button-danger"
                    onClick={() => setConfirmingId(course.subject_id)}
                  >
                    Delete course
                  </button>
                )}
              </div>

              {confirmingId === course.subject_id && (
                <div className="misconception-box" style={{ marginTop: "14px" }}>
                  <strong>
                    Delete "{course.name}" and all your progress in it?
                  </strong>
                  <p>This cannot be undone.</p>
                  <div className="library-actions">
                    <button
                      type="button"
                      className="nav-button nav-button-danger"
                      onClick={() => {
                        setConfirmingId(null);
                        onDelete(course.subject_id);
                      }}
                    >
                      Yes, delete it
                    </button>
                    <button
                      type="button"
                      className="nav-button"
                      onClick={() => setConfirmingId(null)}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {openId === course.subject_id &&
                (journalLoading && !journals[course.subject_id] ? (
                  <div className="loading-message">Loading...</div>
                ) : journalError ? (
                  <div className="error-message">{journalError}</div>
                ) : (
                  journals[course.subject_id]?.concepts.map((concept) => (
                    <ConceptEntry key={concept.concept_id} concept={concept} />
                  ))
                ))}
            </div>
          ))
        )}
      </section>
    </main>
  );
}
