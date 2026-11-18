const CONTINUE_LABELS = {
  reteach: "Reteach This Concept",
  practice: "Practice Again",
  prerequisite: "Learn Prerequisite",
  advance: "Continue to Next Concept",
};

export default function QuizScreen({
  quiz,
  nextConcept,
  quizAnswer,
  onAnswerChange,
  evaluation,
  evaluating,
  onSubmit,
  onContinue,
  busy,
}) {
  return (
    <main className="main-content">
      <section className="diagnostic-card">
        <div className="hero-badge">KNOWLEDGE CHECK</div>

        <h2 className="diagnostic-title">
          Let's see what
          <br />
          <span>you've learned.</span>
        </h2>

        <div className="concept-label">CONCEPT</div>

        <h3 className="question-concept">{nextConcept?.name}</h3>

        <div className="question-box">
          <span className="question-number">QUIZ</span>
          <p>{quiz.question}</p>
        </div>

        {!evaluation ? (
          <>
            <label className="answer-label" htmlFor="quiz-answer">
              Your answer
            </label>

            <textarea
              id="quiz-answer"
              className="answer-input"
              value={quizAnswer}
              onChange={(event) => onAnswerChange(event.target.value)}
              placeholder="Explain your answer in your own words..."
              rows={6}
            />

            <button
              type="button"
              className="start-button"
              onClick={onSubmit}
              disabled={!quizAnswer.trim() || evaluating}
            >
              {evaluating ? "Evaluating..." : "Submit Quiz"}
              <span>→</span>
            </button>
          </>
        ) : (
          <div className="feedback-section">
            <div
              className={`feedback-result ${
                evaluation.result === "correct" ? "correct" : "incorrect"
              }`}
            >
              <strong>
                {evaluation.result === "correct"
                  ? "Excellent!"
                  : "Let's strengthen this concept"}
              </strong>

              <span>Score: {Math.round(evaluation.score * 100)}%</span>
            </div>

            <div className="feedback-box">
              <strong>Feedback</strong>
              <p>{evaluation.feedback}</p>
            </div>

            {evaluation.misconception && (
              <div className="misconception-box">
                <strong>What to improve</strong>
                <p>{evaluation.misconception}</p>
              </div>
            )}

            <div className="question-box">
              <span className="question-number">MASTERY</span>

              <p>
                Current mastery:{" "}
                <strong>{Math.round(evaluation.mastery_score * 100)}%</strong>
              </p>
            </div>

            {evaluation.next_action && (
              <div className="feedback-box">
                <strong>Tutor decision</strong>
                <p>{evaluation.next_action}</p>

                {evaluation.reason && <small>{evaluation.reason}</small>}
              </div>
            )}

            <button
              type="button"
              className="start-button"
              onClick={onContinue}
              disabled={busy}
            >
              {busy
                ? "Loading..."
                : CONTINUE_LABELS[evaluation.next_action] || "Continue"}
              <span>→</span>
            </button>
          </div>
        )}
      </section>
    </main>
  );
}
