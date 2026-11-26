import { useCallback, useEffect, useState } from "react";
import "./App.css";
import * as api from "./api";
import { useSessionState } from "./hooks/useSessionState";
import Header from "./components/Header";
import Notice from "./components/Notice";
import AuthScreen from "./screens/AuthScreen";
import AdminScreen from "./screens/AdminScreen";
import { clearAuth, loadAuth, saveAuth } from "./authStorage";
import SetupScreen from "./screens/SetupScreen";
import DiagnosticScreen from "./screens/DiagnosticScreen";
import LessonScreen from "./screens/LessonScreen";
import QuizScreen from "./screens/QuizScreen";
import ReteachScreen from "./screens/ReteachScreen";
import ProgressScreen from "./screens/ProgressScreen";
import LibraryScreen from "./screens/LibraryScreen";

// The planner is asked again after an "advance" decision. If the planner
// and the action service ever disagree, that would loop forever, so the
// number of consecutive planner rounds is capped.
const MAX_PLANNER_ROUNDS = 10;

const DIAGNOSTIC_QUESTIONS = 5;

// ============================================================
// SESSION HELPERS
// ============================================================

const STUDENT_KEY = "tutor_student_id";
const SUBJECT_KEY = "tutor_subject_id";

// Removes the saved learning session. Progress itself lives on the
// server, so this only forgets which screen the learner was on.
function clearSavedSession(keep = []) {
  try {
    Object.keys(sessionStorage)
      .filter((key) => key.startsWith("tutor_") && !keep.includes(key))
      .forEach((key) => sessionStorage.removeItem(key));
  } catch {
    // Storage may be unavailable; nothing to clear.
  }
}

// A saved session belongs to one learner. If the backend now reports a
// different one (for example after a database reset), the saved screen
// and question ids would point at data that no longer exists.
function adoptSession(studentId) {
  try {
    const saved = sessionStorage.getItem(STUDENT_KEY);

    if (saved !== null && saved !== String(studentId)) {
      clearSavedSession();
    }

    sessionStorage.setItem(STUDENT_KEY, String(studentId));
  } catch {
    // Ignore storage errors.
  }
}

function describeStatus(screen, health) {
  switch (screen) {
    case "diagnostic":
      return { text: "Diagnostic", state: "ok" };
    case "lesson":
      return { text: "Adaptive Lesson", state: "ok" };
    case "reteach":
      return { text: "Reteaching", state: "ok" };
    case "quiz":
      return { text: "Quiz", state: "ok" };
    case "progress":
      return { text: "Progress", state: "ok" };
    default:
      break;
  }

  if (!health) {
    return { text: "Checking...", state: "warn" };
  }

  if (health.status === "offline") {
    return { text: "Backend offline", state: "error" };
  }

  if (health.status !== "ok") {
    return { text: "Database unavailable", state: "error" };
  }

  if (health.llm !== "available") {
    return { text: "AI model offline", state: "warn" };
  }

  return { text: "AI Tutor Ready", state: "ok" };
}

// ============================================================
// TUTOR (everything after the learner is known)
// ============================================================

function Tutor({
  student,
  onRestart,
  onStudentChange,
  onSignOut,
  initialNotice,
}) {
  const studentId = student.student_id;
  const isStaff = student.role === "instructor" || student.role === "admin";
  const isAdmin = student.role === "admin";

  // ----------------------------------------------------------
  // Backend health
  // ----------------------------------------------------------

  const [health, setHealth] = useState(null);
  const [notice, setNotice] = useState(initialNotice || null);

  useEffect(() => {
    let cancelled = false;

    api
      .getHealth()
      .then((data) => {
        if (!cancelled) setHealth(data);
      })
      .catch(() => {
        if (!cancelled) setHealth({ status: "offline" });
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const showError = (error) => {
    console.error(error);
    setNotice({ type: "error", message: error.message });
  };

  // ----------------------------------------------------------
  // Setup
  // ----------------------------------------------------------

  const [subjects, setSubjects] = useState([]);
  const [loadingSubjects, setLoadingSubjects] = useState(true);
  const [subjectError, setSubjectError] = useState("");
  const [subjectId, setSubjectId] = useSessionState(SUBJECT_KEY, "");
  const [level, setLevel] = useState(student.learning_level);
  const [courseTopic, setCourseTopic] = useState("");
  const [generating, setGenerating] = useState(false);
  const [materialName, setMaterialName] = useState("");
  const [uploading, setUploading] = useState(false);
  const [materialStatus, setMaterialStatus] = useState(null);
  const [starting, setStarting] = useState(false);

  const loadSubjects = useCallback(async () => {
    try {
      setLoadingSubjects(true);
      setSubjectError("");
      setSubjects(await api.getSubjects());
    } catch (error) {
      console.error(error);
      setSubjectError(error.message);
    } finally {
      setLoadingSubjects(false);
    }
  }, []);

  useEffect(() => {
    loadSubjects();
  }, [loadSubjects]);

  // Ignore a saved subject that no longer exists on the server.
  const subjectKnown =
    loadingSubjects ||
    subjects.some((subject) => String(subject.id) === String(subjectId));
  const activeSubjectId = subjectKnown ? subjectId : "";

  // ----------------------------------------------------------
  // Learning flow
  // ----------------------------------------------------------

  const [screen, setScreen] = useSessionState("tutor_screen", "setup");
  const [diagnostic, setDiagnostic] = useSessionState("tutor_diagnostic", null);
  const [questionIndex, setQuestionIndex] = useSessionState(
    "tutor_question_index",
    0
  );
  const [diagnosticComplete, setDiagnosticComplete] = useSessionState(
    "tutor_diagnostic_complete",
    false
  );
  const [nextConcept, setNextConcept] = useSessionState(
    "tutor_next_concept",
    null
  );
  const [lesson, setLesson] = useSessionState("tutor_lesson", null);
  const [reteachData, setReteachData] = useSessionState("tutor_reteach", null);
  const [quiz, setQuiz] = useSessionState("tutor_quiz", null);
  const [quizEvaluation, setQuizEvaluation] = useSessionState(
    "tutor_quiz_evaluation",
    null
  );

  // Make the browser's Back and Forward buttons move between the app's
  // screens instead of leaving the site. Each screen change adds a history
  // entry; going back restores the previous screen.
  useEffect(() => {
    const onPopState = (event) => {
      const target = event.state?.tutorScreen;

      if (target) {
        setScreen(target);
      }
    };

    window.addEventListener("popstate", onPopState);

    return () => window.removeEventListener("popstate", onPopState);
  }, [setScreen]);

  useEffect(() => {
    const current = window.history.state?.tutorScreen;

    if (current === screen) {
      return;
    }

    if (current === undefined) {
      window.history.replaceState({ tutorScreen: screen }, "");
    } else {
      window.history.pushState({ tutorScreen: screen }, "");
    }
  }, [screen]);

  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [quizAnswer, setQuizAnswer] = useState("");
  const [loadingLesson, setLoadingLesson] = useState(false);
  const [loadingReteach, setLoadingReteach] = useState(false);
  const [loadingQuiz, setLoadingQuiz] = useState(false);
  const [evaluatingQuiz, setEvaluatingQuiz] = useState(false);

  // ----------------------------------------------------------
  // Progress
  // ----------------------------------------------------------

  const [masteryData, setMasteryData] = useState([]);
  const [concepts, setConcepts] = useState([]);
  const [studentProfile, setStudentProfile] = useState(null);
  const [loadingProgress, setLoadingProgress] = useState(false);
  const [progressError, setProgressError] = useState("");

  const loadProgress = useCallback(async () => {
    if (!activeSubjectId) {
      return;
    }

    try {
      setLoadingProgress(true);
      setProgressError("");

      const [mastery, conceptList, profile] = await Promise.all([
        api.getMastery(studentId),
        api.getConcepts(Number(activeSubjectId)),
        api.getProfile(student.user_id),
      ]);

      setMasteryData(mastery);
      setConcepts(conceptList);
      setStudentProfile(profile);
    } catch (error) {
      console.error(error);
      setProgressError(error.message);
    } finally {
      setLoadingProgress(false);
    }
  }, [studentId, student.user_id, activeSubjectId]);

  useEffect(() => {
    if (screen === "progress") {
      loadProgress();
    }
  }, [screen, loadProgress]);

  // ----------------------------------------------------------
  // Library ("My learning")
  // ----------------------------------------------------------

  const [library, setLibrary] = useState([]);
  const [loadingLibrary, setLoadingLibrary] = useState(false);
  const [libraryError, setLibraryError] = useState("");

  useEffect(() => {
    if (screen !== "library") {
      return;
    }

    let cancelled = false;

    (async () => {
      try {
        setLoadingLibrary(true);
        setLibraryError("");
        const courses = await api.getLibrary(studentId);

        if (!cancelled) {
          setLibrary(courses);
        }
      } catch (error) {
        console.error(error);

        if (!cancelled) {
          setLibraryError(error.message);
        }
      } finally {
        if (!cancelled) {
          setLoadingLibrary(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [screen, studentId]);

  // ============================================================
  // SETUP ACTIONS
  // ============================================================

  const handleSubjectChange = (value) => {
    setSubjectId(value);
    setMaterialName("");
    setMaterialStatus(null);
  };

  const handleLevelChange = async (nextLevel) => {
    const previous = level;

    setLevel(nextLevel);

    try {
      await api.setLearningLevel(studentId, nextLevel);
      onStudentChange({ ...student, learning_level: nextLevel });
    } catch (error) {
      setLevel(previous);
      showError(error);
    }
  };

  const handleGenerateCourse = async () => {
    const topic = courseTopic.trim();

    if (!topic) {
      return;
    }

    try {
      setGenerating(true);

      const created = isStaff
        ? await api.generateCourse(topic)
        : await api.createCourseFromTopic(topic);

      await loadSubjects();

      handleSubjectChange(String(created.subject_id));
      setCourseTopic("");

      if (isStaff) {
        setNotice({
          type: "success",
          message:
            `Created "${created.subject}" with ${created.concepts_created} ` +
            "concepts. Upload some study material so the tutor has " +
            "something to teach from.",
        });
      } else if (!created.created) {
        setNotice({ type: "success", message: created.message });
      } else {
        setNotice({
          type: created.needs_material ? "error" : "success",
          message:
            `Created "${created.subject}" with ${created.concepts_created} ` +
            `concepts. ${created.message}`,
        });
      }
    } catch (error) {
      showError(error);
    } finally {
      setGenerating(false);
    }
  };

  const handleMaterialUpload = async (file) => {
    if (!activeSubjectId) {
      setMaterialStatus({
        type: "error",
        message: "Select a subject before uploading material.",
      });
      return;
    }

    try {
      setUploading(true);
      setMaterialName(file.name);
      setMaterialStatus({
        type: "info",
        message: "Reading and indexing your material...",
      });

      const result = await api.uploadSubjectMaterial(
        Number(activeSubjectId),
        file
      );

      if (!result.chunks_inserted) {
        throw new Error("No readable text was found in this file.");
      }

      setMaterialStatus({
        type: "success",
        message: `${result.chunks_inserted} knowledge chunks added from ${file.name}.`,
      });
    } catch (error) {
      console.error(error);

      setMaterialStatus({
        type: "error",
        message: `Upload failed: ${error.message}`,
      });
    } finally {
      setUploading(false);
    }
  };

  // ============================================================
  // DIAGNOSTIC
  // ============================================================

  const resetLearningState = () => {
    setDiagnostic(null);
    setQuestionIndex(0);
    setAnswer("");
    setFeedback(null);
    setDiagnosticComplete(false);

    setNextConcept(null);
    setLesson(null);
    setReteachData(null);

    setQuiz(null);
    setQuizAnswer("");
    setQuizEvaluation(null);
  };

  const handleStart = async () => {
    if (!activeSubjectId) {
      setNotice({ type: "error", message: "Please select a subject." });
      return;
    }

    try {
      setStarting(true);

      const data = await api.startDiagnostic(
        studentId,
        Number(activeSubjectId),
        DIAGNOSTIC_QUESTIONS
      );

      resetLearningState();
      setDiagnostic(data);
      setScreen("diagnostic");
    } catch (error) {
      showError(error);
    } finally {
      setStarting(false);
    }
  };

  const handleSkipDiagnostic = async () => {
    if (!activeSubjectId) {
      setNotice({ type: "error", message: "Please select a subject." });
      return;
    }

    resetLearningState();

    // Go straight to the adaptive learning pipeline.
    await continueLearning();
  };

  const handleSubmitAnswer = async () => {
    if (!answer.trim() || !diagnostic) {
      return;
    }

    const currentQuestion = diagnostic.questions[questionIndex];

    try {
      setSubmitting(true);

      setFeedback(
        await api.submitDiagnosticAnswer(
          studentId,
          currentQuestion.question_id,
          answer
        )
      );
    } catch (error) {
      showError(error);
    } finally {
      setSubmitting(false);
    }
  };

  const handleNextQuestion = () => {
    if (!diagnostic) {
      return;
    }

    const nextIndex = questionIndex + 1;

    if (nextIndex >= diagnostic.questions.length) {
      setDiagnosticComplete(true);
      return;
    }

    setQuestionIndex(nextIndex);
    setAnswer("");
    setFeedback(null);
  };

  // ============================================================
  // ADAPTIVE LESSON
  //
  // startReteach and startQuiz take the concept explicitly. They are
  // called from continueLearning in the same tick that the concept is
  // chosen, before React has re-rendered, so reading nextConcept from
  // state there would use the PREVIOUS concept (or null).
  // ============================================================

  const startReteach = async (concept) => {
    if (!concept) {
      setNotice({
        type: "error",
        message: "No active concept is available for reteaching.",
      });
      return;
    }

    try {
      setLoadingReteach(true);

      const data = await api.reteach(studentId, concept.id);

      setNextConcept(concept);
      setReteachData(data);
      setScreen("reteach");
    } catch (error) {
      showError(error);
    } finally {
      setLoadingReteach(false);
    }
  };

  const startQuiz = async (concept) => {
    if (!concept) {
      setNotice({
        type: "error",
        message: "No concept is available for the quiz.",
      });
      return;
    }

    try {
      setLoadingQuiz(true);

      const data = await api.generateQuiz(studentId, concept.id);

      setNextConcept(concept);
      setQuiz(data);
      setQuizAnswer("");
      setQuizEvaluation(null);
      setScreen("quiz");
    } catch (error) {
      showError(error);
    } finally {
      setLoadingQuiz(false);
    }
  };

  // Asks the planner which concept comes next, asks the adaptive engine
  // what to do with it, and opens the matching screen.
  const continueLearning = async (subjectOverride) => {
    // Used as an onClick handler too, so only accept a real id.
    const targetSubjectId =
      typeof subjectOverride === "string" || typeof subjectOverride === "number"
        ? String(subjectOverride)
        : activeSubjectId;

    if (!targetSubjectId) {
      setNotice({ type: "error", message: "Subject information is missing." });
      return;
    }

    try {
      setLoadingLesson(true);

      for (let round = 0; round < MAX_PLANNER_ROUNDS; round++) {
        // Step 1: which concept is next?
        const planned = await api.getNextConcept(
          studentId,
          Number(targetSubjectId)
        );

        // Step 2: nothing left to learn.
        if (planned.status === "complete" || !planned.concept) {
          setNextConcept(null);
          setLesson(null);
          setScreen("lesson");
          return;
        }

        const concept = planned.concept;

        setNextConcept(concept);

        // Step 3: what should happen with it?
        const decision = await api.getNextAction(studentId, concept.id);

        if (decision.action === "reteach") {
          await startReteach(concept);
          return;
        }

        if (decision.action === "practice") {
          await startQuiz(concept);
          return;
        }

        if (decision.action === "advance") {
          // Already mastered. Ask the planner again.
          setNextConcept(null);
          setLesson(null);
          continue;
        }

        // Step 4: teach the concept, or its weakest prerequisite.
        let lessonConcept = concept;

        if (decision.action === "prerequisite") {
          lessonConcept = {
            id: decision.prerequisite_concept_id,
            name: decision.prerequisite_concept,
          };

          setNextConcept(lessonConcept);
        }

        const lessonData = await api.generateLesson(studentId, lessonConcept.id);

        setLesson(lessonData);
        setScreen("lesson");
        return;
      }

      showError(
        new Error(
          "The tutor could not decide what to teach next. " +
            "Use \"Start over\" and try again."
        )
      );
    } catch (error) {
      showError(error);
    } finally {
      setLoadingLesson(false);
    }
  };

  // From "My learning": switch to that course and carry on where the
  // learner left off.
  const continueCourse = async (courseId) => {
    handleSubjectChange(String(courseId));
    await continueLearning(courseId);
  };

  const removeCourse = async (courseId) => {
    try {
      setLibraryError("");
      await api.deleteCourse(courseId);

      setLibrary((previous) =>
        previous.filter((course) => course.subject_id !== courseId)
      );
      setSubjects((previous) =>
        previous.filter((subject) => subject.id !== courseId)
      );

      if (String(courseId) === activeSubjectId) {
        handleSubjectChange("");
      }
    } catch (error) {
      setLibraryError(error.message);
    }
  };

  const showNewTopic = () => {
    setScreen("setup");
  };

  // ============================================================
  // QUIZ
  // ============================================================

  const handleEvaluateQuiz = async () => {
    if (!quiz || !quizAnswer.trim() || !nextConcept) {
      return;
    }

    try {
      setEvaluatingQuiz(true);

      setQuizEvaluation(
        await api.evaluateQuizAnswer({
          studentId,
          questionId: quiz.question_id,
          studentAnswer: quizAnswer,
        })
      );
    } catch (error) {
      showError(error);
    } finally {
      setEvaluatingQuiz(false);
    }
  };

  // The evaluation has already updated mastery on the server, so the
  // next step is chosen from the updated mastery rather than by moving
  // to the next item in a list.
  const handleQuizContinue = async () => {
    if (!quizEvaluation) {
      return;
    }

    const action = quizEvaluation.next_action;

    if (action === "reteach") {
      await startReteach(nextConcept);
      return;
    }

    if (action === "practice") {
      await startQuiz(nextConcept);
      return;
    }

    if (action === "prerequisite" || action === "advance") {
      await continueLearning();
      return;
    }

    // Unknown action: show the learner their progress.
    setScreen("progress");
  };

  // After reteaching, check understanding of the SAME concept with a
  // quiz. Asking the planner again would pick this concept again (its
  // mastery has not changed yet) and show the reteach screen in a loop.
  const handleReteachContinue = async () => {
    setLesson(null);

    await startQuiz(nextConcept);
  };

  // ============================================================
  // RENDER
  // ============================================================

  const status = describeStatus(screen, health);

  let content;

  if (screen === "admin" && isAdmin) {
    content = (
      <AdminScreen
        currentUserId={student.user_id}
        onBack={() => setScreen("setup")}
      />
    );
  } else if (screen === "library") {
    content = (
      <LibraryScreen
        courses={library}
        loading={loadingLibrary}
        error={libraryError}
        loadJournal={(subjectId) => api.getJournal(studentId, subjectId)}
        onContinue={continueCourse}
        onDelete={removeCourse}
        onNewTopic={showNewTopic}
        busy={loadingLesson}
      />
    );
  } else if (screen === "progress") {
    content = (
      <ProgressScreen
        subject={subjects.find(
          (subject) => String(subject.id) === String(activeSubjectId)
        )}
        concepts={concepts}
        masteryData={masteryData}
        studentProfile={studentProfile}
        loading={loadingProgress}
        error={progressError}
        onContinue={continueLearning}
        loadingLesson={loadingLesson}
        onViewLibrary={() => setScreen("library")}
        onNewTopic={showNewTopic}
      />
    );
  } else if (screen === "reteach" && reteachData) {
    content = (
      <ReteachScreen
        reteach={reteachData}
        busy={loadingLesson}
        onContinue={handleReteachContinue}
      />
    );
  } else if (screen === "lesson") {
    content = (
      <LessonScreen
        nextConcept={nextConcept}
        lesson={lesson}
        loadingLesson={loadingLesson}
        loadingQuiz={loadingQuiz}
        loadingProgress={loadingProgress}
        onStartQuiz={() => startQuiz(nextConcept)}
        onGenerateLesson={continueLearning}
        onViewProgress={() => setScreen("progress")}
        onViewLibrary={() => setScreen("library")}
        onNewTopic={showNewTopic}
      />
    );
  } else if (screen === "quiz" && quiz) {
    content = (
      <QuizScreen
        quiz={quiz}
        nextConcept={nextConcept}
        quizAnswer={quizAnswer}
        onAnswerChange={setQuizAnswer}
        evaluation={quizEvaluation}
        evaluating={evaluatingQuiz}
        onSubmit={handleEvaluateQuiz}
        onContinue={handleQuizContinue}
        busy={loadingLesson || loadingReteach || loadingQuiz}
      />
    );
  } else if (screen === "diagnostic" && diagnostic) {
    content = (
      <DiagnosticScreen
        diagnostic={diagnostic}
        questionIndex={questionIndex}
        complete={diagnosticComplete}
        answer={answer}
        onAnswerChange={setAnswer}
        feedback={feedback}
        submitting={submitting}
        onSubmit={handleSubmitAnswer}
        onNext={handleNextQuestion}
        loadingLesson={loadingLesson}
        onStartLearning={continueLearning}
      />
    );
  } else {
    content = (
      <SetupScreen
        ready={true}
        subjects={subjects}
        loadingSubjects={loadingSubjects}
        subjectError={subjectError}
        subjectId={activeSubjectId}
        onSubjectChange={handleSubjectChange}
        level={level}
        onLevelChange={handleLevelChange}
        courseTopic={courseTopic}
        onCourseTopicChange={setCourseTopic}
        onGenerateCourse={handleGenerateCourse}
        generating={generating}
        materialName={materialName}
        uploading={uploading}
        materialStatus={materialStatus}
        onMaterialSelected={handleMaterialUpload}
        onStart={handleStart}
        starting={starting}
        onSkip={handleSkipDiagnostic}
        loadingLesson={loadingLesson}
        isStaff={isStaff}
        canAddMaterial={
          isStaff ||
          Boolean(subjects.find((s) => String(s.id) === String(activeSubjectId))?.is_private)
        }
      />
    );
  }

  return (
    <div className="app">
      <Header
        status={status.text}
        statusState={status.state}
        profileName={student.username}
        role={student.role}
        onSignOut={onSignOut}
        onShowAdmin={
          isAdmin && screen !== "admin" ? () => setScreen("admin") : undefined
        }
        onShowLibrary={
          screen !== "library" && screen !== "admin"
            ? () => setScreen("library")
            : undefined
        }
        onShowProgress={
          activeSubjectId && screen !== "progress" && screen !== "admin"
            ? () => setScreen("progress")
            : undefined
        }
        onRestart={screen !== "setup" ? onRestart : undefined}
      />

      <Notice notice={notice} onDismiss={() => setNotice(null)} />

      {content}
    </div>
  );
}

// ============================================================
// APP (signs the user in, then hands over to Tutor)
// ============================================================

function App() {
  const [auth, setAuth] = useState(loadAuth);
  const [student, setStudent] = useState(null);
  const [welcome, setWelcome] = useState(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [session, setSession] = useState(0);

  const token = auth?.token;

  const resetToSignIn = useCallback(() => {
    clearSavedSession();
    clearAuth();

    setWelcome(null);
    setError("");
    setStudent(null);
    setAuth(null);
    setSession((value) => value + 1);
  }, []);

  // The server rejected the saved token (expired, or the account was
  // removed or deactivated): go back to the sign-in form.
  useEffect(() => {
    const onUnauthorized = () => {
      resetToSignIn();
    };

    window.addEventListener(api.UNAUTHORIZED_EVENT, onUnauthorized);

    return () =>
      window.removeEventListener(api.UNAUTHORIZED_EVENT, onUnauthorized);
  }, [resetToSignIn]);

  // Load the learner behind the token (also after a page refresh).
  useEffect(() => {
    if (!token) {
      return undefined;
    }

    let cancelled = false;

    api
      .getMe()
      .then((data) => {
        if (cancelled) return;

        adoptSession(data.student_id);
        setStudent(data);
      })
      .catch((err) => {
        // A 401 is handled by the unauthorized listener above.
        if (!cancelled && err.status !== 401) setError(err.message);
      });

    return () => {
      cancelled = true;
    };
  }, [token, attempt]);

  // Errors are thrown so the form can show them next to the fields.
  const completeSignIn = (data, message) => {
    const next = { token: data.access_token, user: data.user };

    saveAuth(next);
    setStudent(null);
    setError("");
    setWelcome({ type: "success", message });
    setAuth(next);
  };

  const signIn = async (username, password) => {
    const data = await api.login(username, password);

    completeSignIn(data, `Welcome back, ${data.user.username}.`);
  };

  const register = async (username, password) => {
    const data = await api.register(username, password);

    completeSignIn(data, `Account created. Welcome, ${data.user.username}.`);
  };

  const retry = () => {
    setError("");
    setAttempt((value) => value + 1);
  };

  // Forget the current screen but keep the chosen subject. Mounting a new
  // Tutor (via its key) resets every piece of learning state at once.
  const restart = () => {
    clearSavedSession([STUDENT_KEY, SUBJECT_KEY]);
    setSession((value) => value + 1);
  };

  if (!token) {
    return (
      <div className="app">
        <Header status="Sign in" statusState="warn" />

        <AuthScreen onSignIn={signIn} onRegister={register} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="app">
        <Header status="Backend offline" statusState="error" />

        <main className="main-content">
          <section className="setup-card">
            <div className="card-header">
              <div>
                <h3>Can't reach the tutor backend</h3>
                <p>{error}</p>
              </div>
            </div>

            <p className="hint">
              Start the backend from the <code>backend</code> folder with{" "}
              <code>uvicorn app.main:app --port 8000</code>, and make sure
              PostgreSQL is running.
            </p>

            <button
              type="button"
              className="start-button"
              onClick={retry}
              style={{ marginTop: "20px" }}
            >
              Try again
              <span>→</span>
            </button>

            <button
              type="button"
              className="skip-diagnostic-button"
              onClick={resetToSignIn}
            >
              Sign out
            </button>
          </section>
        </main>
      </div>
    );
  }

  if (!student) {
    return (
      <div className="app">
        <Header status="Connecting..." statusState="warn" />

        <main className="main-content">
          <div className="loading-message">Opening your account...</div>
        </main>
      </div>
    );
  }

  return (
    <Tutor
      key={session}
      student={student}
      initialNotice={welcome}
      onRestart={restart}
      onStudentChange={setStudent}
      onSignOut={resetToSignIn}
    />
  );
}

export default App;
