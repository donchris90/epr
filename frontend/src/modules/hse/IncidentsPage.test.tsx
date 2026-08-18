import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import IncidentsPage from "./IncidentsPage";
import { apiClient } from "../../api/client";

/**
 * Regression coverage for a real bug found via a systematic dropdown
 * audit (see README.md's "frontend dropdown bug hunt" session notes):
 * the near-miss logging form had NO classification selector in the
 * UI at all -- it silently submitted a hardcoded "near_miss" value on
 * every save, which the real backend constraint
 * (HSE's INCIDENT_CLASSIFICATIONS) has never accepted. It would have
 * failed on every single real submission. The incident form's own
 * classification dropdown separately, wrongly, included "near_miss"
 * as one of its own options -- also never a valid value.
 */

vi.mock("../../api/client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

function renderWithClient(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

const VALID_CLASSIFICATIONS = ["first_aid", "medical_treatment", "lost_time", "fatality"];

beforeEach(() => {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url.includes("safety-indicators")) return Promise.resolve({ data: null });
    return Promise.resolve({ data: { data: [] } });
  });
  vi.mocked(apiClient.post).mockResolvedValue({ data: {} });
});

describe("IncidentsPage near-miss form", () => {
  it("shows a classification selector once the near-miss form is opened", async () => {
    const user = userEvent.setup();
    renderWithClient(<IncidentsPage />);

    await user.click(screen.getByRole("button", { name: /log near miss/i }));

    // The bug this guards: the near-miss classification select didn't
    // exist at all. Targeted by its real aria-label, not a blind
    // count of every combobox on the page -- the page also legitimately
    // has an unrelated project-picker select (components/ProjectSelect.tsx).
    expect(screen.getByLabelText("Near miss classification")).toBeInTheDocument();
  });

  it("only offers real backend-valid classification values, never 'near_miss' itself", async () => {
    const user = userEvent.setup();
    renderWithClient(<IncidentsPage />);

    await user.click(screen.getByRole("button", { name: /log incident/i }));
    await user.click(screen.getByRole("button", { name: /log near miss/i }));

    const classificationSelects = [
      screen.getByLabelText("Incident classification"),
      screen.getByLabelText("Near miss classification"),
    ];
    for (const select of classificationSelects) {
      const options = within(select).getAllByRole("option").map((o) => (o as HTMLOptionElement).value);
      expect(options).toEqual(VALID_CLASSIFICATIONS);
      expect(options).not.toContain("near_miss");
    }
  });

  it("submits a valid classification value for a near miss, not the old hardcoded invalid default", async () => {
    const user = userEvent.setup();
    renderWithClient(<IncidentsPage />);

    await user.click(screen.getByRole("button", { name: /log near miss/i }));

    const nearMissSelect = screen.getByLabelText("Near miss classification");
    await user.selectOptions(nearMissSelect, "lost_time");

    const description = screen.getByPlaceholderText(/description/i);
    await user.type(description, "Scaffold plank slipped underfoot, no injury");

    const logButtons = screen.getAllByRole("button", { name: /^log$/i });
    await user.click(logButtons[logButtons.length - 1]);

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        "/hse/near-misses",
        expect.objectContaining({ classification: "lost_time" }),
      );
    });

    // The specific regression: this must never be the literal string
    // "near_miss" -- that was never a valid value for this field.
    const [, payload] = vi.mocked(apiClient.post).mock.calls[0];
    expect((payload as { classification: string }).classification).not.toBe("near_miss");
  });
});
