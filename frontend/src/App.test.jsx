import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("./api", () => {
  class ApiError extends Error {}

  return {
    ApiError,
    getStudent: vi.fn(),
    resetStudentCache: vi.fn(),
    getHealth: vi.fn(),
    getSubjects: vi.fn(),
    getConcepts: vi.fn(),
    getMastery: vi.fn(),
    getProfile: vi.fn(),
    setLearningLevel: vi.fn(),
    generateCourse: vi.fn(),
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
};

const CONCEPT_A = { id: 11, name: "Network Devices", description: "Hardware." };

beforeEach(() => {
  vi.clearAllMocks();

  api.getStudent.mockResolvedValue(STUDENT);
  api.getHealth.mockResolvedValue({ status: "ok", llm: "available" });
  api.getSubjects.mockResolvedValue([{ id: 1, name: "Computer Networks" }]);
});

async function chooseSubject(user) {
  const select = await screen.findByLabelText(/what do you want to learn/i);

  await user.selectOptions(select, "1");
}

describe("App", () => {
  it("creates the learner on load and shows the setup screen", async () => {
    render(<App />);

    expect(await screen.findByText("AI Tutor Ready")).toBeInTheDocument();
    expect(api.getStudent).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("Computer Networks")).toBeInTheDocument();
  });

  it("explains how to start the backend when it is unreachable", async () => {
    api.getStudent.mockRejectedValue(new Error("Cannot reach the tutor backend."));

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
      question: "What does a switch do?",
      expected_answer: "Connects devices.",
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
      conceptId: 11,
      question: "What does a switch do?",
      expectedAnswer: "Connects devices.",
      studentAnswer: "It floods packets",
    });

    // The tutor decided to reteach, using the SAME concept (id 11).
    await user.click(
      screen.getByRole("button", { name: /reteach this concept/i })
    );

    expect(await screen.findByText("A switch forwards frames.")).toBeInTheDocument();
    expect(api.reteach).toHaveBeenCalledWith(3, 11);
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
});
