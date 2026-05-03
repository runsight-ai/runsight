import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock("../client", () => ({
  api: {
    get: apiMock.get,
    post: apiMock.post,
  },
}));

beforeEach(() => {
  vi.resetModules();
  apiMock.get.mockReset();
  apiMock.post.mockReset();
});

describe("API client parsing smoke", () => {
  it("cancelRun returns the typed cancel payload and rejects malformed responses", async () => {
    const { runsApi } = await import("../runs");

    apiMock.post.mockResolvedValueOnce({ id: "run_cancel", status: "cancelled" });

    await expect(runsApi.cancelRun("run_cancel")).resolves.toEqual({
      id: "run_cancel",
      status: "cancelled",
    });
    expect(apiMock.post).toHaveBeenCalledWith("/runs/run_cancel/cancel");

    apiMock.post.mockResolvedValueOnce({ id: "run_cancel" });

    await expect(runsApi.cancelRun("run_cancel")).rejects.toThrow();
  });

  it("getGitFile parses the shared file-read response shape", async () => {
    const { gitApi } = await import("../git");

    apiMock.get.mockResolvedValueOnce({
      content: "name: Smoke workflow\n",
      ref: "main",
    });

    await expect(gitApi.getGitFile("main", "workflows/smoke.yaml")).resolves.toEqual({
      content: "name: Smoke workflow\n",
      ref: "main",
    });
    expect(apiMock.get).toHaveBeenCalledWith(
      "/git/file?ref=main&path=workflows%2Fsmoke.yaml",
    );

    apiMock.get.mockResolvedValueOnce({ content: "missing ref" });

    await expect(gitApi.getGitFile("main", "workflows/smoke.yaml")).rejects.toThrow();
  });
});
