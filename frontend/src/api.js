// ============================================================
// API CLIENT
//
// Every request to the backend goes through this module so the
// base URL, error handling and endpoint shapes live in one place.
// ============================================================

// "/api" is proxied to the backend by the Vite dev server (see
// vite.config.js). Set VITE_API_BASE_URL to a full URL to call a
// backend on another origin directly.
const BASE_URL = (import.meta.env.VITE_API_BASE_URL || "/api").replace(
  /\/+$/,
  ""
);

export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// FastAPI reports errors as { detail: "message" } or, for request
// validation failures, { detail: [{ msg, loc, ... }, ...] }.
function errorMessage(data, response) {
  const detail = data?.detail;

  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((item) => item?.msg)
      .filter(Boolean)
      .join("; ");
  }

  if (response.status >= 500) {
    return `The tutor backend hit an error (${response.status}). Check the backend logs.`;
  }

  return `Request failed (${response.status}).`;
}

async function request(path, { method = "GET", json, formData } = {}) {
  const options = { method };

  if (json !== undefined) {
    options.headers = { "Content-Type": "application/json" };
    options.body = JSON.stringify(json);
  } else if (formData !== undefined) {
    // The browser sets the multipart boundary header itself.
    options.body = formData;
  }

  let response;

  try {
    response = await fetch(`${BASE_URL}${path}`, options);
  } catch {
    throw new ApiError(
      "Cannot reach the tutor backend. Make sure it is running, then try again.",
      0
    );
  }

  // Read the body as text first: error pages (for example a plain
  // "Internal Server Error") are not JSON and must not crash the UI.
  const text = await response.text();
  let data = null;

  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    throw new ApiError(errorMessage(data, response), response.status);
  }

  return data;
}

// ------------------------------------------------------------
// Student
// ------------------------------------------------------------

let studentPromise = null;
let studentPromiseFor = "";

// Opens the profile for a username, creating it when the name is new.
// Concurrent calls for the same name share one request, so React
// StrictMode's double effect in development does not send two.
export function getStudent(username) {
  const name = username.trim();
  const key = name.toLowerCase();

  if (!studentPromise || studentPromiseFor !== key) {
    studentPromiseFor = key;

    studentPromise = request("/students/bootstrap", {
      method: "POST",
      json: { username: name },
    }).catch((error) => {
      studentPromise = null;
      throw error;
    });
  }

  return studentPromise;
}

export function resetStudentCache() {
  studentPromise = null;
  studentPromiseFor = "";
}

export const setLearningLevel = (studentId, learningLevel) =>
  request(`/students/${studentId}/level`, {
    method: "PATCH",
    json: { learning_level: learningLevel },
  });

// The profile endpoint is keyed by *user* id, unlike the other student
// endpoints, which use the student (profile) id.
export const getProfile = (userId) => request(`/students/${userId}/profile`);

export const getMastery = (studentId) =>
  request(`/students/${studentId}/mastery`);

// ------------------------------------------------------------
// Curriculum
// ------------------------------------------------------------

export const getHealth = () => request("/health");

export const getSubjects = () => request("/subjects");

export const getConcepts = (subjectId) =>
  request(`/subjects/${subjectId}/concepts`);

export const generateCourse = (topic) =>
  request("/subjects/generate", { method: "POST", json: { topic } });

// ------------------------------------------------------------
// Study material
// ------------------------------------------------------------

// Uploads a PDF, TXT or Markdown file. The backend extracts and embeds
// the text and stores it for the whole subject.
export function uploadSubjectMaterial(subjectId, file) {
  const formData = new FormData();
  formData.append("subject_id", String(subjectId));
  formData.append("file", file);

  return request("/knowledge/upload/subject", { method: "POST", formData });
}

// ------------------------------------------------------------
// Adaptive learning
// ------------------------------------------------------------

export const getNextConcept = (studentId, subjectId) =>
  request(`/students/${studentId}/subjects/${subjectId}/next`);

export const getNextAction = (studentId, conceptId) =>
  request(`/tutor/next/${studentId}/${conceptId}`);

export const startDiagnostic = (studentId, subjectId, limit = 5) =>
  request("/tutor/diagnostic/start", {
    method: "POST",
    json: { student_id: studentId, subject_id: subjectId, limit },
  });

export const submitDiagnosticAnswer = (studentId, questionId, answer) =>
  request("/tutor/diagnostic/submit", {
    method: "POST",
    json: {
      student_id: studentId,
      question_id: questionId,
      student_answer: answer,
    },
  });

export const generateLesson = (studentId, conceptId) =>
  request("/tutor/lesson", {
    method: "POST",
    json: { student_id: studentId, concept_id: conceptId },
  });

export const reteach = (studentId, conceptId) =>
  request("/tutor/reteach", {
    method: "POST",
    json: { student_id: studentId, concept_id: conceptId },
  });

export const generateQuiz = (studentId, conceptId) =>
  request("/tutor/quiz", {
    method: "POST",
    json: { student_id: studentId, concept_id: conceptId },
  });

export const evaluateQuizAnswer = ({
  studentId,
  conceptId,
  question,
  expectedAnswer,
  studentAnswer,
}) =>
  request("/tutor/evaluate", {
    method: "POST",
    json: {
      student_id: studentId,
      concept_id: conceptId,
      question,
      expected_answer: expectedAnswer,
      student_answer: studentAnswer,
    },
  });
