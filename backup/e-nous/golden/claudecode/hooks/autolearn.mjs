#!/usr/bin/env node
// autolearn for Claude Code — a Claude session feeds the same autolearn store OpenCode's plugin feeds.
//
// autolearn ships an OpenCode plugin only; its store (~/.autolearn), its throttle and its reviewer
// are harness-agnostic. This hook reuses them through the installed autolearn-core.mjs:
//   start  recompose memory.context.md (Claude reads it through rules/instructions.md)
//   stop   once the session holds `review_threshold` new user messages, spawn the review
//   end    the exit review of whatever the session left unreviewed
// It never blocks Claude: every failure is a debug line and exit 0.
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "fs"
import { homedir } from "os"
import { basename, join } from "path"

const CORE = process.env.AUTOLEARN_CORE || join(homedir(), ".config", "opencode", "plugins", "autolearn-core.mjs")
const OFF = ["AUTOLEARN_DISABLED", "AUTOLEARN_REVIEWER", "OPS_GLOBAL__HEADLESS"].some(name => process.env[name] === "1")

if (OFF || !existsSync(CORE)) process.exit(0)
const core = await import(CORE)

// The user's and the assistant's words only: tool traffic, meta lines and subagent sidechains are not the conversation.
function conversation(path) {
  const said = []
  for (const line of readFileSync(path, "utf-8").split("\n")) {
    let entry
    try { entry = JSON.parse(line) } catch { continue }
    if (!["user", "assistant"].includes(entry?.type) || entry.isSidechain || entry.isMeta) continue
    const content = entry.message?.content
    const text = typeof content === "string"
      ? content
      : (content || []).filter(block => block?.type === "text").map(block => block.text).join("\n")
    if (text.trim()) said.push({ role: entry.type, content: core.redact(core.truncate(text, 2000)), timestamp: entry.timestamp })
  }
  return said
}

function review(input, fresh, trigger) {
  const config = core.parseConfig()
  const buffer = fresh.slice(-(config.max_conversation_buffer || 50))
  const project = basename(input.cwd || process.cwd())
  const reviewMd = core.formatReview(buffer, { project, trigger })
  if (buffer.some(m => m.content.includes(core.REVIEW_HEADING))) return false   // never review a review
  const done = core.runReviewSubprocess({
    reviewMd, title: `autolearn ${trigger} review`, cwd: input.cwd, env: { AUTOLEARN_OPENCODE_BIN: "opencode" },
    messageCount: buffer.length, project, trigger,
  })
  return done?.ok !== false
}

try {
  const event = process.argv[2]
  const input = JSON.parse(readFileSync(0, "utf-8") || "{}")
  core.ensureStore()
  if (event === "start") core.composeContext()
  if ((event === "stop" || event === "end") && input.session_id && existsSync(input.transcript_path || "")) {
    const ledger = join(core.AL_HOME, "claude", `${input.session_id}.json`)
    const reviewed = existsSync(ledger) ? JSON.parse(readFileSync(ledger, "utf-8")).reviewed || 0 : 0
    const said = conversation(input.transcript_path)
    const fresh = said.slice(reviewed)
    const threshold = core.parseConfig().review_threshold || core.THRESHOLD_DEFAULT
    const due = event === "stop" ? fresh.filter(m => m.role === "user").length >= threshold : fresh.length > 2
    if (due && review(input, fresh, event === "stop" ? "threshold" : "exit")) {
      mkdirSync(join(core.AL_HOME, "claude"), { recursive: true })
      writeFileSync(ledger, JSON.stringify({ reviewed: said.length }))
    }
  }
} catch (err) {
  core.dbg("CLAUDE HOOK FAILED", err?.message)
}
process.exit(0)
