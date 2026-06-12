# Command line

The `araclean` command normalizes text from the shell — no Python required. It lives behind the
`[cli]` extra:

```bash
pip install 'araclean[cli]'
```

It is a thin adapter over the same core the Python API uses: arguments are validated once, the
pipeline is built once, then text **streams** through it line by line — so a corpus larger than
memory works without further ceremony. Every flag is listed in the
[CLI reference](../reference/cli.md), which is generated from the command itself.

## Files, stdin, stdout

With no input argument (or `-`), `araclean normalize` reads stdin and writes stdout, so it drops
into a pipe like any Unix tool:

```console
$ printf 'اَلسّلامُ عليكم\nالعـــربية\n' | araclean normalize --profile search
السلام عليكم
العربيه
```

Pass a file to read it, and `--output` to write a file instead of stdout:

```console
$ araclean normalize corpus.txt --profile search --output corpus.clean.txt
```

Line endings are preserved per line, and all I/O is UTF-8.

## Choosing and tuning a profile

`--profile` / `-p` picks the named profile (default `light` — lossless encoding repair). Every
per-knob override from the Python API has a flag twin, and the same validation applies: a flag that
does not apply to the chosen profile is rejected with a clear error *before any input is read*,
never silently ignored.

```console
$ printf '٢٠٢٤\n' | araclean normalize -p ml --map-digits
2024
$ printf 'كِتَابٌ في مَدْرَسَةٍ\n' | araclean normalize -p search --teh-marbuta keep
كتاب في مدرسة
$ printf 'نص\n' | araclean normalize -p light --emoji strip
error: override(s) ['emoji'] do not apply to profile 'light': it has no matching step to configure.
```

See [Tuning profiles](tuning-profiles.md) for what each knob does and which profile owns it.

## JSONL corpora

Most real corpora are JSON Lines. `--jsonl` parses each line as a JSON object, normalizes one
string field in place (default `text`, change it with `--field`), and re-emits the record with
everything else untouched:

```console
$ printf '{"id": 1, "text": "العـــربية"}\n' | araclean normalize --jsonl --field text
{"id": 1, "text": "العربية"}
```

Arabic is emitted verbatim (not `\uXXXX`-escaped). A malformed line — invalid JSON, or a missing /
non-string field — stops the run with an error naming the line number, so a silent half-cleaned
corpus cannot happen. Blank lines pass through unchanged.

## Exit status & errors

| Code | Meaning |
|------|---------|
| `0` | Success. |
| `1` | A streaming failure: unreadable input/output, or an invalid `--jsonl` record. |
| `2` | Invalid options (unknown profile, knob, or value), or the `[cli]` extra is not installed. |

Errors go to stderr; stdout carries only normalized text, so redirecting output stays safe even
when a run fails.
