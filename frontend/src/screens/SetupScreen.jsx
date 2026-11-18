const LEVELS = [
  { value: "beginner", icon: "🌱", title: "Beginner", hint: "I'm starting from scratch" },
  { value: "intermediate", icon: "📈", title: "Intermediate", hint: "I know the basics" },
  { value: "advanced", icon: "🚀", title: "Advanced", hint: "I want deeper understanding" },
];

export default function SetupScreen({
  ready,
  subjects,
  loadingSubjects,
  subjectError,
  subjectId,
  onSubjectChange,
  level,
  onLevelChange,
  courseTopic,
  onCourseTopicChange,
  onGenerateCourse,
  generating,
  materialName,
  uploading,
  materialStatus,
  onMaterialSelected,
  onStart,
  starting,
  onSkip,
  loadingLesson,
}) {
  const subjectUnavailable =
    !ready || loadingSubjects || !!subjectError || !subjectId;

  return (
    <main className="main-content">
      <section className="hero">
        <div className="hero-badge">PERSONALIZED LEARNING</div>

        <h2>
          Learn anything.
          <br />
          <span>Your tutor adapts to you.</span>
        </h2>

        <p>
          Pick a course or create one on any topic, then add your own study
          material. The tutor assesses your knowledge and adapts the learning
          path based on your progress.
        </p>
      </section>

      <section className="setup-card">
        <div className="card-header">
          <div>
            <h3>Start Learning</h3>
            <p>Tell us how you'd like to learn.</p>
          </div>

          <div className="step-number">01</div>
        </div>

        <div className="form-section">
          <label htmlFor="subject">What do you want to learn?</label>

          {loadingSubjects ? (
            <div className="loading-message">Loading subjects...</div>
          ) : subjectError ? (
            <div className="error-message">{subjectError}</div>
          ) : (
            <select
              id="subject"
              value={subjectId}
              onChange={(event) => onSubjectChange(event.target.value)}
            >
              <option value="">
                {subjects.length === 0
                  ? "No courses yet — create one below"
                  : "Select a subject"}
              </option>

              {subjects.map((subject) => (
                <option key={subject.id} value={subject.id}>
                  {subject.name}
                </option>
              ))}
            </select>
          )}
        </div>

        <div className="form-section">
          <label htmlFor="course-topic">Or create a new course</label>

          <form
            className="inline-form"
            onSubmit={(event) => {
              event.preventDefault();
              onGenerateCourse();
            }}
          >
            <input
              id="course-topic"
              type="text"
              maxLength={100}
              placeholder="e.g. Operating Systems"
              value={courseTopic}
              onChange={(event) => onCourseTopicChange(event.target.value)}
              disabled={generating || !ready}
            />

            <button
              type="submit"
              className="secondary-button"
              disabled={!courseTopic.trim() || generating || !ready}
            >
              {generating ? "Generating..." : "Generate course"}
            </button>
          </form>

          {generating && (
            <p className="hint">
              Building your course with the AI model. This can take a minute.
            </p>
          )}
        </div>

        <div className="form-section">
          <label>What's your current level?</label>

          <div className="level-options">
            {LEVELS.map((item) => (
              <button
                key={item.value}
                type="button"
                className={`level-card ${level === item.value ? "selected" : ""}`}
                onClick={() => onLevelChange(item.value)}
                disabled={!ready}
              >
                <span className="level-icon">{item.icon}</span>

                <span>
                  <strong>{item.title}</strong>
                  <small>{item.hint}</small>
                </span>
              </button>
            ))}
          </div>
        </div>

        <div className="divider">
          <span>STUDY MATERIAL</span>
        </div>

        <div className="form-section">
          <label>Learn from your own material</label>

          <label className={`upload-area ${subjectUnavailable ? "disabled" : ""}`}>
            <input
              type="file"
              accept=".pdf,.txt,.md,.markdown"
              disabled={uploading || subjectUnavailable}
              onChange={(event) => {
                const file = event.target.files[0] || null;

                // Allow choosing the same file again later.
                event.target.value = "";

                if (file) {
                  onMaterialSelected(file);
                }
              }}
            />

            <span className="upload-icon">📄</span>

            <span className="upload-title">
              {uploading
                ? "Adding material..."
                : materialName || "Upload your study material"}
            </span>

            <span className="upload-description">
              {subjectUnavailable
                ? "Select a subject first"
                : "PDF, TXT or Markdown • Added to the selected subject"}
            </span>
          </label>

          {materialStatus && (
            <p className={`upload-status upload-status-${materialStatus.type}`}>
              {materialStatus.message}
            </p>
          )}

          <p className="hint">
            The tutor only teaches from study material. A course you create
            needs some before the diagnostic and lessons can start.
          </p>
        </div>

        <button
          type="button"
          className="start-button"
          onClick={onStart}
          disabled={subjectUnavailable || starting}
        >
          {starting ? "Starting..." : "Start Learning"}
          <span>→</span>
        </button>

        <button
          type="button"
          className="skip-diagnostic-button"
          onClick={onSkip}
          disabled={subjectUnavailable || loadingLesson}
        >
          {loadingLesson
            ? "Preparing..."
            : "Skip Diagnostic — Test Adaptive Learning"}
        </button>

        <p className="privacy-note">
          Your material will be used to create a personalized learning
          experience.
        </p>
      </section>

      <section className="features">
        <div className="feature">
          <span>🎯</span>
          <div>
            <strong>Adaptive</strong>
            <p>Learning adjusts to your mastery.</p>
          </div>
        </div>

        <div className="feature">
          <span>🧠</span>
          <div>
            <strong>Personalized</strong>
            <p>Identifies gaps and misconceptions.</p>
          </div>
        </div>

        <div className="feature">
          <span>📚</span>
          <div>
            <strong>Grounded</strong>
            <p>Learn from trusted study material.</p>
          </div>
        </div>
      </section>
    </main>
  );
}
