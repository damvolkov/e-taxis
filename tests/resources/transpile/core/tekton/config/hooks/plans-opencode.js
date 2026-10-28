// plans — the plans law in OpenCode (plugin API v2: a default export with an id and a setup function).
// When a session goes idle in a project whose .plans/ disagrees with the law, the plugin sends the agent the same list
// the Claude Code Stop hook prints (hooks/plans.mjs, one check for both coders); it sends a list once, so a plan the
// agent cannot fix never loops.

import { audit, message, root } from "../hooks/plans.mjs";

export default {
  id: "plans",
  setup(ctx) {
    const controller = new AbortController();
    const told = new Map();
    void (async () => {
      for await (const event of ctx.event.subscribe({ signal: controller.signal })) {
        if (event.type !== "session.idle") continue;
        const sessionID = event.properties?.sessionID ?? event.sessionID;
        const directory = event.properties?.directory ?? ctx.location.directory;
        if (!sessionID || !directory) continue;
        const problems = audit(root(directory));
        const text = problems.length ? message(problems) : "";
        if (!text || told.get(sessionID) === text) continue;
        told.set(sessionID, text);
        await ctx.session.prompt({ sessionID, text }).catch(() => {});
      }
    })();
    return () => controller.abort();
  },
};
