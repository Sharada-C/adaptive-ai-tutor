import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "./api";

function mockFetch(status, body, { json = true } = {}) {
  const text = json ? JSON.stringify(body) : body;

  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    text: () => Promise.resolve(text),
  });
}

describe("api client", () => {
  beforeEach(() => {
    api.resetStudentCache();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls the backend under /api", async () => {
    mockFetch(200, []);

    await api.getSubjects();

    expect(fetch).toHaveBeenCalledWith("/api/subjects", { method: "GET" });
  });

  it("sends JSON bodies with a content type", async () => {
    mockFetch(200, { question: "q" });

    await api.generateQuiz(3, 9);

    const [url, options] = fetch.mock.calls[0];

    expect(url).toBe("/api/tutor/quiz");
    expect(options.method).toBe("POST");
    expect(options.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(options.body)).toEqual({ student_id: 3, concept_id: 9 });
  });

  it("maps evaluate arguments to the backend field names", async () => {
    mockFetch(200, {});

    await api.evaluateQuizAnswer({
      studentId: 1,
      conceptId: 2,
      question: "q",
      expectedAnswer: "e",
      studentAnswer: "a",
    });

    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({
      student_id: 1,
      concept_id: 2,
      question: "q",
      expected_answer: "e",
      student_answer: "a",
    });
  });

  it("uploads material as multipart without a manual content type", async () => {
    mockFetch(200, { chunks_inserted: 4 });

    const file = new File(["hello"], "notes.txt", { type: "text/plain" });

    await api.uploadSubjectMaterial(5, file);

    const [url, options] = fetch.mock.calls[0];

    expect(url).toBe("/api/knowledge/upload/subject");
    expect(options.body).toBeInstanceOf(FormData);
    expect(options.body.get("subject_id")).toBe("5");
    expect(options.body.get("file")).toBe(file);
    expect(options.headers).toBeUndefined();
  });

  it("surfaces a string detail from FastAPI", async () => {
    mockFetch(422, { detail: "No study material is available." });

    await expect(api.generateQuiz(1, 1)).rejects.toMatchObject({
      message: "No study material is available.",
      status: 422,
    });
  });

  it("joins validation error messages", async () => {
    mockFetch(422, {
      detail: [{ msg: "Field required" }, { msg: "Value is not valid" }],
    });

    await expect(api.getSubjects()).rejects.toThrow(
      "Field required; Value is not valid"
    );
  });

  it("does not crash on a non-JSON error body", async () => {
    mockFetch(500, "Internal Server Error", { json: false });

    await expect(api.getSubjects()).rejects.toThrow(/backend hit an error/);
  });

  it("reports an unreachable backend in plain language", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError("Failed"));

    await expect(api.getSubjects()).rejects.toThrow(/Cannot reach the tutor/);
  });

  it("shares one bootstrap request between concurrent callers", async () => {
    mockFetch(200, { student_id: 1, user_id: 1 });

    await Promise.all([api.getStudent("Sharu"), api.getStudent("sharu")]);

    expect(fetch).toHaveBeenCalledTimes(1);
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({
      username: "Sharu",
    });
  });

  it("sends a new request when the profile name changes", async () => {
    mockFetch(200, { student_id: 1, user_id: 1 });

    await api.getStudent("Sharu");
    await api.getStudent("Asha");

    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("retries bootstrap after a failure", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError("down"));

    await expect(api.getStudent("Sharu")).rejects.toThrow();

    mockFetch(200, { student_id: 1, user_id: 1 });

    await expect(api.getStudent("Sharu")).resolves.toMatchObject({
      student_id: 1,
    });
  });
});
