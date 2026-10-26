import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import PrivacyPage from "./PrivacyPage";
import TermsPage from "./TermsPage";
import { LEGAL } from "./legalConfig";
import LoginPage from "../LoginPage";
import SignupPage from "../SignupPage";

function at(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route path="/terms" element={<TermsPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("legal pages", () => {
  it("renders the privacy policy with the contact address and NDPA rights", () => {
    at("/privacy");
    expect(screen.getByRole("heading", { level: 1, name: "Privacy Policy" })).toBeInTheDocument();
    expect(screen.getByText(/Your rights/)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: LEGAL.contactEmail }).length).toBeGreaterThan(0);
  });

  it("renders the terms and links to the privacy policy", () => {
    at("/terms");
    expect(screen.getByRole("heading", { level: 1, name: "Terms of Service" })).toBeInTheDocument();
    const links = screen.getAllByRole("link", { name: "Privacy Policy" });
    expect(links.some((l) => l.getAttribute("href") === "/privacy")).toBe(true);
  });

  it("is linked from sign-in and sign-up", () => {
    at("/login");
    expect(screen.getByRole("link", { name: "Terms of Service" })).toHaveAttribute("href", "/terms");
    expect(screen.getByRole("link", { name: "Privacy Policy" })).toHaveAttribute("href", "/privacy");
  });

  it("sign-up states agreement to both documents", () => {
    at("/signup");
    expect(screen.getByText(/By creating a workspace you agree/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Terms of Service" })).toHaveAttribute("href", "/terms");
    expect(screen.getByRole("link", { name: "Privacy Policy" })).toHaveAttribute("href", "/privacy");
  });
});
