---
description: Deterministic semver release (gate → CHANGELOG fold → commit → tag → CI → publish → verify → optional GitHub Release). Use to publish a project as a versioned release.
arguments:
- project
- bump
- flags
argument-hint: "[project] [bump] [flags]"
---

$project = path del proyecto (default `.`)
$bump = bump: `patch` | `minor` | `major` | `auto` (default `auto`)
$flags = flags: `--gh-release` `--testpypi` `--dry-run` `--skip-gate` `--force`

# Release — $bump en $project

## 0) Localizar y validar
- `cd` a $project. Leer `pyproject.toml`/`package.json`/`Cargo.toml` para nombre. Falta → parar.
- Gate del proyecto: preferir `make ci`; else `just ci`; else `pnpm ci`; else leer README. Ninguno → preguntar.

## 1) Guardas deterministas (abortar si falla, salvo `--force`)
- `git status --porcelain` vacío. Sucio → listar ficheros y **parar** (posible WIP de otro agente; **nunca** `stash`/`clean`/`reset --hard`).
- Sonda de escritura concurrente:
  `h1=$(git diff HEAD|sha256sum); sleep 10; h2=$(git diff HEAD|sha256sum)`; distintas → otro agente escribiendo → **parar**.
- `git fetch --tags --quiet` y `git tag -l "v<NEW>"` vacío (si existe el tag, parar).
- HEAD no por detrás de origin; `git rev-parse origin/<default>` vs `HEAD`.

## 2) Versión
- Leer `## [Unreleased]` del CHANGELOG. Vacío y sin diff vs último tag → "nada que publicar" → parar.
- `auto`: con secciones → `BREAKING`/`!`/`Changed` que altera default → `major` (o `minor` si 0.x); `Added` de API pública → `minor`; solo `Fixed`/interna → `patch`. Razonar y confirmar con `question`.
- NEW = bump(último tag, $bump).

## 3) Gate local (salvo `--skip-gate`)
- Ejecutar el gate del proyecto. Capturar rc + últimas 20 líneas. Rc≠0 → **parar**, no tocar nada.

## 4) CHANGELOG
- Mover contenido de `[Unreleased]` a `[X.Y.Z] - YYYY-MM-DD` (UTC hoy). `[Unreleased]` queda vacío.
- Enlaces: `compare/vX.Y.Z...HEAD` y `releases/tag/vX.Y.Z`.

## 5) Commits convencionales
- Por área (`feat:`/`fix:`/`docs:`/`test:`/`chore:`); si es todo interno, un `chore(release): vNEW` basta.
- **Nunca** stageear secretos: antes de `git add -A`, `git diff --cached --name-only | grep -Ei 'token|\.pem|id_rsa|pypirc|secret'` → si matchea, **parar**. Preferir `git add` con paths explícitos.

## 6) Tag local (sin push)
- `git tag -a vX.Y.Z -m "<name> vX.Y.Z"`.

## 7) Push main + CI
- `git push origin HEAD:<default>`.
- `gh run list --limit 1 --json databaseId -q '.[0].databaseId'` → `gh run watch <id> --exit-status`.
- Rc≠0 → imprimir jobs fallidos y **parar sin publicar**. No subir tag aún.

## 8) Push tag → publicar
- `--dry-run` aquí: imprimir los comandos pendientes y parar.
- `git push origin vX.Y.Z`.
- Poll Release workflow (`gh run list --workflow Release --limit 1`). `gh run watch --exit-status`.
- Fallo con 502/503/timeout/"Package upload appears to have failed": **un** retry: `sleep 45 && gh run rerun <id> --failed && gh run watch <id> --exit-status`. Segundo fallo → log tail y parar.
- `--testpypi`: publicar contra TestPyPI (solo si el proyecto define cómo).

## 9) Verificar registro (números reales)
- Python: `curl -s https://pypi.org/pypi/<name>/json` (poll 4×10 s), `info.version` == `vX.Y.Z`.
- JS: `npm view <name> version`. Rust: `curl -s https://crates.io/api/v1/crates/<name>/versions`.
- Imprimir valor real + status HTTP.

## 10) GitHub Release (opcional, `--gh-release`)
- Extraer sección `## [X.Y.Z]` del CHANGELOG a `/tmp/n.md`.
- `gh release create vX.Y.Z --title "<name> vX.Y.Z" --notes-file /tmp/n.md --latest`.
- Si "already exists": `gh release edit vX.Y.Z --latest=true --verify-tag`.
- Prefiere notes-only si no hay `dist/` limpio del tag.

## 11) Reporte final (con URLs e IDs)
- Registry URL + version + HTTP status.
- URL del run de CI (main) y su conclusión.
- URL del run de release + conclusión.
- URL de GitHub Release (si aplica).
- `git log --oneline -1`, `git status --short` (debe estar limpio).

## Reglas absolutas
- Nunca `--force-push`, nunca reescribir un tag existente en `origin` (`git ls-remote --tags origin | grep vX.Y.Z`). Versiones problemáticas → publicar nueva arriba, no enmendar.
- Nunca pegar secretos en este chat. Si falta uno: instruir al usuario a añadirlo él (env, GitHub secret, PyPI token). No intentes generar/leer secretos.
- Nunca `git clean`/`reset --hard`/`stash` en proyectos ajenos a tu sesión.
- Si un guarda falla (árbol sucio, sonda concurrente, CI rojo, fichero tipo secreto), **para**, explica qué disparó y qué debe hacer el usuario. No "continúes" saltándote el paso.
