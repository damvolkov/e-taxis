#!/usr/bin/env node
// plans — the Stop check of the plans law (persona: Plans). Deterministic, no model, no network.
//
// Reads the hook's JSON on stdin (cwd, stop_hook_active), finds the project root (git top level, else cwd) and,
// only when <root>/.plans/ exists, holds every plan to the law:
//   name      TODO_<word>.md · TODO_<word>_FINISHED.md · TODO_<word>_CANCELLED.md · TODO_<word>_TRANSFERRED.md
//   shape     title · ---- · PROGRESS: <STATE> · ---- · 1. <step> … · ---- · breakdown
//   state     ACTIVE | BLOCKED on a bare name, FINISHED / CANCELLED / TRANSFERRED on the matching suffix — TRANSFERRED:
//             what was left moved whole into another plan
//   strikes   FINISHED ⇒ every step ~~struck~~; every step struck ⇒ FINISHED
//   changelog FINISHED / CANCELLED / TRANSFERRED ⇒ <root>/CHANGELOG.md names TODO_<word>
// As a Claude Code Stop hook (run directly): a violation exits 2 with the list on stderr, so the turn stays open until
// the plan is true; on a stop the check itself already re-opened (stop_hook_active), it lets go — a law that loops is
// worse than one late. As a module, `audit(top)` returns the same list: the OpenCode plugin (plugins/plans.js) uses it.

import { execFileSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const NAME = /^TODO_([A-Za-z0-9]+)(?:_(FINISHED|CANCELLED|TRANSFERRED))?\.md$/;
const RULE = /^-{3,}\s*$/m;
const STATE = /^PROGRESS:\s*(ACTIVE|BLOCKED|FINISHED|CANCELLED|TRANSFERRED)\s*$/m;
const STEP = /^\s*\d+\.\s+(.*\S)\s*$/gm;
const OPEN = new Set(["ACTIVE", "BLOCKED"]);

const check = (dir, file, changelog) => {
  const name = NAME.exec(file);
  if (!name) return [`${file}: not TODO_<word>.md or TODO_<word>_FINISHED|CANCELLED|TRANSFERRED.md`];
  const [, word, suffix] = name;
  const parts = readFileSync(join(dir, file), "utf8").split(RULE);
  if (parts.length < 4) return [`${file}: needs title, ----, PROGRESS, ----, the numbered steps, ----, the breakdown`];
  const state = STATE.exec(parts[1])?.[1];
  const steps = [...parts[2].matchAll(STEP)].map((m) => m[1]);
  const struck = steps.filter((s) => s.startsWith("~~") && s.endsWith("~~")).length;
  const ended = suffix ?? "";
  return [
    !state && `${file}: no PROGRESS line (ACTIVE, BLOCKED, FINISHED, CANCELLED or TRANSFERRED) between the first two rules`,
    steps.length === 0 && `${file}: no numbered steps between the second and third rules`,
    state && !ended && !OPEN.has(state) && `${file}: PROGRESS is ${state} — rename it TODO_${word}_${state}.md`,
    state && ended && state !== ended && `${file}: name says ${ended}, PROGRESS says ${state}`,
    state === "FINISHED" && struck < steps.length && `${file}: FINISHED with ${steps.length - struck} step(s) not ~~struck~~`,
    OPEN.has(state) && steps.length > 0 && struck === steps.length &&
      `${file}: every step is struck — set PROGRESS: FINISHED and rename it TODO_${word}_FINISHED.md`,
    ended && !changelog.includes(`TODO_${word}`) &&
      `${file}: ended, but CHANGELOG.md has no summary naming TODO_${word}`,
  ].filter(Boolean);
};

export const root = (cwd) => {
  try {
    return execFileSync("git", ["-C", cwd, "rev-parse", "--show-toplevel"], { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
  } catch {
    return cwd;
  }
};

export const audit = (top) => {
  const dir = join(top, ".plans");
  if (!existsSync(dir) || !statSync(dir).isDirectory()) return [];
  const changelog = existsSync(join(top, "CHANGELOG.md")) ? readFileSync(join(top, "CHANGELOG.md"), "utf8") : "";
  return readdirSync(dir)
    .filter((file) => !file.startsWith(".") && statSync(join(dir, file)).isFile())
    .sort()
    .flatMap((file) => check(dir, file, changelog));
};

export const message = (problems) =>
  `plans law (persona: Plans) — fix before stopping:\n${problems.map((p) => `- ${p}`).join("\n")}\n`;

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const input = (() => {
    try {
      return JSON.parse(readFileSync(0, "utf8") || "{}");
    } catch {
      return {};
    }
  })();
  const problems = input.stop_hook_active ? [] : audit(root(input.cwd || process.cwd()));
  if (problems.length) {
    process.stderr.write(message(problems));
    process.exit(2);
  }
}
