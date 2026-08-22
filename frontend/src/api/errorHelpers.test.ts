import { describe, it, expect } from "vitest";
import { getErrorTitle, getErrorDetail, isNetworkError, isRetryableError, getFieldErrors } from "./client";

function axiosError(status: number, data: any = {}) {
  return { isAxiosError: true, response: { status, data } };
}

describe("error helpers", () => {
  it("identifies a network error (no response at all)", () => {
    const err = { isAxiosError: true, response: undefined };
    expect(isNetworkError(err)).toBe(true);
    expect(getErrorTitle(err)).toBe("Network error");
  });

  it.each([
    [403, "You don't have permission to do this"],
    [404, "Not found"],
    [409, "This couldn't be completed"],
    [422, "Check the highlighted fields"],
    [429, "Too many requests"],
    [500, "Something went wrong on our end"],
  ])("maps status %i to a specific title", (status, expected) => {
    expect(getErrorTitle(axiosError(status))).toBe(expected);
  });

  it("403/404/422 are not retryable, 500/network/unknown are", () => {
    expect(isRetryableError(axiosError(403))).toBe(false);
    expect(isRetryableError(axiosError(404))).toBe(false);
    expect(isRetryableError(axiosError(422))).toBe(false);
    expect(isRetryableError(axiosError(500))).toBe(true);
    expect(isRetryableError(axiosError(409))).toBe(true);
    expect(isRetryableError({ isAxiosError: true, response: undefined })).toBe(true);
  });

  it("extracts field errors from a FastAPI-style 422 detail array", () => {
    const err = axiosError(422, { detail: [{ loc: ["body", "email"], msg: "Invalid email address" }] });
    expect(getFieldErrors(err)).toEqual([{ field: "email", message: "Invalid email address" }]);
  });

  it("extracts field errors from an {errors: {field: message}} shape", () => {
    const err = axiosError(422, { errors: { name: "Name is required" } });
    expect(getFieldErrors(err)).toEqual([{ field: "name", message: "Name is required" }]);
  });

  it("returns no field errors for non-422 statuses", () => {
    expect(getFieldErrors(axiosError(500, { detail: [{ loc: ["x"], msg: "y" }] }))).toEqual([]);
  });

  it("uses the backend detail for a 409 conflict when present", () => {
    const err = axiosError(409, { detail: "Budget already locked for this period" });
    expect(getErrorDetail(err)).toBe("Budget already locked for this period");
  });
});
