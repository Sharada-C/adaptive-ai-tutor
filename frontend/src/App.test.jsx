import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("./api", () => {
  class ApiError extends Error {}

  return {
    ApiError,
    UNAUTHORIZED_EVENT: "tutor:unauthorized",
    login: vi.fn(),
    register: vi.fn(),
    getMe: vi.fn(),
    listUsers: vi.fn(),
    updateUser: vi.fn(),
    getHealth: vi.fn(),
    getSubjects: vi.fn(),
    getConcepts: vi.fn(),
    getMastery: vi.fn(),
    getProfile: vi.fn(),
    setLearningLevel: vi.fn(),
    generateCourse: vi.fn(),
    createCourseFromTopic: vi.fn(),
    uploadSubjectMaterial: vi.fn(),
    startDiagnostic: vi.fn(),
    submitDiagnosticAnswer: vi.fn(),
    getNextConcept: vi.fn(),
    getNextAction: vi.fn(),
    generateLesson: vi.fn(),
    reteach: vi.fn(),
    generateQuiz: vi.fn(),
    evaluateQuizAnswer: vi.fn(),
  };
});

import * as api from "./api";
import App from "./App";

const STUDENT = {
  user_id: 7,
  student_id: 3,
  username: "learner",
  learning_level: "beginner",
  role: "student",
};

const CONCEPT_A = { id: 11, name: "Network Devices", description: "Hardware." };

function signedIn(user = { username: "learner", role: "student" }) {
  localStorage.setItem(
    "tutor_auth",
    JSON.stringify({ token: "tok", user })
  );
}

beforeEach(() => {
  vi.clearAllMocks();

  // Most tests start as a signed-in learner.
  signedIn();

  api.getMe.mockResolvedValue(STUDENT);
  api.getHealth.mockResolvedValue({ status: "ok", llm: "available" });
  api.getSubjects.mockResolvedValue([{ id: 1, name: "Computer Networks" }]);
});

async function chooseSubject(user) {
  const select = await screen.findByLabelText(/what do you want to learn/i);

  await user.selectOptions(select, "1");
}

describe("App", () => {
  it("loads the signed-in learner and shows the setup screen", async () => {
    render(<App />);

    expect(await screen.findByText("AI Tutor Ready")).toBeInTheDocument();
    expect(api.getMe).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("Computer Networks")).toBeInTheDocument();
  });

  it("explains how to start the backend when it is unreachable", async () => {
    api.getMe.mockRejectedValue(new Error("Cannot reach the tutor backend."));

    render(<App />);

    expect(
      await screen.findByText(/can't reach the tutor backend/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/uvicorn app.main:app/)).toBeInTheDocument();
  });

  it("warns on the setup screen when the AI model is offline", async () => {
    api.getHealth.mockResolvedValue({ status: "ok", llm: "unavailable" });

    render(<App />);

    expect(await screen.findByText("AI model offline")).toBeInTheDocument();
  });

  it("saves the learning level to the backend", async () => {
    api.setLearningLevel.mockResolvedValue({});

    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: /advanced/i }));

    expect(api.setLearningLevel).toHaveBeenCalledWith(3, "advanced");
  });

  it("shows a backend error from starting the diagnostic as a notice", async () => {
    api.startDiagnostic.mockRejectedValue(
      new Error("No study material is available for 'Network Devices'.")
    );

    const user = userEvent.setup();
    render(<App />);

    await chooseSubject(user);
    await user.click(screen.getByRole("button", { name: /^start learning/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /no study material is available/i
    );
  });

  it("runs a full lesson -> quiz -> reteach loop with the right concept", async () => {
    api.getNextConcept.mockResolvedValue({
      status: "ok",
      concept: CONCEPT_A,
    });
    api.getNextAction.mockResolvedValue({ action: "learn" });
    api.generateLesson.mockResolvedValue({
      explanation: "Switches connect devices.",
      retrieved_knowledge: [],
    });
    api.generateQuiz.mockResolvedValue({
      question_id: 42,
      question: "What does a switch do?",
      difficulty: "easy",
    });
    api.evaluateQuizAnswer.mockResolvedValue({
      result: "incorrect",
      score: 0.2,
      feedback: "Not quite.",
      misconception: null,
      mastery_score: 0.2,
      next_action: "reteach",
      reason: "Low mastery",
    });
    api.reteach.mockResolvedValue({
      concept: "Network Devices",
      explanation: "A switch forwards frames.",
      misconceptions: [],
    });

    const user = userEvent.setup();
    render(<App />);

    await chooseSubject(user);
    await user.click(
      screen.getByRole("button", { name: /skip diagnostic/i })
    );

    // Lesson for the planned concept.
    expect(await screen.findByText("Switches connect devices.")).toBeInTheDocument();
    expect(api.generateLesson).toHaveBeenCalledWith(3, 11);

    // Quiz.
    await user.click(screen.getByRole("button", { name: /continue to quiz/i }));
    expect(await screen.findByText("What does a switch do?")).toBeInTheDocument();
    expect(api.generateQuiz).toHaveBeenCalledWith(3, 11);

    await user.type(screen.getByLabelText(/your answer/i), "It floods packets");
    await user.click(screen.getByRole("button", { name: /submit quiz/i }));

    expect(await screen.findByText(/current mastery/i)).toBeInTheDocument();
    expect(api.evaluateQuizAnswer).toHaveBeenCalledWith({
      studentId: 3,
      questionId: 42,
      studentAnswer: "It floods packets",
    });

    // The tutor decided to reteach, using the SAME concept (id 11).
    await user.click(
      screen.getByRole("button", { name: /reteach this concept/i })
    );

    expect(await screen.findByText("A switch forwards frames.")).toBeInTheDocument();
    expect(api.reteach).toHaveBeenCalledWith(3, 11);

    // Continuing after the reteach checks the SAME concept with a quiz.
    // It must not ask the planner again (which would reteach in a loop).
    api.getNextConcept.mockClear();
    api.generateQuiz.mockClear();

    await user.click(screen.getByRole("button", { name: /continue learning/i }));

    expect(await screen.findByText("QUIZ")).toBeInTheDocument();
    expect(api.generateQuiz).toHaveBeenCalledWith(3, 11);
    expect(api.getNextConcept).not.toHaveBeenCalled();
  });

  it("goes straight to reteach when the engine says so, using the new concept", async () => {
    api.getNextConcept.mockResolvedValue({ status: "ok", concept: CONCEPT_A });
    api.getNextAction.mockResolvedValue({ action: "reteach" });
    api.reteach.mockResolvedValue({
      concept: "Network Devices",
      explanation: "Reteaching text.",
      misconceptions: ["Hubs are smart"],
    });

    const user = userEvent.setup();
    render(<App />);

    await chooseSubject(user);
    await user.click(screen.getByRole("button", { name: /skip diagnostic/i }));

    expect(await screen.findByText("Reteaching text.")).toBeInTheDocument();
    expect(screen.getByText("Hubs are smart")).toBeInTheDocument();
    expect(api.reteach).toHaveBeenCalledWith(3, 11);
  });

  it("keeps asking the planner after an 'advance' decision", async () => {
    api.getNextConcept
      .mockResolvedValueOnce({ status: "ok", concept: { id: 10, name: "Old" } })
      .mockResolvedValueOnce({ status: "ok", concept: CONCEPT_A });
    api.getNextAction
      .mockResolvedValueOnce({ action: "advance" })
      .mockResolvedValueOnce({ action: "learn" });
    api.generateLesson.mockResolvedValue({
      explanation: "Lesson for the second concept.",
      retrieved_knowledge: [],
    });

    const user = userEvent.setup();
    render(<App />);

    await chooseSubject(user);
    await user.click(screen.getByRole("button", { name: /skip diagnostic/i }));

    expect(
      await screen.findByText("Lesson for the second concept.")
    ).toBeInTheDocument();
    expect(api.generateLesson).toHaveBeenCalledWith(3, 11);
  });

  it("teaches the prerequisite when the engine asks for it", async () => {
    api.getNextConcept.mockResolvedValue({ status: "ok", concept: CONCEPT_A });
    api.getNextAction.mockResolvedValue({
      action: "prerequisite",
      prerequisite_concept_id: 5,
      prerequisite_concept: "Network Fundamentals",
    });
    api.generateLesson.mockResolvedValue({
      explanation: "Fundamentals lesson.",
      retrieved_knowledge: [],
    });

    const user = userEvent.setup();
    render(<App />);

    await chooseSubject(user);
    await user.click(screen.getByRole("button", { name: /skip diagnostic/i }));

    expect(await screen.findByText("Fundamentals lesson.")).toBeInTheDocument();
    expect(api.generateLesson).toHaveBeenCalledWith(3, 5);
  });

  it("shows the end-of-path screen when the planner is complete", async () => {
    api.getNextConcept.mockResolvedValue({ status: "complete", concept: null });

    const user = userEvent.setup();
    render(<App />);

    await chooseSubject(user);
    await user.click(screen.getByRole("button", { name: /skip diagnostic/i }));

    expect(
      await screen.findByText(/of this learning path/i)
    ).toBeInTheDocument();
  });

  it("uploads study material for the selected subject", async () => {
    signedIn({ username: "teach", role: "instructor" });
    api.getMe.mockResolvedValue({ ...STUDENT, role: "instructor" });

    api.uploadSubjectMaterial.mockResolvedValue({ chunks_inserted: 6 });

    const user = userEvent.setup();
    const { container } = render(<App />);

    await chooseSubject(user);

    const file = new File(["notes"], "notes.txt", { type: "text/plain" });
    await user.upload(container.querySelector('input[type="file"]'), file);

    await waitFor(() =>
      expect(api.uploadSubjectMaterial).toHaveBeenCalledWith(1, file)
    );
    expect(
      await screen.findByText(/6 knowledge chunks added/i)
    ).toBeInTheDocument();
  });

  it("creates a course and selects it", async () => {
    signedIn({ username: "teach", role: "instructor" });
    api.getMe.mockResolvedValue({ ...STUDENT, role: "instructor" });

    api.generateCourse.mockResolvedValue({
      subject_id: 2,
      subject: "Operating Systems",
      concepts_created: 8,
    });
    api.getSubjects
      .mockResolvedValueOnce([{ id: 1, name: "Computer Networks" }])
      .mockResolvedValue([
        { id: 1, name: "Computer Networks" },
        { id: 2, name: "Operating Systems" },
      ]);

    const user = userEvent.setup();
    render(<App />);

    await screen.findByText("Computer Networks");

    await user.type(screen.getByLabelText(/create a new course/i), "Operating Systems");
    await user.click(screen.getByRole("button", { name: /generate course/i }));

    expect(api.generateCourse).toHaveBeenCalledWith("Operating Systems");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /created "operating systems" with 8 concepts/i
    );
    expect(screen.getByLabelText(/what do you want to learn/i)).toHaveValue("2");
  });

  it("tells the student when a lesson is shown straight from the material", async () => {
    api.getNextConcept.mockResolvedValue({ status: "ok", concept: CONCEPT_A });
    api.getNextAction.mockResolvedValue({ action: "learn" });
    api.generateLesson.mockResolvedValue({
      explanation: "A switch connects devices.",
      retrieved_knowledge: [],
      mode: "extractive",
    });

    const user = userEvent.setup();
    render(<App />);

    await chooseSubject(user);
    await user.click(screen.getByRole("button", { name: /skip diagnostic/i }));

    expect(await screen.findByText("A switch connects devices.")).toBeInTheDocument();
    expect(screen.getByText(/shown directly from your study material/i)).toBeInTheDocument();
  });
});

describe("authentication", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  const fillSignIn = async (user, name, password) => {
    await user.type(await screen.findByLabelText(/^username$/i), name);
    await user.type(screen.getByLabelText(/^password$/i), password);
  };

  it("shows the sign-in form when nobody is signed in", async () => {
    render(<App />);

    expect(await screen.findByLabelText(/^username$/i)).toBeInTheDocument();
    expect(api.getMe).not.toHaveBeenCalled();
  });

  it("signs in and stores the token", async () => {
    api.login.mockResolvedValue({
      access_token: "tok-1",
      user: { username: "Sharu", role: "student" },
    });
    api.getMe.mockResolvedValue({ ...STUDENT, username: "Sharu" });

    const user = userEvent.setup();
    render(<App />);

    await fillSignIn(user, "Sharu", "correct-horse");
    await user.click(screen.getByRole("button", { name: /^sign in/i }));

    expect(await screen.findByText("AI Tutor Ready")).toBeInTheDocument();
    expect(api.login).toHaveBeenCalledWith("Sharu", "correct-horse");
    expect(JSON.parse(localStorage.getItem("tutor_auth")).token).toBe("tok-1");
  });

  it("shows the server's message for a wrong password", async () => {
    api.login.mockRejectedValue(new Error("Incorrect username or password."));

    const user = userEvent.setup();
    render(<App />);

    await fillSignIn(user, "Sharu", "nope");
    await user.click(screen.getByRole("button", { name: /^sign in/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Incorrect username or password."
    );
    expect(localStorage.getItem("tutor_auth")).toBeNull();
  });

  it("creates an account", async () => {
    api.register.mockResolvedValue({
      access_token: "tok-2",
      user: { username: "Asha", role: "student" },
    });
    api.getMe.mockResolvedValue({ ...STUDENT, username: "Asha" });

    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("tab", { name: /create account/i }));
    await fillSignIn(user, "Asha", "long-enough-pw");
    await user.type(screen.getByLabelText(/confirm password/i), "long-enough-pw");
    await user.click(screen.getByRole("button", { name: /^create account/i }));

    expect(await screen.findByText("AI Tutor Ready")).toBeInTheDocument();
    expect(api.register).toHaveBeenCalledWith("Asha", "long-enough-pw");
  });

  it("rejects a short password or mismatch without calling the server", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("tab", { name: /create account/i }));
    await fillSignIn(user, "Asha", "short");
    await user.type(screen.getByLabelText(/confirm password/i), "short");
    await user.click(screen.getByRole("button", { name: /^create account/i }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(api.register).not.toHaveBeenCalled();
  });

  it("returns to sign-in when the server rejects the token", async () => {
    signedIn();

    render(<App />);

    await screen.findByText("AI Tutor Ready");

    window.dispatchEvent(new Event("tutor:unauthorized"));

    expect(await screen.findByLabelText(/^username$/i)).toBeInTheDocument();
  });

  it("signs out and forgets the token", async () => {
    signedIn();

    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: /sign out/i }));

    expect(await screen.findByLabelText(/^username$/i)).toBeInTheDocument();
    expect(localStorage.getItem("tutor_auth")).toBeNull();
  });
});

describe("roles", () => {
  it("lets students create their own course but not add to shared ones", async () => {
    signedIn();

    const { container } = render(<App />);

    await screen.findByText("Computer Networks");

    expect(screen.getByLabelText(/type any topic/i)).toBeInTheDocument();
    // Shared course: the upload control is present but disabled.
    expect(container.querySelector('input[type="file"]')).toBeDisabled();
  });

  it("creates a private course from any topic as a student", async () => {
    signedIn();
    api.createCourseFromTopic.mockResolvedValue({
      subject_id: 9,
      subject: "Photosynthesis",
      concepts_created: 6,
      created: true,
      needs_material: false,
      message: "Your course is ready with 3 Wikipedia article(s) as study material.",
    });
    api.getSubjects
      .mockResolvedValueOnce([{ id: 1, name: "Computer Networks" }])
      .mockResolvedValue([
        { id: 1, name: "Computer Networks" },
        { id: 9, name: "Photosynthesis", is_private: true },
      ]);

    const user = userEvent.setup();
    const { container } = render(<App />);

    await screen.findByText("Computer Networks");
    await user.type(screen.getByLabelText(/type any topic/i), "Photosynthesis");
    await user.click(screen.getByRole("button", { name: /create my course/i }));

    expect(api.createCourseFromTopic).toHaveBeenCalledWith("Photosynthesis");
    expect(api.generateCourse).not.toHaveBeenCalled();
    expect(await screen.findByRole("alert")).toHaveTextContent(/3 wikipedia article/i);
    expect(screen.getByLabelText(/what do you want to learn/i)).toHaveValue("9");
    // Own course: uploads are allowed.
    expect(container.querySelector('input[type="file"]')).toBeEnabled();
  });

  it("does not show user management to students", async () => {
    signedIn();

    render(<App />);

    await screen.findByText("AI Tutor Ready");

    expect(
      screen.queryByRole("button", { name: /manage users/i })
    ).not.toBeInTheDocument();
  });

  it("lets an admin open user management and change a role", async () => {
    signedIn({ username: "boss", role: "admin" });
    api.getMe.mockResolvedValue({
      ...STUDENT,
      user_id: 1,
      username: "boss",
      role: "admin",
    });
    api.listUsers.mockResolvedValue([
      { id: 1, username: "boss", role: "admin", is_active: true, has_password: true },
      { id: 2, username: "asha", role: "student", is_active: true, has_password: true },
    ]);
    api.updateUser.mockResolvedValue({
      id: 2,
      username: "asha",
      role: "instructor",
      is_active: true,
      has_password: true,
    });

    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: /manage users/i }));
    await user.selectOptions(
      await screen.findByLabelText("Role for asha"),
      "instructor"
    );

    expect(api.updateUser).toHaveBeenCalledWith(2, { role: "instructor" });
  });
});
