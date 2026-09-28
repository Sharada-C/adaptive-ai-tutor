import { useEffect, useState } from "react";
import "./App.css";
import * as pdfjsLib from "pdfjs-dist";


pdfjsLib.GlobalWorkerOptions.workerSrc =
  new URL(
    "pdfjs-dist/build/pdf.worker.min.mjs",
    import.meta.url
  ).toString();

const API_BASE_URL = "http://127.0.0.1:8000";
const STUDENT_ID = 1;

// ============================================================
// SESSION STORAGE HELPERS
// ============================================================

function loadSession(key, fallback) {
  try {
    const value = sessionStorage.getItem(key);

    if (value === null) {
      return fallback;
    }

    return JSON.parse(value);
  } catch {
    return fallback;
  }
}

function saveSession(key, value) {
  try {
    sessionStorage.setItem(
      key,
      JSON.stringify(value)
    );
  } catch {
    // Ignore storage errors.
  }
}

// ============================================================
// FILE TEXT EXTRACTION
// ============================================================

async function extractTextFromFile(file) {
  if (!file) {
    throw new Error("No file selected.");
  }

  // TXT
  if (file.type === "text/plain" || file.name.toLowerCase().endsWith(".txt")) {
    const text = await file.text();

    if (!text.trim()) {
      throw new Error("The selected text file is empty.");
    }

    return text;
  }

  // PDF
  if (
    file.type === "application/pdf" ||
    file.name.toLowerCase().endsWith(".pdf")
  ) {
    const arrayBuffer = await file.arrayBuffer();

    const pdf = await pdfjsLib.getDocument({
      data: arrayBuffer,
    }).promise;

    const pages = [];

    for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber++) {
      const page = await pdf.getPage(pageNumber);

      const content = await page.getTextContent();

      const pageText = content.items
        .map((item) => item.str)
        .join(" ")
        .trim();

      if (pageText) {
        pages.push(pageText);
      }
    }

    const text = pages.join("\n\n").trim();

    if (!text) {
      throw new Error(
        "No readable text was found in this PDF. Scanned/image-only PDFs are not supported yet."
      );
    }

    return text;
  }

  throw new Error(
    "Unsupported file type. Please upload a PDF or TXT file."
  );
}

// ============================================================
// APP
// ============================================================

function App() {
  // ============================================================
  // SETUP
  // ============================================================

  const [subjects, setSubjects] = useState([]);
  const [subjectId, setSubjectId] = useState(
    () => loadSession("tutor_subject_id", "")
  );

  const [level, setLevel] = useState(
    () => loadSession("tutor_level", "beginner")
  );

  const [material, setMaterial] = useState(null);
  const [uploadingMaterial, setUploadingMaterial] = useState(false);
  const [materialStatus, setMaterialStatus] = useState("");
  // ============================================================
  // INGEST STUDY MATERIAL
  // ============================================================

  const handleMaterialUpload = async (file) => {
    if (!file) {
      return;
    }

    if (!conceptId) {
      setMaterialStatus(
        "Please select a concept before uploading material."
      );
      return;
    }

    try {
      setUploadingMaterial(true);
      setMaterialStatus("Reading your material...");

      // Extract text from PDF or TXT.
      const text = await extractTextFromFile(file);

      if (!text.trim()) {
        throw new Error(
          "No readable text was found in the selected file."
        );
      }

      setMaterialStatus(
        "Adding material to the tutor..."
      );

      // Send extracted text to the existing
      // knowledge ingestion endpoint.
      const response = await fetch(
        `${API_BASE_URL}/knowledge/ingest`,
        {
          method: "POST",

          headers: {
            "Content-Type": "application/json",
          },

          body: JSON.stringify({
            concept_id: Number(conceptId),
            text: text,
            source: file.name,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
          "Unable to ingest the study material."
        );
      }

      console.log(
        "Material ingestion successful:",
        data
      );

      setMaterialStatus(
        `${data.chunks_inserted} knowledge chunks added successfully.`
      );
    } catch (error) {
      console.error(
        "Material upload failed:",
        error
      );

      setMaterialStatus(
        `Upload failed: ${error.message}`
      );
    } finally {
      setUploadingMaterial(false);
    }
  };
  const [conceptId, setConceptId] = useState("");
  const [loadingConcepts, setLoadingConcepts] = useState(false);

  const [loadingSubjects, setLoadingSubjects] =
    useState(true);

  const [subjectError, setSubjectError] =
    useState("");

  const [starting, setStarting] =
    useState(false);

  // ============================================================
  // SCREEN
  // ============================================================

  const [screen, setScreen] = useState(
    () => loadSession("tutor_screen", "setup")
  );

  // ============================================================
  // DIAGNOSTIC
  // ============================================================

  const [diagnostic, setDiagnostic] =
    useState(() =>
      loadSession("tutor_diagnostic", null)
    );

  const [currentQuestionIndex, setCurrentQuestionIndex] =
    useState(() =>
      loadSession(
        "tutor_question_index",
        0
      )
    );

  const [answer, setAnswer] =
    useState("");

  const [feedback, setFeedback] =
    useState(null);

  const [submitting, setSubmitting] =
    useState(false);

  const [diagnosticComplete, setDiagnosticComplete] =
    useState(() =>
      loadSession(
        "tutor_diagnostic_complete",
        false
      )
    );

  // ============================================================
  // ADAPTIVE LESSON
  // ============================================================

  const [nextConcept, setNextConcept] =
    useState(() =>
      loadSession(
        "tutor_next_concept",
        null
      )
    );

  const [lesson, setLesson] =
    useState(() =>
      loadSession(
        "tutor_lesson",
        null
      )
    );

  const [reteach, setReteach] = useState(
    () => loadSession("tutor_reteach", null)
  );
  const [loadingReteach, setLoadingReteach] = useState(false);

  const [loadingLesson, setLoadingLesson] =
    useState(false);

  // ============================================================
  // PROGRESS DASHBOARD
  // ============================================================

  const [masteryData, setMasteryData] = useState([]);
  const [concepts, setConcepts] = useState([]);
  const [studentProfile, setStudentProfile] = useState(null);

  const [loadingProgress, setLoadingProgress] = useState(false);
  const [progressError, setProgressError] = useState("");

  // ============================================================
  // QUIZ
  // ============================================================

  const [quiz, setQuiz] =
    useState(() =>
      loadSession("tutor_quiz", null)
    );

  const [quizAnswer, setQuizAnswer] =
    useState("");

  const [quizEvaluation, setQuizEvaluation] =
    useState(() =>
      loadSession(
        "tutor_quiz_evaluation",
        null
      )
    );

  const [loadingQuiz, setLoadingQuiz] =
    useState(false);

  const [evaluatingQuiz, setEvaluatingQuiz] =
    useState(false);

  // ============================================================
  // PERSIST SESSION STATE
  // ============================================================

  useEffect(() => {
    saveSession(
      "tutor_screen",
      screen
    );
  }, [screen]);

  useEffect(() => {
    saveSession(
      "tutor_subject_id",
      subjectId
    );
  }, [subjectId]);

  useEffect(() => {
    saveSession(
      "tutor_level",
      level
    );
  }, [level]);

  useEffect(() => {
    saveSession(
      "tutor_diagnostic",
      diagnostic
    );
  }, [diagnostic]);

  useEffect(() => {
    saveSession(
      "tutor_question_index",
      currentQuestionIndex
    );
  }, [currentQuestionIndex]);

  useEffect(() => {
    saveSession(
      "tutor_diagnostic_complete",
      diagnosticComplete
    );
  }, [diagnosticComplete]);

  useEffect(() => {
    saveSession(
      "tutor_next_concept",
      nextConcept
    );
  }, [nextConcept]);

  useEffect(() => {
    saveSession(
      "tutor_lesson",
      lesson
    );
  }, [lesson]);

  useEffect(() => {
    saveSession("tutor_reteach", reteach);
  }, [reteach]);

  useEffect(() => {
    saveSession(
      "tutor_quiz",
      quiz
    );
  }, [quiz]);

  useEffect(() => {
    saveSession(
      "tutor_quiz_evaluation",
      quizEvaluation
    );
  }, [quizEvaluation]);

  // ============================================================
  // LOAD SUBJECTS
  // ============================================================

  useEffect(() => {
    async function loadSubjects() {
      try {
        setLoadingSubjects(true);
        setSubjectError("");

        const response = await fetch(
          `${API_BASE_URL}/subjects`
        );

        if (!response.ok) {
          throw new Error(
            "Unable to load subjects."
          );
        }

        const data =
          await response.json();

        setSubjects(data);
      } catch (error) {
        console.error(error);

        setSubjectError(
          "Could not connect to the tutor backend."
        );
      } finally {
        setLoadingSubjects(false);
      }
    }

    loadSubjects();
  }, []);

  // ============================================================
// LOAD CONCEPTS FOR SELECTED SUBJECT
// ============================================================

useEffect(() => {
  if (!subjectId) {
    setConcepts([]);
    setConceptId("");
    return;
  }

  async function loadConcepts() {
    try {
      setLoadingConcepts(true);

      const response = await fetch(
        `${API_BASE_URL}/subjects/${Number(subjectId)}/concepts`
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
            "Unable to load concepts."
        );
      }

      const conceptList = Array.isArray(data)
        ? data
        : [data];

      setConcepts(conceptList);

      // Automatically select the first concept.
      if (conceptList.length > 0) {
        setConceptId(
          String(conceptList[0].id)
        );
      } else {
        setConceptId("");
      }
    } catch (error) {
      console.error(error);
      setConcepts([]);
      setConceptId("");
    } finally {
      setLoadingConcepts(false);
    }
  }

  loadConcepts();
}, [subjectId]);

  // ============================================================
  // START DIAGNOSTIC
  // ============================================================

  const handleStart = async () => {
    if (!subjectId) {
      alert(
        "Please select a subject."
      );
      return;
    }

    try {
      setStarting(true);

      const response =
        await fetch(
          `${API_BASE_URL}/tutor/diagnostic/start`,
          {
            method: "POST",

            headers: {
              "Content-Type":
                "application/json",
            },

            body: JSON.stringify({
              student_id:
                STUDENT_ID,

              subject_id:
                Number(subjectId),

              limit: 5,
            }),
          }
        );

      const data =
        await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
            "Unable to start diagnostic."
        );
      }

      console.log(
        "Diagnostic started:",
        data
      );

      setDiagnostic(data);

      setCurrentQuestionIndex(0);

      setAnswer("");

      setFeedback(null);

      setDiagnosticComplete(
        false
      );

      setNextConcept(null);

      setLesson(null);

      setQuiz(null);

      setQuizAnswer("");

      setQuizEvaluation(null);

      setScreen(
        "diagnostic"
      );
    } catch (error) {
      console.error(error);

      alert(error.message);
    } finally {
      setStarting(false);
    }
  };
  // ============================================================
  // SKIP DIAGNOSTIC
  // ============================================================

  const handleSkipDiagnostic = async () => {
    if (!subjectId) {
      alert("Please select a subject.");
      return;
    }

    // Clear any previous temporary session state.
    setDiagnostic(null);
    setCurrentQuestionIndex(0);
    setAnswer("");
    setFeedback(null);
    setDiagnosticComplete(false);

    setNextConcept(null);
    setLesson(null);

    setQuiz(null);
    setQuizAnswer("");
    setQuizEvaluation(null);

    // Directly enter the adaptive learning pipeline.
    await handleContinueLearning();
  };
  // ============================================================
  // SUBMIT DIAGNOSTIC ANSWER
  // ============================================================

  const handleSubmitAnswer =
    async () => {
      if (
        !answer.trim() ||
        !diagnostic
      ) {
        return;
      }

      const currentQuestion =
        diagnostic.questions[
          currentQuestionIndex
        ];

      try {
        setSubmitting(true);

        const response =
          await fetch(
            `${API_BASE_URL}/tutor/diagnostic/submit`,
            {
              method: "POST",

              headers: {
                "Content-Type":
                  "application/json",
              },

              body: JSON.stringify({
                student_id:
                  STUDENT_ID,

                question_id:
                  currentQuestion.question_id,

                student_answer:
                  answer,
              }),
            }
          );

        const data =
          await response.json();

        if (!response.ok) {
          throw new Error(
            data.detail ||
              "Unable to submit answer."
          );
        }

        console.log(
          "Diagnostic answer evaluated:",
          data
        );

        setFeedback(data);
      } catch (error) {
        console.error(error);

        alert(error.message);
      } finally {
        setSubmitting(false);
      }
    };

  // ============================================================
  // NEXT DIAGNOSTIC QUESTION
  // ============================================================

  const handleNextQuestion =
    () => {
      if (!diagnostic) {
        return;
      }

      const nextIndex =
        currentQuestionIndex + 1;

      if (
        nextIndex >=
        diagnostic.questions.length
      ) {
        setDiagnosticComplete(
          true
        );

        return;
      }

      setCurrentQuestionIndex(
        nextIndex
      );

      setAnswer("");

      setFeedback(null);
    };

  // ============================================================
  // GET NEXT CONCEPT + GENERATE LESSON
  // ============================================================

  const handleContinueLearning =
    async () => {
      if (!subjectId) {
        alert(
          "Subject information is missing."
        );

        return;
      }

      try {
        setLoadingLesson(true);


        // ------------------------------------------------------
        // STEP 1: Ask adaptive planner
        // ------------------------------------------------------

        const plannerResponse =
          await fetch(
            `${API_BASE_URL}/students/${STUDENT_ID}/subjects/${Number(
              subjectId
            )}/next`
          );

        const plannerData =
          await plannerResponse.json();

        if (!plannerResponse.ok) {
          throw new Error(
            plannerData.detail ||
              "Unable to determine the next concept."
          );
        }

        console.log(
          "Planner response:",
          plannerData
        );

        // ------------------------------------------------------
        // STEP 2: No concepts remaining
        // ------------------------------------------------------

        if (
          plannerData.status ===
            "complete" ||
          !plannerData.concept
        ) {
          setNextConcept(null);

          setLesson(null);

          setScreen("lesson");

          return;
        }

        // ------------------------------------------------------
        // STEP 3: Store selected concept
        // ------------------------------------------------------

        const concept =
          plannerData.concept;

        console.log(
          "Adaptive concept selected:",
          concept
        );

        setNextConcept(
          concept
        );

        // ------------------------------------------------------
        // STEP 4: Generate lesson
        // ------------------------------------------------------

        const lessonResponse =
          await fetch(
            `${API_BASE_URL}/tutor/lesson`,
            {
              method: "POST",

              headers: {
                "Content-Type":
                  "application/json",
              },

              body: JSON.stringify({
                student_id:
                  STUDENT_ID,

                concept_id:
                  concept.id,
              }),
            }
          );

        const lessonData =
          await lessonResponse.json();

        if (!lessonResponse.ok) {
          throw new Error(
            lessonData.detail ||
              "Unable to generate the lesson."
          );
        }

        console.log(
          "Lesson generated:",
          lessonData
        );

        setLesson(
          lessonData
        );

        // ------------------------------------------------------
        // STEP 5: Explicitly navigate to lesson
        // ------------------------------------------------------

        setScreen("lesson");
      } catch (error) {
        console.error(error);

        alert(error.message);
      } finally {
        setLoadingLesson(false);
      }
    };



  const handleStartReteach = async () => {
    console.log("RETEACH BUTTON CLICKED");

    if (!nextConcept) {
      alert("No active concept is available for reteaching.");
    }

    
    try {
      setLoadingReteach(true);

      const response = await fetch(`${API_BASE_URL}/tutor/reteach`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          student_id: STUDENT_ID,
          concept_id: nextConcept.id,
        }),
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to generate reteaching."
        );  
      }

      console.log("RETEACH RESPONSE:", data);
      setReteach(data);
      setScreen("reteach");
    } catch (error) {
      console.error("Reteach failed:", error);
      alert(error.message);
    } finally {
      setLoadingReteach(false);
    }
  };
  // ============================================================
// LOAD PROGRESS
// ============================================================

const loadProgress = async () => {
  if (!subjectId) {
    alert("Subject information is missing.");
    return;
  }

  try {
    setLoadingProgress(true);
    setProgressError("");

    const [masteryResponse, conceptsResponse] =
      await Promise.all([
        fetch(
          `${API_BASE_URL}/students/${STUDENT_ID}/mastery`
        ),
        fetch(
          `${API_BASE_URL}/subjects/${Number(subjectId)}/concepts`
        ),
      ]);

    const masteryDataResponse =
      await masteryResponse.json();

    const conceptsDataResponse =
      await conceptsResponse.json();

    if (!masteryResponse.ok) {
      throw new Error(
        masteryDataResponse.detail ||
          "Unable to load mastery data."
      );
    }

    if (!conceptsResponse.ok) {
      throw new Error(
        conceptsDataResponse.detail ||
          "Unable to load concepts."
      );
    }

    setMasteryData(masteryDataResponse);

    // The API normally returns an array.
    // Keep this defensive so the UI doesn't crash
    // if only one concept is returned.
    setConcepts(
      Array.isArray(conceptsDataResponse)
        ? conceptsDataResponse
        : [conceptsDataResponse]
    );
  } catch (error) {
    console.error(error);
    setProgressError(error.message);
  } finally {
    setLoadingProgress(false);
  }
};
 
const loadStudentProfile = async () => {
  try {
    const response = await fetch(
      `${API_BASE_URL}/students/${STUDENT_ID}/profile`
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail || "Unable to load student profile."
      );
    }

    setStudentProfile(data);
  } catch (error) {
    console.error("Failed to load student profile:", error);
  }
};

  useEffect(() => {
    loadStudentProfile();
  }, []);
  // ============================================================
  // START QUIZ
  // ============================================================

  const handleStartQuiz =
    async () => {
      if (!nextConcept) {
        alert(
          "No concept is available for the quiz."
        );

        return;
      }

      try {
        setLoadingQuiz(true);

        const response =
          await fetch(
            `${API_BASE_URL}/tutor/quiz`,
            {
              method: "POST",

              headers: {
                "Content-Type":
                  "application/json",
              },

              body: JSON.stringify({
                student_id:
                  STUDENT_ID,

                concept_id:
                  nextConcept.id,
              }),
            }
          );

        const data =
          await response.json();

        if (!response.ok) {
          throw new Error(
            data.detail ||
              "Unable to generate quiz."
          );
        }

        console.log(
          "Quiz generated:",
          data
        );

        setQuiz(data);

        setQuizAnswer("");

        setQuizEvaluation(
          null
        );

        setScreen("quiz");
      } catch (error) {
        console.error(error);

        alert(error.message);
      } finally {
        setLoadingQuiz(false);
      }
    };

  // ============================================================
  // EVALUATE QUIZ
  // ============================================================

  const handleEvaluateQuiz =
    async () => {
      if (
        !quiz ||
        !quizAnswer.trim() ||
        !nextConcept
      ) {
        return;
      }

      try {
        setEvaluatingQuiz(
          true
        );

        const response =
          await fetch(
            `${API_BASE_URL}/tutor/evaluate`,
            {
              method: "POST",

              headers: {
                "Content-Type":
                  "application/json",
              },

              body: JSON.stringify({
                student_id:
                  STUDENT_ID,

                concept_id:
                  nextConcept.id,

                question:
                  quiz.question,

                expected_answer:
                  quiz.expected_answer,

                student_answer:
                  quizAnswer,
              }),
            }
          );

        const data =
          await response.json();

        if (!response.ok) {
          throw new Error(
            data.detail ||
              "Unable to evaluate quiz answer."
          );
        }

        console.log(
          "QUIZ EVALUATION NEXT ACTION:",
          data.next_action,
          data
        );

        setQuizEvaluation(
          data
        );
      } catch (error) {
        console.error(error);

        alert(error.message);
      } finally {
        setEvaluatingQuiz(
          false
        );
      }
    };

  // ============================================================
  // CONTINUE AFTER QUIZ
  // ============================================================

  const handleNextAfterQuiz =
    async () => {
      /*
       * IMPORTANT:
       *
       * Evaluation has already updated
       * ConceptMastery in the backend.
       *
       * We now ask the adaptive planner again.
       *
       * This means the next lesson is determined
       * by the student's updated mastery rather
       * than by simply moving to the next array item.
       */

      setQuiz(null);

      setQuizAnswer("");

      setQuizEvaluation(null);

      // Get the next adaptive concept.
      await handleContinueLearning();
    };
  // ============================================================
// PROGRESS DASHBOARD
// ============================================================

if (screen === "progress") {
  const subject = subjects.find(
    (item) => item.id === Number(subjectId)
  );

  const conceptMap = new Map(
    concepts.map((concept) => [
      concept.id,
      concept,
    ])
  );

  const subjectMastery = masteryData.filter(
    (item) =>
      conceptMap.has(item.concept_id)
  );

  const overallMastery =
    subjectMastery.length > 0
      ? subjectMastery.reduce(
          (sum, item) =>
            sum + item.mastery_score,
          0
        ) / subjectMastery.length
      : 0;

  const masteredCount =
    subjectMastery.filter(
      (item) => item.mastery_score >= 0.8
    ).length;

  const learningCount =
    subjectMastery.filter(
      (item) => item.mastery_score < 0.8
    ).length;

  const totalAttempts =
    subjectMastery.reduce(
      (sum, item) =>
        sum + item.attempts,
      0
    );

  const totalCorrect =
    subjectMastery.reduce(
      (sum, item) =>
        sum + item.correct_answers,
      0
    );

  return (
    <div className="app">

      <header className="navbar">

        <div className="brand">

          <div className="brand-icon">
            AI
          </div>

          <div>
            <h1>
              Adaptive AI Tutor
            </h1>

            <span>
              Learn at your own pace
            </span>
          </div>

        </div>

        <div className="status">
          <span className="status-dot"></span>
          Progress
        </div>

      </header>

      <main className="main-content">

        <section className="diagnostic-card">

          <div className="hero-badge">
            YOUR PROGRESS
          </div>

          <h2 className="diagnostic-title">

            See how you're
            <br />

            <span>
              progressing.
            </span>

          </h2>

          {subject && (
            <p className="lesson-description">
              {subject.name}
            </p>
          )}

          {loadingProgress ? (

            <div className="loading-message">
              Loading your progress...
            </div>

          ) : progressError ? (

            <div className="error-message">
              {progressError}
            </div>

          ) : (

            <>

              {/* OVERALL MASTERY */}

              <div className="feedback-box">

                <strong>
                  Overall Mastery
                </strong>

                <div
                  style={{
                    fontSize: "42px",
                    fontWeight: "700",
                    marginTop: "8px",
                  }}
                >
                  {Math.round(
                    overallMastery * 100
                  )}
                  %
                </div>

                <div
                  className="progress-track"
                  style={{
                    marginTop: "12px",
                  }}
                >
                  <div
                    className="progress-fill"
                    style={{
                      width: `${
                        overallMastery * 100
                      }%`,
                    }}
                  ></div>
                </div>

                  </div>

                  {/* LEARNER PROFILE */}

                  {studentProfile && (
                    <div
                      className="feedback-box"
                      style={{
                        marginTop: "24px",
                      }}
                    >
                      <div className="concept-label">
                        LEARNER PROFILE
                      </div>

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
                          <p
                            style={{
                              marginTop: "6px",
                              textTransform: "capitalize",
                            }}
                          >
                            {studentProfile.learning_level}
                          </p>
                        </div>

                        <div>
                          <strong>Overall Mastery</strong>
                          <p
                            style={{
                              marginTop: "6px",
                            }}
                          >
                            {Math.round(
                              studentProfile.overall_mastery * 100
                            )}
                            %
                          </p>
                        </div>
                      </div>

                      <div
                        style={{
                          marginTop: "20px",
                        }}
                      >
                        <strong>Subject Progress</strong>

                        {studentProfile.subject_mastery.map(
                          (subject) => (
                            <div
                              key={subject.subject_id}
                              style={{
                                marginTop: "14px",
                              }}
                            >
                              <div
                                style={{
                                  display: "flex",
                                  justifyContent: "space-between",
                                  alignItems: "center",
                                }}
                              >
                                <span>
                                  {subject.subject_name}
                                </span>

                                <span>
                                  {Math.round(
                                    subject.mastery * 100
                                  )}
                                  %
                                </span>
                              </div>

                              <div
                                className="progress-track"
                                style={{
                                  marginTop: "8px",
                                }}
                              >
                                <div
                                  className="progress-fill"
                                  style={{
                                    width: `${subject.mastery * 100
                                      }%`,
                                  }}
                                ></div>
                              </div>
                            </div>
                          )
                        )}
                      </div>

                      <div
                        style={{
                          marginTop: "24px",
                        }}
                      >
                        <strong>Concepts to Strengthen</strong>

                        {studentProfile.concepts_to_strengthen.length ===
                        0 ? (
                          <p
                            style={{
                              marginTop: "10px",
                              opacity: 0.7,
                            }}
                          >
                            No concepts currently need additional
                            strengthening.
                          </p>
                        ) : (
                          studentProfile.concepts_to_strengthen.map(
                            (concept) => (
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
                                    <strong>
                                      {concept.concept_name}
                                    </strong>

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

                                  <span>
                                    {Math.round(
                                      concept.mastery * 100
                                    )}
                                    %
                                  </span>
                                </div>

                                <div
                                  className="progress-track"
                                  style={{
                                    marginTop: "8px",
                                  }}
                                >
                                  <div
                                    className="progress-fill"
                                    style={{
                                      width: `${
                                        concept.mastery * 100
                                      }%`,
                                    }}
                                  ></div>
                                </div>
                              </div>
                            )
                          )
                        )}
                      </div>
                    </div>
                  )}

                  {/* SUMMARY */}

                  <div className="features">

                <div className="feature">

                  <span>✓</span>

                  <div>
                    <strong>
                      {masteredCount}
                    </strong>

                    <p>
                      Concepts mastered
                    </p>
                  </div>

                </div>

                <div className="feature">

                  <span>📚</span>

                  <div>
                    <strong>
                      {learningCount}
                    </strong>

                    <p>
                      Concepts to strengthen
                    </p>
                  </div>

                </div>

                <div className="feature">

                  <span>🎯</span>

                  <div>
                    <strong>
                      {totalAttempts}
                    </strong>

                    <p>
                      Total attempts
                    </p>
                  </div>

                </div>

              </div>

              {/* CONCEPT BREAKDOWN */}

              <div
                style={{
                  marginTop: "28px",
                }}
              >

                <div className="concept-label">
                  CONCEPT BREAKDOWN
                </div>

                {subjectMastery.length === 0 ? (

                  <div className="loading-message">
                    No mastery data available yet.
                  </div>

                ) : (

                  subjectMastery.map(
                    (mastery) => {

                      const concept =
                        conceptMap.get(
                          mastery.concept_id
                        );

                      if (!concept) {
                        return null;
                      }

                      const percentage =
                        Math.round(
                          mastery.mastery_score *
                            100
                        );

                      return (
                        <div
                          key={
                            mastery.concept_id
                          }
                          style={{
                            marginTop: "18px",
                            padding: "16px",
                            border:
                              "1px solid #e6e7eb",
                            borderRadius:
                              "12px",
                          }}
                        >

                          <div
                            style={{
                              display: "flex",
                              justifyContent:
                                "space-between",
                              alignItems:
                                "center",
                              gap: "12px",
                            }}
                          >

                            <strong>
                              {concept.name}
                            </strong>

                            <span>
                              {percentage}%
                            </span>

                          </div>

                          <div
                            className="progress-track"
                            style={{
                              marginTop: "10px",
                            }}
                          >

                            <div
                              className="progress-fill"
                              style={{
                                width: `${percentage}%`,
                              }}
                            ></div>

                          </div>

                          <small
                            style={{
                              display: "block",
                              marginTop: "8px",
                              opacity: 0.7,
                            }}
                          >
                            {mastery.attempts}{" "}
                            attempts •{" "}
                            {mastery.correct_answers}{" "}
                            correct
                          </small>

                        </div>
                      );
                    }
                  )

                )}

              </div>

              {/* CONTINUE */}

              <button
                type="button"
                className="start-button"
                onClick={
                  handleContinueLearning
                }
                disabled={
                  loadingLesson
                }
                style={{
                  marginTop: "28px",
                }}
              >

                {loadingLesson
                  ? "Preparing..."
                  : "Continue Learning"}

                <span>
                  →
                </span>

              </button>

            </>

          )}

        </section>

      </main>

    </div>
  );
  } {
    if (screen === "reteach" && reteach) {
      return (
        <div className="screen-container">
        <div className="content-card">
          <h2>Let's Clear This Up</h2>

          <p>
            <strong>Concept:</strong> {reteach.concept}
          </p>

          {reteach.misconceptions &&
            reteach.misconceptions.length > 0 && (
              <div className="feedback-box">
                <h3>What needs correction</h3>

                <ul>
                  {reteach.misconceptions.map(
                    (misconception, index) => (
                      <li key={index}>{misconception}</li>
                    )
                  )}
                </ul>
              </div>
            
            )}

          <div className="lesson-explanation">
            <h3>Reteaching</h3>
            <p>{reteach.explanation}</p>
          </div>

          <button
            type="button"
            onClick={async () => {
              setReteach(null);
              setQuiz(null);
              setQuizAnswer("");
              setQuizEvaluation(null);
              setLesson(null);
              await handleContinueLearning();
            }}
          >
            Continue Learning →
          </button>
        </div>
      </div>
    );
  }
  }


  // ============================================================
  // LESSON SCREEN
  // ============================================================

  if (
    screen === "lesson"
  ) {
    return (
      <div className="app">

        <header className="navbar">

          <div className="brand">

            <div className="brand-icon">
              AI
            </div>

            <div>
              <h1>
                Adaptive AI Tutor
              </h1>

              <span>
                Learn at your own pace
              </span>
            </div>

          </div>

          <div className="status">
            <span className="status-dot"></span>
            Adaptive Lesson
          </div>

        </header>

        <main className="main-content">

          <section className="diagnostic-card">

            <div className="hero-badge">
              YOUR NEXT LESSON
            </div>

            {nextConcept ? (
              <>
                <h2 className="diagnostic-title">

                  Let's learn
                  <br />

                  <span>
                    {nextConcept.name}.
                  </span>

                </h2>

                {nextConcept.description && (
                  <p className="lesson-description">
                    {
                      nextConcept.description
                    }
                  </p>
                )}
              </>
            ) : (
              <>
                <h2 className="diagnostic-title">

                  You've reached the end
                  <br />

                  <span>
                    of this learning path.
                  </span>

                </h2>

                <p>
                  You have demonstrated mastery
                  of the available concepts for
                  this subject.
                </p>

                <button
                  type="button"
                  className="start-button"
                  onClick={async () => {
                    await loadProgress();
                    setScreen("progress");
                  }}
                  disabled={loadingProgress}
                  style={{ marginTop: "24px" }}
                >
                    {loadingProgress
                      ? "Loading Progress..."
                      : "View Your Progress"}

                  <span>
                    →
                  </span>
                </button>
              </>
            )}

            {loadingLesson ? (

              <div className="loading-message">
                Generating your personalized
                lesson...
              </div>

            ) : lesson ? (

              <>

                <div className="feedback-box lesson-content">

                  <strong>
                    Explanation
                  </strong>

                  <p>
                    {lesson.explanation}
                  </p>

                </div>

                {lesson.retrieved_knowledge &&
                  lesson.retrieved_knowledge.length >
                    0 && (

                  <div className="misconception-box">

                    <strong>
                      Knowledge used by
                      your tutor
                    </strong>

                    {lesson.retrieved_knowledge.map(
                      (item, index) => (

                        <div
                          key={`${item.source}-${index}`}
                          className="knowledge-item"
                        >

                          <small>
                            {item.source}
                          </small>

                          <p>
                            {item.content}
                          </p>

                        </div>

                      )
                    )}

                  </div>

                )}

                <div className="question-box">

                  <span className="question-number">
                    CHECK
                  </span>

                  <p>
                    Can you explain{" "}
                    <strong>
                      {nextConcept?.name}
                    </strong>{" "}
                    in your own words?
                  </p>

                </div>

                <button
                  type="button"
                  className="start-button"
                  onClick={
                    handleStartQuiz
                  }
                  disabled={
                    loadingQuiz
                  }
                >

                  {loadingQuiz
                    ? "Preparing Quiz..."
                    : "Continue to Quiz"}

                  <span>
                    →
                  </span>

                </button>

              </>

            ) : nextConcept ? (

              <button
                type="button"
                className="start-button"
                onClick={
                  handleContinueLearning
                }
                disabled={
                  loadingLesson
                }
              >

                Generate Lesson

                <span>
                  →
                </span>

              </button>

            ) : null}

          </section>

        </main>

      </div>
    );
  }

  // ============================================================
  // QUIZ SCREEN
  // ============================================================

  if (
    screen === "quiz" &&
    quiz
  ) {
    return (
      <div className="app">

        <header className="navbar">

          <div className="brand">

            <div className="brand-icon">
              AI
            </div>

            <div>
              <h1>
                Adaptive AI Tutor
              </h1>

              <span>
                Learn at your own pace
              </span>
            </div>

          </div>

          <div className="status">
            <span className="status-dot"></span>
            Quiz
          </div>

        </header>

        <main className="main-content">

          <section className="diagnostic-card">

            <div className="hero-badge">
              KNOWLEDGE CHECK
            </div>

            <h2 className="diagnostic-title">

              Let's see what
              <br />

              <span>
                you've learned.
              </span>

            </h2>

            <div className="concept-label">
              CONCEPT
            </div>

            <h3 className="question-concept">
              {nextConcept?.name}
            </h3>

            <div className="question-box">

              <span className="question-number">
                QUIZ
              </span>

              <p>
                {quiz.question}
              </p>

            </div>

            {!quizEvaluation ? (

              <>

                <label
                  className="answer-label"
                  htmlFor="quiz-answer"
                >
                  Your answer
                </label>

                <textarea
                  id="quiz-answer"
                  className="answer-input"
                  value={quizAnswer}
                  onChange={(event) =>
                    setQuizAnswer(
                      event.target.value
                    )
                  }
                  placeholder="Explain your answer in your own words..."
                  rows={6}
                />

                <button
                  type="button"
                  className="start-button"
                  onClick={
                    handleEvaluateQuiz
                  }
                  disabled={
                    !quizAnswer.trim() ||
                    evaluatingQuiz
                  }
                >

                  {evaluatingQuiz
                    ? "Evaluating..."
                    : "Submit Quiz"}

                  <span>
                    →
                  </span>

                </button>

              </>

            ) : (

              <div className="feedback-section">

                <div
                  className={`feedback-result ${
                    quizEvaluation.result ===
                    "correct"
                      ? "correct"
                      : "incorrect"
                  }`}
                >

                  <strong>

                    {quizEvaluation.result ===
                    "correct"
                      ? "Excellent!"
                      : "Let's strengthen this concept"}

                  </strong>

                  <span>

                    Score:{" "}
                    {Math.round(
                      quizEvaluation.score *
                        100
                    )}
                    %

                  </span>

                </div>

                <div className="feedback-box">

                  <strong>
                    Feedback
                  </strong>

                  <p>
                    {
                      quizEvaluation.feedback
                    }
                  </p>

                </div>

                {quizEvaluation.misconception && (

                  <div className="misconception-box">

                    <strong>
                      What to improve
                    </strong>

                    <p>
                      {
                        quizEvaluation.misconception
                      }
                    </p>

                  </div>

                )}

                <div className="question-box">

                  <span className="question-number">
                    MASTERY
                  </span>

                  <p>

                    Current mastery:{" "}

                    <strong>
                      {Math.round(
                        quizEvaluation.mastery_score *
                          100
                      )}
                      %
                    </strong>

                  </p>

                </div>

                {quizEvaluation.next_action && (

                  <div className="feedback-box">

                    <strong>
                      Tutor decision
                    </strong>

                    <p>
                      {
                        quizEvaluation.next_action
                      }
                    </p>

                    {quizEvaluation.reason && (
                      <small>
                        {
                          quizEvaluation.reason
                        }
                      </small>
                    )}

                  </div>

                )}

                  <button
                    type="button"
                    className="start-button"
                    onClick={async () => {
                      if (!quizEvaluation) return;

                      const action = quizEvaluation.next_action;

                      if (action === "reteach") {
                        await handleStartReteach();
                        return;
                      }
                      

                      if (action === "practice") {
                        setQuiz(null);
                        setQuizAnswer("");
                        setQuizEvaluation(null);
                        await handleStartQuiz();
                        return;
                      }

                      if (action === "prerequisite") {
                        setQuiz(null);
                        setQuizAnswer("");
                        setQuizEvaluation(null);
                        await handleContinueLearning();
                        return;
                      }

                      if (action === "advance") {
                        setQuiz(null);
                        setQuizAnswer("");
                        setQuizEvaluation(null);

                        await handleContinueLearning();
                        return;
                      }

                      // Fallback
                      setQuiz(null);
                      setQuizAnswer("");
                      setQuizEvaluation(null);
                      await loadProgress();
                      setScreen("progress");
                    }}
                    disabled={loadingProgress}
                  >
                    {loadingProgress
                      ? "Loading..."
                      : quizEvaluation.next_action === "reteach"
                        ? "Reteach This Concept"
                        : quizEvaluation.next_action === "practice"
                          ? "Practice Again"
                          : quizEvaluation.next_action === "prerequisite"
                            ? "Learn Prerequisite"
                            : quizEvaluation.next_action === "advance"
                              ? "Continue to Next Concept"
                              : "Continue"}

                    <span>
                      →
                    </span>
                  </button>

              </div>

            )}

          </section>

        </main>

      </div>
    );
  }

  // ============================================================
  // DIAGNOSTIC SCREEN
  // ============================================================

  if (
    screen === "diagnostic" &&
    diagnostic
  ) {

    const currentQuestion =
      diagnostic.questions[
        currentQuestionIndex
      ];

    const totalQuestions =
      diagnostic.questions.length;

    const questionNumber =
      currentQuestionIndex + 1;

    const progress =
      totalQuestions > 0
        ? (questionNumber /
            totalQuestions) *
          100
        : 0;

    // ----------------------------------------------------------
    // DIAGNOSTIC COMPLETE
    // ----------------------------------------------------------

    if (
      diagnosticComplete
    ) {

      return (
        <div className="app">

          <header className="navbar">

            <div className="brand">

              <div className="brand-icon">
                AI
              </div>

              <div>
                <h1>
                  Adaptive AI Tutor
                </h1>

                <span>
                  Learn at your own pace
                </span>
              </div>

            </div>

            <div className="status">
              <span className="status-dot"></span>
              Diagnostic Complete
            </div>

          </header>

          <main className="main-content">

            <section className="diagnostic-card completion-card">

              <div className="completion-icon">
                ✓
              </div>

              <div className="hero-badge">
                DIAGNOSTIC COMPLETE
              </div>

              <h2>

                Great job.
                <br />

                <span>
                  Your learning path is ready.
                </span>

              </h2>

              <p>
                Your answers have been evaluated.
                The tutor can now adapt the
                learning experience to your
                current understanding.
              </p>

              <button
                type="button"
                className="start-button"
                onClick={async () => {
                  setLesson(null);
                  setNextConcept(null);

                  await handleContinueLearning();
                }}
                disabled={
                  loadingLesson
                }
              >

                {loadingLesson
                  ? "Preparing Your Lesson..."
                  : "Start Learning"}

                <span>
                  →
                </span>

              </button>

            </section>

          </main>

        </div>
      );
    }

    // ----------------------------------------------------------
    // DIAGNOSTIC QUESTION
    // ----------------------------------------------------------

    return (
      <div className="app">

        <header className="navbar">

          <div className="brand">

            <div className="brand-icon">
              AI
            </div>

            <div>
              <h1>
                Adaptive AI Tutor
              </h1>

              <span>
                Learn at your own pace
              </span>
            </div>

          </div>

          <div className="status">
            <span className="status-dot"></span>
            Diagnostic in progress
          </div>

        </header>

        <main className="main-content">

          <section className="diagnostic-card">

            <div className="diagnostic-top">

              <div>

                <div className="hero-badge">
                  KNOWLEDGE CHECK
                </div>

                <h2 className="diagnostic-title">

                  Let's understand
                  <br />

                  <span>
                    what you already know.
                  </span>

                </h2>

              </div>

              <div className="question-counter">

                <strong>
                  {questionNumber}
                </strong>

                <span>
                  / {totalQuestions}
                </span>

              </div>

            </div>

            <div className="progress-track">

              <div
                className="progress-fill"
                style={{
                  width: `${progress}%`,
                }}
              ></div>

            </div>

            <div className="concept-label">
              CONCEPT
            </div>

            <h3 className="question-concept">
              {currentQuestion.concept}
            </h3>

            <div className="question-box">

              <span className="question-number">
                Q{questionNumber}
              </span>

              <p>
                {currentQuestion.question}
              </p>

            </div>

            {!feedback ? (

              <>

                <label
                  className="answer-label"
                  htmlFor="answer"
                >
                  Your answer
                </label>

                <textarea
                  id="answer"
                  className="answer-input"
                  value={answer}
                  onChange={(event) =>
                    setAnswer(
                      event.target.value
                    )
                  }
                  placeholder="Explain your answer in your own words..."
                  rows={6}
                />

                <button
                  type="button"
                  className="start-button"
                  onClick={
                    handleSubmitAnswer
                  }
                  disabled={
                    !answer.trim() ||
                    submitting
                  }
                >

                  {submitting
                    ? "Evaluating..."
                    : "Submit Answer"}

                  <span>
                    →
                  </span>

                </button>

              </>

            ) : (

              <div className="feedback-section">

                <div
                  className={`feedback-result ${
                    feedback.result ===
                    "correct"
                      ? "correct"
                      : "incorrect"
                  }`}
                >

                  <strong>

                    {feedback.result ===
                    "correct"
                      ? "Good understanding"
                      : "Let's work on this"}

                  </strong>

                  <span>

                    Score:{" "}
                    {Math.round(
                      feedback.score *
                        100
                    )}
                    %

                  </span>

                </div>

                <div className="feedback-box">

                  <strong>
                    Feedback
                  </strong>

                  <p>
                    {feedback.feedback}
                  </p>

                </div>

                {feedback.misconception && (

                  <div className="misconception-box">

                    <strong>
                      What to improve
                    </strong>

                    <p>
                      {
                        feedback.misconception
                      }
                    </p>

                  </div>

                )}

                <button
                  type="button"
                  className="start-button"
                  onClick={
                    handleNextQuestion
                  }
                >

                  {questionNumber ===
                  totalQuestions
                    ? "Finish Diagnostic"
                    : "Next Question"}

                  <span>
                    →
                  </span>

                </button>

              </div>

            )}

          </section>

        </main>

      </div>
    );
  }

  // ============================================================
  // SETUP SCREEN
  // ============================================================

  return (
    <div className="app">

      <header className="navbar">

        <div className="brand">

          <div className="brand-icon">
            AI
          </div>

          <div>

            <h1>
              Adaptive AI Tutor
            </h1>

            <span>
              Learn at your own pace
            </span>

          </div>

        </div>

        <div className="status">

          <span className="status-dot"></span>

          AI Tutor Ready

        </div>

      </header>

      <main className="main-content">

        <section className="hero">

          <div className="hero-badge">
            PERSONALIZED LEARNING
          </div>

          <h2>

            Learn anything.
            <br />

            <span>
              Your tutor adapts to you.
            </span>

          </h2>

          <p>
            Start with a topic or upload your own
            study material. The tutor assesses your
            knowledge and adapts the learning path
            based on your progress.
          </p>

        </section>

        <section className="setup-card">

          <div className="card-header">

            <div>

              <h3>
                Start Learning
              </h3>

              <p>
                Tell us how you'd like to learn.
              </p>

            </div>

            <div className="step-number">
              01
            </div>

          </div>

          <div className="form-section">

            <label htmlFor="subject">
              What do you want to learn?
            </label>

            {loadingSubjects ? (

              <div className="loading-message">
                Loading subjects...
              </div>

            ) : subjectError ? (

              <div className="error-message">
                {subjectError}
              </div>

            ) : (

              <select
                id="subject"
                value={subjectId}
                onChange={(event) =>
                  setSubjectId(
                    event.target.value
                  )
                }
              >

                <option value="">
                  Select a subject
                </option>

                {subjects.map(
                  (subject) => (

                    <option
                      key={subject.id}
                      value={subject.id}
                    >
                      {subject.name}
                    </option>

                  )
                )}

              </select>

            )}

          </div>
          <div className="form-section">

            <label htmlFor="concept">
              Which concept do you want to study?
            </label>

            {loadingConcepts ? (

              <div className="loading-message">
                Loading concepts...
              </div>

            ) : concepts.length === 0 ? (

              <div className="loading-message">
                No concepts available for this subject.
              </div>

            ) : (

              <select
                id="concept"
                value={conceptId}
                onChange={(event) =>
                  setConceptId(event.target.value)
                }
              >

                <option value="">
                  Select a concept
                </option>

                {concepts.map((concept) => (

                  <option
                    key={concept.id}
                    value={concept.id}
                  >
                    {concept.name}
                  </option>

                ))}

              </select>

            )}

          </div>

          <div className="form-section">

            <label>
              What's your current level?
            </label>

            <div className="level-options">

              <button
                type="button"
                className={`level-card ${
                  level === "beginner"
                    ? "selected"
                    : ""
                }`}
                onClick={() =>
                  setLevel(
                    "beginner"
                  )
                }
              >

                <span className="level-icon">
                  🌱
                </span>

                <span>

                  <strong>
                    Beginner
                  </strong>

                  <small>
                    I'm starting from scratch
                  </small>

                </span>

              </button>

              <button
                type="button"
                className={`level-card ${
                  level === "intermediate"
                    ? "selected"
                    : ""
                }`}
                onClick={() =>
                  setLevel(
                    "intermediate"
                  )
                }
              >

                <span className="level-icon">
                  📈
                </span>

                <span>

                  <strong>
                    Intermediate
                  </strong>

                  <small>
                    I know the basics
                  </small>

                </span>

              </button>

              <button
                type="button"
                className={`level-card ${
                  level === "advanced"
                    ? "selected"
                    : ""
                }`}
                onClick={() =>
                  setLevel(
                    "advanced"
                  )
                }
              >

                <span className="level-icon">
                  🚀
                </span>

                <span>

                  <strong>
                    Advanced
                  </strong>

                  <small>
                    I want deeper understanding
                  </small>

                </span>

              </button>

            </div>

          </div>

          <div className="divider">

            <span>
              OPTIONAL
            </span>

          </div>

          <div className="form-section">

            <label>
              Learn from your own material
            </label>

            <label className="upload-area">

              <input
                type="file"
                accept=".pdf,.txt"
                disabled={uploadingMaterial}
                onChange={async (event) => {
                  const file =
                    event.target.files[0] || null;

                  setMaterial(file);
                  setMaterialStatus("");

                  if (file) {
                    await handleMaterialUpload(file);
                  }
                }}
              />

              <span className="upload-icon">
                📄
              </span>

              <span className="upload-title">

                {material
                  ? material.name
                  : "Upload your study material"}

              </span>

              <span className="upload-description">
                PDF or TXT • Optional
              </span>

            </label>

          </div>

          <button
            type="button"
            className="start-button"
            onClick={handleStart}
            disabled={
              loadingSubjects ||
              !!subjectError ||
              !subjectId ||
              starting
            }
          >

            {starting
              ? "Starting..."
              : "Start Learning"}

            <span>
              →
            </span>

          </button>
          <button
            type="button"
            className="skip-diagnostic-button"
            onClick={handleSkipDiagnostic}
            disabled={
              loadingSubjects ||
              !!subjectError ||
              !subjectId ||
              loadingLesson
            }
          >
            {loadingLesson
              ? "Preparing..."
              : "Skip Diagnostic — Test Adaptive Learning"}
          </button>
          <p className="privacy-note">
            Your material will be used to create a
            personalized learning experience.
          </p>

        </section>

        <section className="features">

          <div className="feature">

            <span>
              🎯
            </span>

            <div>

              <strong>
                Adaptive
              </strong>

              <p>
                Learning adjusts to your mastery.
              </p>

            </div>

          </div>

          <div className="feature">

            <span>
              🧠
            </span>

            <div>

              <strong>
                Personalized
              </strong>

              <p>
                Identifies gaps and misconceptions.
              </p>

            </div>

          </div>

          <div className="feature">

            <span>
              📚
            </span>

            <div>

              <strong>
                Grounded
              </strong>

              <p>
                Learn from trusted study material.
              </p>

            </div>

          </div>

        </section>

      </main>

    </div>
  );
}

export default App;