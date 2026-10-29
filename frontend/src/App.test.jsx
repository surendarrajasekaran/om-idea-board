import React from "react";
import { afterEach, expect, test, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "./main";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
const idea = {
  id: 1,
  content: "Build something useful",
  created_at: "2026-10-29T12:00:00Z",
};

test("loads, searches, and clears the board", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: async () => [idea] }),
  );
  render(<App />);
  expect(await screen.findByText(idea.content)).toBeInTheDocument();
  await userEvent.type(
    screen.getByRole("textbox", { name: "Search ideas" }),
    "no match",
  );
  expect(screen.getByText("No sparks found.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Clear search/ }));
  expect(screen.getByText(idea.content)).toBeInTheDocument();
});

test("submits trimmed content and clears the form", async () => {
  const fetch = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: async () => [] })
    .mockResolvedValueOnce({ ok: true, json: async () => idea });
  vi.stubGlobal("fetch", fetch);
  render(<App />);
  await screen.findByText("The next good idea could be yours.");
  await userEvent.type(
    screen.getByLabelText("Your idea"),
    `  ${idea.content}  `,
  );
  await userEvent.click(
    screen.getByRole("button", { name: /Add to the board/ }),
  );
  expect(await screen.findByText(idea.content)).toBeInTheDocument();
  expect(fetch.mock.calls[1][1].body).toBe(
    JSON.stringify({ content: idea.content }),
  );
  expect(screen.getByLabelText("Your idea")).toHaveValue("");
});

test("keeps unsaved input on failure and offers a retry", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockResolvedValue({ ok: false }),
  );
  render(<App />);
  await screen.findByText("The next good idea could be yours.");
  await userEvent.type(screen.getByLabelText("Your idea"), "Keep my draft");
  await userEvent.click(
    screen.getByRole("button", { name: /Add to the board/ }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Your idea wasn’t saved",
  );
  expect(screen.getByLabelText("Your idea")).toHaveValue("Keep my draft");
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: /Add to the board/ }),
    ).toBeEnabled(),
  );
});
