const MASTERED_THRESHOLD = 0.8;

function percent(value) {
  return Math.round(value * 100);
}

function ProgressBar({ value, style }) {
  return (
    <div className="progress-track" style={style}>
      <div className="progress-fill" style={{ width: `${value * 100}%` }}></div>
    </div>
  );
}

export default function ProgressScreen({
  subject,
  concepts,
  masteryData,
  studentProfile,
  loading,
  error,
  onContinue,
  loadingLesson,
}) {
  const conceptMap = new Map(concepts.map((concept) => [concept.id, concept]));

  const subjectMastery = masteryData.filter((item) =>
    conceptMap.has(item.concept_id)
  );

  const overallMastery =
    subjectMastery.length > 0
      ? subjectMastery.reduce((sum, item) => sum + item.mastery_score, 0) /
        subjectMastery.length
      : 0;

  const masteredCount = subjectMastery.filter(
    (item) => item.mastery_score >= MASTERED_THRESHOLD
  ).length;

  const learningCount = subjectMastery.length - masteredCount;

  const totalAttempts = subjectMastery.reduce(
    (sum, item) => sum + item.attempts,
    0
  );

  return (
    <main className="main-content">
      <section className="diagnostic-card">
        <div className="hero-badge">YOUR PROGRESS</div>

        <h2 className="diagnostic-title">
          See how you're
          <br />
          <span>progressing.</span>
        </h2>

        {subject && <p className="lesson-description">{subject.name}</p>}

        {loading ? (
          <div className="loading-message">Loading your progress...</div>
        ) : error ? (
          <div className="error-message">{error}</div>
        ) : (
          <>
            {/* OVERALL MASTERY */}

            <div className="feedback-box">
              <strong>Overall Mastery</strong>

              <div
                style={{ fontSize: "42px", fontWeight: "700", marginTop: "8px" }}
              >
                {percent(overallMastery)}%
              </div>

              <ProgressBar value={overallMastery} style={{ marginTop: "12px" }} />
            </div>

            {/* LEARNER PROFILE */}

            {studentProfile && (
              <div className="feedback-box" style={{ marginTop: "24px" }}>
                <div className="concept-label">LEARNER PROFILE</div>

                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginTop: "12px",
                    gap: "16px",
                    flexWrap: "wrap",
                  }}
                >
                  <div>
                    <strong>Learning Level</strong>
                    <p style={{ marginTop: "6px", textTransform: "capitalize" }}>
                      {studentProfile.learning_level}
                    </p>
                  </div>

                  <div>
                    <strong>Overall Mastery</strong>
                    <p style={{ marginTop: "6px" }}>
                      {percent(studentProfile.overall_mastery)}%
                    </p>
                  </div>
                </div>

                <div style={{ marginTop: "20px" }}>
                  <strong>Subject Progress</strong>

                  {studentProfile.subject_mastery.map((item) => (
                    <div key={item.subject_id} style={{ marginTop: "14px" }}>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                        }}
                      >
                        <span>{item.subject_name}</span>
                        <span>{percent(item.mastery)}%</span>
                      </div>

                      <ProgressBar
                        value={item.mastery}
                        style={{ marginTop: "8px" }}
                      />
                    </div>
                  ))}
                </div>

                <div style={{ marginTop: "24px" }}>
                  <strong>Concepts to Strengthen</strong>

                  {studentProfile.concepts_to_strengthen.length === 0 ? (
                    <p style={{ marginTop: "10px", opacity: 0.7 }}>
                      No concepts currently need additional strengthening.
                    </p>
                  ) : (
                    studentProfile.concepts_to_strengthen.map((concept) => (
                      <div
                        key={concept.concept_id}
                        style={{
                          marginTop: "14px",
                          padding: "12px",
                          border: "1px solid #e6e7eb",
                          borderRadius: "10px",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            gap: "12px",
                          }}
                        >
                          <div>
                            <strong>{concept.concept_name}</strong>

                            <small
                              style={{
                                display: "block",
                                marginTop: "4px",
                                opacity: 0.7,
                              }}
                            >
                              {concept.subject_name}
                            </small>
                          </div>

                          <span>{percent(concept.mastery)}%</span>
                        </div>

                        <ProgressBar
                          value={concept.mastery}
                          style={{ marginTop: "8px" }}
                        />
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}

            {/* SUMMARY */}

            <div className="features">
              <div className="feature">
                <span>✓</span>
                <div>
                  <strong>{masteredCount}</strong>
                  <p>Concepts mastered</p>
                </div>
              </div>

              <div className="feature">
                <span>📚</span>
                <div>
                  <strong>{learningCount}</strong>
                  <p>Concepts to strengthen</p>
                </div>
              </div>

              <div className="feature">
                <span>🎯</span>
                <div>
                  <strong>{totalAttempts}</strong>
                  <p>Total attempts</p>
                </div>
              </div>
            </div>

            {/* CONCEPT BREAKDOWN */}

            <div style={{ marginTop: "28px" }}>
              <div className="concept-label">CONCEPT BREAKDOWN</div>

              {subjectMastery.length === 0 ? (
                <div className="loading-message">
                  No mastery data available yet.
                </div>
              ) : (
                subjectMastery.map((mastery) => {
                  const concept = conceptMap.get(mastery.concept_id);

                  return (
                    <div
                      key={mastery.concept_id}
                      style={{
                        marginTop: "18px",
                        padding: "16px",
                        border: "1px solid #e6e7eb",
                        borderRadius: "12px",
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          gap: "12px",
                        }}
                      >
                        <strong>{concept.name}</strong>
                        <span>{percent(mastery.mastery_score)}%</span>
                      </div>

                      <ProgressBar
                        value={mastery.mastery_score}
                        style={{ marginTop: "10px" }}
                      />

                      <small
                        style={{
                          display: "block",
                          marginTop: "8px",
                          opacity: 0.7,
                        }}
                      >
                        {mastery.attempts} attempts • {mastery.correct_answers}{" "}
                        correct
                      </small>
                    </div>
                  );
                })
              )}
            </div>

            {/* CONTINUE */}

            <button
              type="button"
              className="start-button"
              onClick={onContinue}
              disabled={loadingLesson}
              style={{ marginTop: "28px" }}
            >
              {loadingLesson ? "Preparing..." : "Continue Learning"}
              <span>→</span>
            </button>
          </>
        )}
      </section>
    </main>
  );
}
