import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "./api";
import { loadAuth, saveAuth } from "./authStorage";

function mockFetch(status, body, { json = true } = {}) {
  const text = json ? JSON.stringify(body) : body;

  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    text: () => Promise.resolve(text),
  });
}

describe("api client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls the backend under /api", async () => {
    mockFetch(200, []);

    await api.getSubjects();

    expect(fetch).toHaveBeenCalledWith("/api/subjects", {
      method: "GET",
      headers: {},
    });
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
      questionId: 7,
      studentAnswer: "a",
    });

    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({
      student_id: 1,
      question_id: 7,
      student_answer: "a",
    });
  });

  it("shows the message of a structured error such as a locked concept", async () => {
    mockFetch(409, {
      detail: { code: "prerequisite_required", message: "'B' is locked until you master 'A'." },
    });

    await expect(api.generateQuiz(1, 2)).rejects.toMatchObject({
      message: "'B' is locked until you master 'A'.",
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
    expect(options.headers["Content-Type"]).toBeUndefined();
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

  it("sends the saved token as a bearer header", async () => {
    saveAuth({ token: "abc123", user: { username: "sharu" } });
    mockFetch(200, []);

    await api.getSubjects();

    expect(fetch.mock.calls[0][1].headers.Authorization).toBe(
      "Bearer abc123"
    );
  });

  it("does not send a token when signing in", async () => {
    saveAuth({ token: "old", user: { username: "sharu" } });
    mockFetch(200, { access_token: "new", user: {} });

    await api.login("sharu", "secret-pass");

    const [url, options] = fetch.mock.calls[0];

    expect(url).toBe("/api/auth/login");
    expect(options.headers.Authorization).toBeUndefined();
    expect(JSON.parse(options.body)).toEqual({
      username: "sharu",
      password: "secret-pass",
    });
  });

  it("registers through /auth/register", async () => {
    mockFetch(201, { access_token: "t", user: {} });

    await api.register("asha", "secret-pass");

    expect(fetch.mock.calls[0][0]).toBe("/api/auth/register");
  });

  it("clears the session and signals when the token is rejected", async () => {
    saveAuth({ token: "expired", user: { username: "sharu" } });
    mockFetch(401, { detail: "Your session has expired." });

    const handler = vi.fn();
    window.addEventListener(api.UNAUTHORIZED_EVENT, handler);

    await expect(api.getSubjects()).rejects.toMatchObject({ status: 401 });

    window.removeEventListener(api.UNAUTHORIZED_EVENT, handler);

    expect(handler).toHaveBeenCalledTimes(1);
    expect(loadAuth()).toBeNull();
  });

  it("treats a wrong password as an error, not an expired session", async () => {
    saveAuth({ token: "still-good", user: { username: "sharu" } });
    mockFetch(401, { detail: "Incorrect username or password." });

    const handler = vi.fn();
    window.addEventListener(api.UNAUTHORIZED_EVENT, handler);

    await expect(api.login("sharu", "wrong")).rejects.toThrow(
      "Incorrect username or password."
    );

    window.removeEventListener(api.UNAUTHORIZED_EVENT, handler);

    expect(handler).not.toHaveBeenCalled();
    expect(loadAuth()?.token).toBe("still-good");
  });

  it("shows a permission error from the server", async () => {
    mockFetch(403, { detail: "You do not have permission to do that." });

    await expect(api.listUsers()).rejects.toMatchObject({ status: 403 });
  });
});
