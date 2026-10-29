// hooks — the house hooks in OpenCode (server plugin API v2): one generic runtime over ../hooks/hooks.json, which
// e-taxis renders from core/tekton/config/hooks.yaml through specs/tekton/opencode.yaml · native.hooks. Nothing here
// names a house event: each binding says where it registers (domain, name), what must hold (when, matchers) and what an
// exit 2 does (effect). A command runs as `/bin/sh -c`, the string Claude Code runs, with the JSON Claude Code would
// send on stdin (session_id, cwd, stop_hook_active, tool_name, tool_input).
//   reopen  ctx.session.prompt(stderr): the turn goes on, and its end carries stop_hook_active: true
//   throw   stderr as the error: the tool call or the prompt is refused
//   refuse  the permission decision becomes deny, stderr its reason
//   none    the exit code is not read
// Registrations are never awaited inside setup: OpenCode 2.2.0 resolves a session or permission hook only once every
// plugin's setup has returned (awaited, the server never serves). Unloading the plugin disposes them. Only the default
// export: a v1 loader would take any other exported function for a plugin.

import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";

const STREAM = "event";

const load = (url) => {
  try {
    return JSON.parse(readFileSync(url, "utf8")).hooks ?? [];
  } catch {
    return [];
  }
};

const run = (command, stdin, cwd) =>
  new Promise((resolve) => {
    const child = spawn("/bin/sh", ["-c", command], { cwd, stdio: ["pipe", "ignore", "pipe"] });
    const errors = [];
    child.stderr.on("data", (chunk) => errors.push(chunk));
    child.on("error", (error) => resolve({ code: -1, stderr: String(error) }));
    child.on("close", (code) => resolve({ code, stderr: Buffer.concat(errors).toString("utf8") }));
    child.stdin.on("error", () => {});
    child.stdin.end(JSON.stringify(stdin));
  });

const holds = (binding, payload) =>
  Object.entries(binding.when ?? {}).every(([key, value]) => (payload?.[key] ?? null) === value) &&
  (binding.matchers.length === 0 || binding.matchers.includes(payload?.tool ?? payload?.action));

const stdin = (binding, payload, cwd, again) => ({
  session_id: payload?.sessionID,
  cwd,
  ...(binding.effect === "reopen" ? { stop_hook_active: again } : {}),
  ...(payload?.tool ?? payload?.action
    ? { tool_name: payload.tool ?? payload.action, tool_input: payload.input ?? { resources: payload.resources ?? [] } }
    : {}),
});

const points = (bindings) => {
  const grouped = new Map();
  for (const binding of bindings) {
    const names = grouped.get(binding.domain) ?? new Map();
    grouped.set(binding.domain, names.set(binding.name, [...(names.get(binding.name) ?? []), binding]));
  }
  return grouped;
};

export default {
  id: "house-hooks",
  setup(ctx) {
    const reopened = new Set();
    const effects = {
      none: async () => {},
      throw: async (_, __, stderr) => {
        throw new Error(stderr.trim() || "blocked by a house hook");
      },
      refuse: async (_, payload, stderr) => {
        payload.effect = "deny";
        payload.message = stderr.trim() || "denied by a house hook";
      },
      reopen: async (binding, payload, stderr) => {
        reopened.add(payload.sessionID);
        await ctx.session.prompt({ sessionID: payload.sessionID, text: stderr.trim() || `${binding.event}: a house hook kept the turn open` });
      },
    };
    const fire = async (bindings, payload, cwd) => {
      for (const binding of bindings.filter((binding) => holds(binding, payload))) {
        const again = binding.effect === "reopen" && reopened.delete(payload?.sessionID);
        const { code, stderr } = await run(binding.command, stdin(binding, payload, cwd, again), cwd);
        if (code === 2) await effects[binding.effect](binding, payload, stderr);
      }
    };
    const fail = (where) => (error) => console.error(`house hooks: ${where}: ${error}`);
    const { [STREAM]: streamed = new Map(), ...hooked } = Object.fromEntries(points(load(new URL("../hooks/hooks.json", import.meta.url))));
    for (const [domain, names] of Object.entries(hooked))
      for (const [name, found] of names) void ctx[domain].hook(name, (payload) => fire(found, payload, ctx.location.directory)).catch(fail(`${domain}.${name}`));
    const controller = new AbortController();
    if (streamed.size)
      void (async () => {
        for await (const event of ctx.event.subscribe({ signal: controller.signal, types: [...streamed.keys()] }))
          void fire(streamed.get(event.type) ?? [], event.data, event.location?.directory ?? ctx.location.directory).catch(fail(event.type));
      })().catch(() => {});
    return () => controller.abort();
  },
};
