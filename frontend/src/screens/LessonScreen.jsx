export default function LessonScreen({
  nextConcept,
  lesson,
  loadingLesson,
  loadingQuiz,
  loadingProgress,
  onStartQuiz,
  onGenerateLesson,
  onViewProgress,
}) {
  return (
    <main className="main-content">
      <section className="diagnostic-card">
        <div className="hero-badge">YOUR NEXT LESSON</div>

        {nextConcept ? (
          <>
            <h2 className="diagnostic-title">
              Let's learn
              <br />
              <span>{nextConcept.name}.</span>
            </h2>

            {nextConcept.description && (
              <p className="lesson-description">{nextConcept.description}</p>
            )}
          </>
        ) : (
          <>
            <h2 className="diagnostic-title">
              You've reached the end
              <br />
              <span>of this learning path.</span>
            </h2>

            <p>
              You have demonstrated mastery of the available concepts for this
              subject.
            </p>

            <button
              type="button"
              className="start-button"
              onClick={onViewProgress}
              disabled={loadingProgress}
              style={{ marginTop: "24px" }}
            >
              {loadingProgress ? "Loading Progress..." : "View Your Progress"}
              <span>→</span>
            </button>
          </>
        )}

        {loadingLesson ? (
          <div className="loading-message">
            Generating your personalized lesson...
          </div>
        ) : lesson ? (
          <>
            <div className="feedback-box lesson-content">
              <strong>Explanation</strong>
              <p>{lesson.explanation}</p>
              {lesson.mode === "extractive" && (
                <small className="mode-note">
                  Shown directly from your study material. The AI's own
                  wording could not be verified against it.
                </small>
              )}
            </div>

            {lesson.retrieved_knowledge &&
              lesson.retrieved_knowledge.length > 0 && (
                <div className="misconception-box">
                  <strong>Knowledge used by your tutor</strong>

                  {lesson.retrieved_knowledge.map((item, index) => (
                    <div
                      key={`${item.source}-${index}`}
                      className="knowledge-item"
                    >
                      <small>{item.source}</small>
                      <p>{item.content}</p>
                    </div>
                  ))}
                </div>
              )}

            <div className="question-box">
              <span className="question-number">CHECK</span>

              <p>
                Can you explain <strong>{nextConcept?.name}</strong> in your
                own words?
              </p>
            </div>

            <button
              type="button"
              className="start-button"
              onClick={onStartQuiz}
              disabled={loadingQuiz}
            >
              {loadingQuiz ? "Preparing Quiz..." : "Continue to Quiz"}
              <span>→</span>
            </button>
          </>
        ) : nextConcept ? (
          <button
            type="button"
            className="start-button"
            onClick={onGenerateLesson}
            disabled={loadingLesson}
          >
            Generate Lesson
            <span>→</span>
          </button>
        ) : null}
      </section>
    </main>
  );
}
