export default function DiagnosticScreen({
  diagnostic,
  questionIndex,
  complete,
  answer,
  onAnswerChange,
  feedback,
  submitting,
  onSubmit,
  onNext,
  loadingLesson,
  onStartLearning,
}) {
  // ----------------------------------------------------------
  // DIAGNOSTIC COMPLETE
  // ----------------------------------------------------------

  if (complete) {
    return (
      <main className="main-content">
        <section className="diagnostic-card completion-card">
          <div className="completion-icon">✓</div>

          <div className="hero-badge">DIAGNOSTIC COMPLETE</div>

          <h2>
            Great job.
            <br />
            <span>Your learning path is ready.</span>
          </h2>

          <p>
            Your answers have been evaluated. The tutor can now adapt the
            learning experience to your current understanding.
          </p>

          <button
            type="button"
            className="start-button"
            onClick={onStartLearning}
            disabled={loadingLesson}
          >
            {loadingLesson ? "Preparing Your Lesson..." : "Start Learning"}
            <span>→</span>
          </button>
        </section>
      </main>
    );
  }

  // ----------------------------------------------------------
  // DIAGNOSTIC QUESTION
  // ----------------------------------------------------------

  const totalQuestions = diagnostic.questions.length;
  const currentQuestion = diagnostic.questions[questionIndex];

  if (!currentQuestion) {
    return (
      <main className="main-content">
        <section className="diagnostic-card">
          <p>
            This diagnostic session is no longer available. Use "Start over"
            to begin a new one.
          </p>
        </section>
      </main>
    );
  }

  const questionNumber = questionIndex + 1;
  const progress = (questionNumber / totalQuestions) * 100;

  return (
    <main className="main-content">
      <section className="diagnostic-card">
        <div className="diagnostic-top">
          <div>
            <div className="hero-badge">KNOWLEDGE CHECK</div>

            <h2 className="diagnostic-title">
              Let's understand
              <br />
              <span>what you already know.</span>
            </h2>
          </div>

          <div className="question-counter">
            <strong>{questionNumber}</strong>
            <span>/ {totalQuestions}</span>
          </div>
        </div>

        <div className="progress-track">
          <div className="progress-fill" style={{ width: `${progress}%` }}></div>
        </div>

        <div className="concept-label">CONCEPT</div>

        <h3 className="question-concept">{currentQuestion.concept}</h3>

        <div className="question-box">
          <span className="question-number">Q{questionNumber}</span>
          <p>{currentQuestion.question}</p>
        </div>

        {!feedback ? (
          <>
            <label className="answer-label" htmlFor="answer">
              Your answer
            </label>

            <textarea
              id="answer"
              className="answer-input"
              value={answer}
              onChange={(event) => onAnswerChange(event.target.value)}
              placeholder="Explain your answer in your own words..."
              rows={6}
            />

            <button
              type="button"
              className="start-button"
              onClick={onSubmit}
              disabled={!answer.trim() || submitting}
            >
              {submitting ? "Evaluating..." : "Submit Answer"}
              <span>→</span>
            </button>
          </>
        ) : (
          <div className="feedback-section">
            <div
              className={`feedback-result ${
                feedback.result === "correct" ? "correct" : "incorrect"
              }`}
            >
              <strong>
                {feedback.result === "correct"
                  ? "Good understanding"
                  : "Let's work on this"}
              </strong>

              <span>Score: {Math.round(feedback.score * 100)}%</span>
            </div>

            <div className="feedback-box">
              <strong>Feedback</strong>
              <p>{feedback.feedback}</p>
            </div>

            {feedback.misconception && (
              <div className="misconception-box">
                <strong>What to improve</strong>
                <p>{feedback.misconception}</p>
              </div>
            )}

            <button type="button" className="start-button" onClick={onNext}>
              {questionNumber === totalQuestions
                ? "Finish Diagnostic"
                : "Next Question"}
              <span>→</span>
            </button>
          </div>
        )}
      </section>
    </main>
  );
}
