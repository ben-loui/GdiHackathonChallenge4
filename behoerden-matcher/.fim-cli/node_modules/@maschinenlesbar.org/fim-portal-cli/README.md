# fim-portal-cli

[![CI](https://github.com/maschinenlesbar-org/fim-portal-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/maschinenlesbar-org/fim-portal-cli/actions/workflows/ci.yml)
[![Release](https://github.com/maschinenlesbar-org/fim-portal-cli/actions/workflows/release.yml/badge.svg)](https://github.com/maschinenlesbar-org/fim-portal-cli/actions/workflows/release.yml)
[![npm](https://img.shields.io/npm/v/@maschinenlesbar.org/fim-portal-cli)](https://www.npmjs.com/package/@maschinenlesbar.org/fim-portal-cli)

**Website:** [English](https://maschinenlesbar.org/fim-portal-cli/) · [Deutsch](https://maschinenlesbar.org/fim-portal-cli/de/) — command reference, guides and API docs

Browse Germany's **FIM Portal** — the authoritative catalogue of XDatenfelder schemas,
XZuFi services and XProzess processes — from your terminal. `fim-portal` is a
command-line tool over the [FIM Portal REST API](https://fimportal.de/docs) (`fimportal.de`):
search and download data schemas, data fields, document profiles, service profiles,
service texts and process models — as clean JSON or native XML/PDF you can pipe
straight into [`jq`](https://jqlang.github.io/jq/) or save to a file.

- **Works out of the box** — no account, no API key, no configuration. Install and query.
- **Clean JSON output** — pretty-printed by default, `--compact` for one-line/scripting.
- **Download native artefacts** — XDatenfelder XML, XZuFi XML, XProzess XML and PDF
  exports with a single flag.
- **Covers the catalogue** — XDatenfelder (`schemas`, `fields`, `groups`,
  `document-profiles`), XZuFi (`service-profiles`, `service-texts`,
  `organizational-units`, `specializations`, `online-services`) and XProzess
  (`processes`, `process-classes`).
- **Safe to script** — errors go to stderr, structured exit codes, optional file
  output with `-o`.

> Want to use this as a TypeScript library or understand how it's built?
> See **[DEVELOPING.md](https://github.com/maschinenlesbar-org/fim-portal-cli/blob/main/DEVELOPING.md)**.

## Install

```bash
npm i -g @maschinenlesbar.org/fim-portal-cli
```

This installs the **`fim-portal`** command. Requires **Node.js 22.12+**.

Check it works:

```bash
fim-portal --help
```

## Quickstart

No setup needed — the FIM Portal's open endpoints require no authentication. Your first search:

```bash
fim-portal schemas search --fts-query "Geburt" --is-latest --limit 5
```

The result is a JSON envelope; the matching schemas live under `items`. Pull out just ids and names with `jq`:

```bash
fim-portal schemas search --fts-query "Geburt" --is-latest --limit 5 \
  | jq '.items[] | {id: .fim_id, name, version: .fim_version}'
```

Take a `fim_id` from those results and fetch its full record:

```bash
fim-portal schemas get S07000009
```

## Commands

```text
schemas            search | versions | get | xdf | quality-report
document-profiles  search | versions | get | xdf
fields             search | versions | get | xdf
groups             search | versions | get | xdf
service-profiles   search | get | xzufi | pdf
service-texts      search | get | xzufi | pdf | parsed-xzufi
organizational-units  list | xzufi
specializations       list | xzufi
online-services       list | xzufi
process-classes    search | get | xprozess
processes          search | get | xprozess | report | visualization | visualization-display
code-lists
search-csv
```

`get`, `versions`, `xdf`, `xzufi`, `xprozess`, `pdf`, `report`, `visualization`,
and `visualization-display` take a `<fim_id>` (and optionally a version, defaulting
to `latest`). For `fields` and `groups`, a `<namespace>` argument comes before the
FIM id.

### `schemas search` filters

| Flag | Meaning |
| --- | --- |
| `--fts-query <text>` | free-text search |
| `--suche-nur-in <module>` | restrict FTS to one module (e.g. `Rechtsgrundlagen`) |
| `--name <text>` | name contains |
| `--nummernkreis <prefix>` | owning number range, repeatable, prefix match |
| `--xdf-version <v>` | XDF version: `2.0` or `3.0.0` |
| `--freigabe-status <n>` | approval status `1`–`8`, repeatable |
| `--is-latest` | newest version per id only |
| `--order-by <field>` | sort field (`id_asc`, `name_asc`, `geaendert_datum_zeit_desc`, …) |
| `--limit <n>` | page size (`1`–`200`, default `200`) |
| `--offset <n>` | page offset (0-based) |

The table lists the most-used filters. Each `search` command also accepts more
specialised ones (date windows like `--gueltig-am` / `--updated-since`, status
filters, `--bezeichnung`, `--stichwort`, and others) — run
`fim-portal <group> search --help` for the complete, authoritative list.

The same core filters (`--fts-query`, `--name`, `--nummernkreis`, `--xdf-version`,
`--freigabe-status`, `--is-latest`, `--order-by`, `--limit`, `--offset`) are shared
across `document-profiles search`, `fields search` and `groups search`.

### `fields search` extra filters

| Flag | Meaning |
| --- | --- |
| `--feldart <kind>` | field kind: `input`, `select`, `label`, `hidden`, `locked` |
| `--datentyp <type>` | data type: `text`, `text_latin`, `date`, `time`, `datetime`, `bool`, `num`, `num_int`, `num_currency`, `file`, `obj` |

### `document-profiles search` extra filter

| Flag | Meaning |
| --- | --- |
| `--dokumentart <code>` | document kind code `001`–`014`, `999` |

### `service-profiles search` filters

| Flag | Meaning |
| --- | --- |
| `--fts-query <text>` | free-text search |
| `--sprache <lang>` | language: `Deutsch`, `Englisch`, `Polnisch`, etc. |
| `--sdg-relevant` | only SDG-relevant services |
| `--ozg-themenfeld <field>` | OZG thematic field, repeatable |
| `--leistungsadressat <a>` | service addressee, repeatable |
| `--vollzugsbehoerde <v>` | executing authority: `BAMF`, `BLE`, `DRV` |
| `--einheitlicher-ansprechpartner` | EA-relevant only |
| `--updated-since <iso>` | changed after ISO date |
| `--order-by <field>` | sort field (`relevance`, `titel_asc`, `geaendert_datum_zeit_desc`, …) |
| `--limit <n>` | page size |
| `--offset <n>` | page offset |

### `service-texts search` filters

| Flag | Meaning |
| --- | --- |
| `--fts-query <text>` | free-text search |
| `--source <src>` | `leika`, `landesredaktion`, or `pvog` |
| `--limit <n>` | page size |
| `--offset <n>` | page offset |

`service-texts search` additionally accepts many structured filters
(`--leistungsschluessel`, `--title`, `--leistungstyp`, `--ozg-id`,
`--vollzugsbehoerde`, `--updated-since`, `--order-by`, and more) — run
`fim-portal service-texts search --help` for the full list.

### `processes search` filters

| Flag | Meaning |
| --- | --- |
| `--fts-query <text>` | free-text search |
| `--detaillierungsstufe <n>` | detail level `101`–`105` |
| `--is-musterprozess` | template processes only |
| `--anwendungsgebiet <code>` | application domain `01`–`17` |
| `--freigabe-status <n>` | approval status, repeatable |
| `--limit <n>` | page size |
| `--offset <n>` | page offset |

### `organizational-units list`, `specializations list`, `online-services list` (cursor pagination)

| Flag | Meaning |
| --- | --- |
| `--fts-query <text>` | free-text search (`organizational-units`, `online-services` only) |
| `--limit <n>` | page size |
| `--cursor <n>` | cursor from previous response's `next_cursor` |

### `code-lists` filters

| Flag | Meaning |
| --- | --- |
| `--limit <n>` | page size |
| `--offset <n>` | page offset |

### `search-csv` filters

| Flag | Meaning |
| --- | --- |
| `--resource <name>` | required — `schema`, `document-profile`, `field`, `group`, `leistung-steckbriefe`, `processclass` or `process` |
| `--term <text>` | search term (every resource) |
| `--xdf-version <v>` | XDF version `2.0` or `3.0.0` (`schema`, `document-profile`, `field`, `group`) |
| `--feldart <kind>` | field kind, e.g. `select` (`field`) |
| `--datentyp <type>` | data type, e.g. `text` (`field`) |
| `--dokumentart <code>` | document kind, e.g. `001` (`document-profile`) |
| `--sprache <lang>` | language, e.g. `Englisch` (`leistung-steckbriefe`) |
| `--order-by <field>` | sort order of the resource's JSON search (`name_asc`, `titel_asc`, …); not for `process` or `processclass`, which have none |

`search-csv` wraps `tools/search-csv-download`, whose server rejects nothing: an
unknown `--resource` (such as the plural `schemas`) silently exports Leistungen, and a
filter value it doesn't know (`--feldart SELECT`, `--dokumentart 1`) or a filter for
another resource (`--feldart` with `--resource schema`) is ignored, exporting the
**unfiltered** result. So the CLI checks all of it before any request: the filters
with a known domain take only its values (the error lists them), each filter only the
resources in brackets above, and `--order-by` only the resource's sort orders (the
process resources have none, so it is refused there). A
rejected value or filter is a usage error (exit `1`).

Every option that takes one value is a usage error when given twice
(`--name A --name B` used to search for `B` alone); the repeatable ones say so above.

## Common tasks

A few recipes to get going — see **[Usage.md](https://github.com/maschinenlesbar-org/fim-portal-cli/blob/main/Usage.md)** for the full,
use-case-driven set.

```bash
# Find schemas matching a topic, latest versions only
fim-portal schemas search --fts-query "Geburt" --is-latest --limit 5

# Full schema at a specific version
fim-portal schemas get S07000009 1.0

# Quality report for a schema
fim-portal schemas quality-report S07000009 latest

# Download the XDatenfelder XML to a file
fim-portal -o geburt.xml schemas xdf S07000009 1.0

# Search released text-input fields
fim-portal fields search --feldart input --datentyp text \
  --freigabe-status 5 --freigabe-status 6 --limit 20

# Look up a service profile by keyword
fim-portal service-profiles search --fts-query "Personalausweis" --sprache Deutsch

# Export a service profile as PDF
fim-portal -o leistung.pdf service-profiles pdf 99008001012012 de-DE

# Find template processes at detail level 105
fim-portal processes search --detaillierungsstufe 105 --is-musterprozess --limit 20

# Download a process visualization PDF
fim-portal -o vis.pdf processes visualization 99146014080000 01.00.00 105 17

# Bulk CSV export of field search results
fim-portal -o fields.csv search-csv --resource field --term Name

# Page through organizational units (cursor pagination)
# next_cursor is opaque (not an offset): pass back exactly what the API returned
cursor=$(fim-portal --compact organizational-units list --limit 50 | jq .next_cursor)
fim-portal organizational-units list --cursor "$cursor" --limit 50
```

> The identifiers above (`S07000009`, `99008001012012`, `99146014080000`, etc.) are
> illustrative — substitute ids from a real `search` or `list` result.

## Output & scripting

Every JSON command prints **pretty JSON to stdout**. Download commands (`xdf`,
`xzufi`, `xprozess`, `pdf`, `report`, `visualization`, `visualization-display`,
`search-csv`) stream raw bytes to stdout or to a file with `-o/--output` (`-o -` is
stdout, as in other Unix tools, so a script can pass a variable that defaults to `-`). Errors
and diagnostics go to stderr, so piping stdout into `jq` stays clean.

Each line on stderr is a **log record**: a timestamp (UTC), a level (`ERROR`, `WARN`,
`INFO`) and a topic, the program and the area it comes from (`fim-portal.cli` for usage
errors, `fim-portal.api` for the API's answers, a malformed one included, and a `WARN` when text in
an answer was not valid (invalid bytes, half a character) and was replaced with U+FFFD, `fim-portal.http` for the connection,
`fim-portal.output` for the `Wrote N bytes …` confirmations of downloads and any failure to
write the output, to the `-o` file or to stdout: stdout redirected to a file that fills up or
hits a size limit is an ERROR and exit 1, never half a file with exit 0). By default it
is written log4j style; `--log-format jsonl` writes one JSON object per line instead. A
record is always one line: a line break, a control character or a bidi control in a
message (a server's text, a value you typed) is written as an escape (`\n`, `\u001b`,
`\u202e`), so it can neither split a record nor forge another one, nor steer the terminal;
a message longer than 4000 characters is cut and ends in `… (N more characters)`:

```text
2026-10-09T14:03:12.481Z WARN  [fim-portal.http] requests to mirror.test are sent unencrypted (http:, not https:)
2026-10-09T14:03:12.902Z ERROR [fim-portal.api] HTTP 404 for GET https://fimportal.de/api/v1/schemas/S1/latest: Not Found
```

```bash
fim-portal --log-format jsonl -o geburt.xml schemas xdf S07000009 1.0 2>log.jsonl   # {"ts":"…","level":"INFO","topic":"fim-portal.output","msg":"Wrote … bytes to geburt.xml …"}
```

> **`-o` never overwrites by accident.** An existing file (a dangling symlink too) is
> refused before any request (exit `1`), unless you pass `--force`; a directory is always
> refused, and `--force` without `-o` is a usage error. The write is atomic: the data goes to
> a temporary file beside the target, renamed over it once complete, so a write cut short (a
> full disk) leaves the old file as it was and no half-written or temporary file behind.
> `--force` keeps the old file's mode and writes through a symlink to the file it points at,
> unless another user made the link in a directory others can write to (such as `/tmp`): that
> one is refused (exit `1`), as Linux refuses it to the shell.
> A file that appears while the request runs is not overwritten either (exit `1`, an `ERROR`
> record of `fim-portal.output`). An answer that isn't the data asked for
> fails (exit `1`) without touching the file: an HTML page (a maintenance or proxy
> page) for a download, a JSON body without the documented shape (`null`, `{}`,
> a page without `items`), or one with a number a double can't carry exactly (`1e400`,
> `12345678901234567890`: JSON.parse would print a changed value).

```bash
# How many schemas match a query?
fim-portal schemas search --fts-query "Meldung" | jq '.total_count'

# Pull item summaries from a paginated result
fim-portal --compact fields search --feldart select --limit 50 \
  | jq '.items | length'

# Reshape a service profile (title + service key)
fim-portal service-profiles get 99008001012012 \
  | jq '{title: .title, schluessel: .leistungsschluessel}'
```

Use `--compact` for single-line JSON in pipelines and logs:

```bash
fim-portal --compact schemas search --fts-query "Geburt" --is-latest | jq '.items[0]'
```

`--compact` (and every global option) works **before or after** the command —
both `fim-portal --compact schemas search …` and `fim-portal schemas search … --compact`
do the same thing.

**Exit codes** make the CLI easy to use in scripts:

| Code | Meaning |
| --- | --- |
| `0` | success (also `--help` / `--version`) |
| `4` | resource not found (`404`) |
| `1` | any other error (bad usage / invalid arguments, network failure, server error, unexpected) |

A reader that stops early (`fim-portal … | head`) ends the run quietly with `0`. When
stderr's reader is gone (`2>&1 | true`), a failed run still exits with its own code.

## Troubleshooting

- **`command not found: fim-portal`** — the global npm bin directory isn't on your
  `PATH`. Run `npm prefix -g` and add its `bin` directory (on Windows, the prefix
  itself) to `PATH`, or run via
  `npx @maschinenlesbar.org/fim-portal-cli …`.
- **Exit `4` / "not found"** — the id doesn't exist in the portal. Re-fetch it
  from a fresh `search` result; ids and versions can change as the catalogue updates.
- **Exit `1` / network error** — connectivity, DNS, or a timeout. Try again, or raise
  the limit with `--timeout 60000`.
- **`429` / too many requests** — the portal rate-limits by IP. The CLI retries
  automatically (up to `--max-retries`, default `2`), honouring the server's
  `Retry-After` up to 30 s; the message ends `(after N retries)` when they ran out, so
  wait a moment and retry. When the server asks for a longer wait the CLI does not
  retry at all and says so (`the server asked to retry after 3600 s, longer than the
  30 s the client waits; not retried`): wait that long before trying again.
- **Empty `items` / `total_count: 0`** — the search matched nothing; broaden
  `--fts-query`, drop a filter, or try a different keyword.
- **`-o` write error** — the parent directory must exist and be writable (the file is
  written beside the target and renamed over it); the path is used verbatim with no
  auto-creation, and a missing or read-only directory is refused before any request
  (`Cannot write to "…": the directory "…" does not exist.`). `Refusing to overwrite existing
  file …`: pick another path or add `--force`.
- **XML/PDF to stdout by accident** — download commands (`xdf`, `pdf`, `xprozess`,
  …) stream binary/XML. Always use `-o <file>` unless you intend to pipe the bytes.

## Global options

These apply to every command and may be given **before or after** it:

| Option | Description |
| --- | --- |
| `-V, --version` | Print the version number |
| `-h, --help` | Show help for the program or a command |
| `--compact` | Print JSON on a single line instead of pretty-printed |
| `--log-format <format>` | How errors, warnings and notes are written to stderr: `text` (default; log4j style, `2026-10-09T14:03:12.481Z WARN  [fim-portal.http] …`) or `jsonl` (one JSON object per line: `ts`, `level`, `topic`, `msg`). stdout is not affected |
| `-o, --output <file>` | Write the output (JSON or a download) to a file instead of stdout; `-o -` means stdout (any other value starting with a dash is refused as the next option, so write a file named `-x` as `./-x`). An existing file is refused before any request (exit `1`) unless `--force` is given; a directory, and a file whose directory is missing or not writable, are refused either way. The file is written beside the target and renamed over it when complete, so a write cut short (a full disk) or interrupted (Ctrl-C, `SIGTERM`, `SIGHUP`: exit `130`, `143`, `129`) leaves the old file as it was and no half-written or temporary one. A device, a FIFO or the shell's own descriptor (`/dev/null`, `/dev/stdout`, `>(gzip > x.gz)`) is written in place, without `--force` |
| `--force` | With `-o`: replace an existing file (atomically, keeping its mode; through a symlink to the file it points at, which is created if the link dangles; never through a link another user made in a directory others can write to) |
| `--base-url <url>` | API base URL (default `https://fimportal.de`; `https://schema.fim.fitko.net` also works). Must be an `http:`/`https:` URL spelled `http(s)://` and the host, without a query, a fragment, a backslash, whitespace or control characters, and a `%` in a user name or password must be an escape (write a literal `%` as `%25`) — anything else is rejected at parse time (exit `1`) before any request is made. A plain `http:` URL to a host other than loopback (`localhost`, `127.0.0.0/8`, `::1`) logs one warning on stderr before the first request, a `WARN` record of `fim-portal.http` (`requests to <host> are sent unencrypted (http:, not https:)`) (naming the URL's credentials instead when it carries any, never printing them); stdout and the exit code are unchanged. A `user:password@` in it is shown as `***@` in every message; echoed back by a server (the `Basic` value, `user:password`, the password; for a user name without a password, a token, the user name), it is shown as `***` |
| `--timeout <ms>` | Per-request timeout (default `30000`; at most `2147483647`) |
| `--user-agent <ua>` | `User-Agent` header value |
| `--max-retries <n>` | Retries for transient `429`/`503` responses and reset connections (`0`–`10`, default `2`). Each retry backs off linearly (200 ms, 400 ms, …), or waits the server's `Retry-After` when that is longer (up to 30 s; a longer one is not retried, and the error says so). Timeouts and refused connections are not retried. Each retry logs one WARN record of `fim-portal.http` before it waits (`HTTP 503 from host: retry 1 of 3 in 2 s`) |
| `--max-response-bytes <n>` | Cap response body size in bytes (`0` = unlimited; default 100 MiB) |

## Learn more

- **[SKILLS.md](https://github.com/maschinenlesbar-org/fim-portal-cli/blob/main/SKILLS.md)** — Claude Code Agent Skills that drive this CLI for real-world tasks.
- **[Usage.md](https://github.com/maschinenlesbar-org/fim-portal-cli/blob/main/Usage.md)** — full use-case-driven cookbook.
- **[GLOSSARY.md](https://github.com/maschinenlesbar-org/fim-portal-cli/blob/main/GLOSSARY.md)** — every domain term and flag explained.
- **[DEVELOPING.md](https://github.com/maschinenlesbar-org/fim-portal-cli/blob/main/DEVELOPING.md)** — TypeScript library usage, architecture, testing, CI.

## Data license

This CLI is a **client** — it accesses data it does not own or redistribute. The
upstream data is © its provider and licensed **separately from this tool's code**.
See **[DATA_LICENSE.md](DATA_LICENSE.md)**.

> [!WARNING]
> **Data license not declared by the provider.** FITKO publishes no explicit license
> for the FIM catalogue data (CC0 / DL-DE Zero is only inferred, not confirmed).
> Attribute as good practice and verify with FITKO before commercial reuse.

## License

**Dual-licensed** — use it under **either**:

- **[AGPL-3.0-or-later](LICENSE)** (default, free). Note the AGPL's §13 network
  clause: if you run a modified version as a network service, you must offer that
  modified source to the service's users.
- **Commercial license** (paid), for closed-source / proprietary or SaaS use
  without the AGPL's obligations.

See **[LICENSING.md](LICENSING.md)** for details, and **[CONTRIBUTING.md](CONTRIBUTING.md)**
for the contribution policy (this project does not accept external code
contributions). Commercial enquiries: **sebs@2xs.org**.
