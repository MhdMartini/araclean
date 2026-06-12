"""The `araclean` command-line interface — one adapter at the facade seam (issue 0020, ADR-0003).

A thin Typer layer over the core: it parses arguments, builds the effective `Pipeline` **once**
through the config trust boundary (`NormalizeConfig`), then streams text through it line by line, so
a corpus larger than memory is cleaned without writing Python (story 45). It holds no normalization
logic — every behavior lives in the deep core, so the CLI is integration-tested by invoking it.

Typer lives behind the optional ``[cli]`` extra (ADR-0003 lean core). This module imports it lazily
inside `build_app` so ``import araclean.cli`` succeeds without the extra; running the CLI without it
prints an actionable "install ``araclean[cli]``" message instead of an ImportError traceback. The
console entry point is `main` (declared in ``[project.scripts]``).
"""

from __future__ import annotations

import contextlib
import json
import sys

# A runtime import (not TYPE_CHECKING-only): Typer evaluates the command annotations at runtime.
from pathlib import Path
from typing import TYPE_CHECKING, cast

from pydantic import ValidationError

from araclean.api import build_pipeline
from araclean.config import ProfileName
from araclean.pipeline import Pipeline
from araclean.steps import (
    CleanMode,
    EmojiMode,
    EmojiSupportNotInstalledError,
    HashtagMode,
    TehMarbutaTarget,
)

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable
    from typing import TextIO

    import typer


_CLI_EXTRA_HINT = (
    "The araclean command-line interface needs the optional [cli] extra (Typer), which is not "
    "installed. Install it with: pip install 'araclean[cli]'."
)


class CLIExtraNotInstalledError(ImportError):
    """Raised when the CLI is built without the optional ``[cli]`` extra (Typer) installed.

    Subclasses `ImportError` (so a caller probing for the capability can catch it); the message
    says how to install it. Mirrors `EmojiSupportNotInstalledError` for the ``[emoji]`` extra.
    """


class _CLIRunError(Exception):
    """An expected, user-facing failure while streaming (bad JSON, a missing field): the command
    turns it into a clear stderr message and a non-zero exit, not a traceback."""


def _normalize_text_line(line: str, pipe: Pipeline) -> str:
    """Normalize one line's content, preserving whether it ended with a newline."""
    if line.endswith("\n"):
        return pipe(line[:-1]) + "\n"
    return pipe(line)


def _normalize_jsonl_line(line: str, pipe: Pipeline, *, field: str, lineno: int) -> str:
    """Normalize the `field` of one JSONL record in place and re-emit it as a JSON object line.

    A blank line passes through unchanged. A line that is not a JSON object, or whose `field` is
    missing or not a string, raises `_CLIRunError` with the line number so the failure is locatable.
    Arabic is emitted verbatim (``ensure_ascii=False``).
    """
    has_newline = line.endswith("\n")
    content = line[:-1] if has_newline else line
    if not content.strip():
        return line
    try:
        parsed: object = json.loads(content)
    except json.JSONDecodeError as exc:
        raise _CLIRunError(f"line {lineno}: invalid JSON: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise _CLIRunError(f"line {lineno}: expected a JSON object, got {type(parsed).__name__}")
    record = cast("dict[str, object]", parsed)
    value = record.get(field)
    if not isinstance(value, str):
        raise _CLIRunError(f"line {lineno}: record has no string field {field!r} to normalize")
    record[field] = pipe(value)
    rendered = json.dumps(record, ensure_ascii=False)
    return rendered + "\n" if has_newline else rendered


def _run(reader: Iterable[str], writer: TextIO, pipe: Pipeline, *, jsonl: bool, field: str) -> None:
    """Stream every line of `reader` through `pipe`, writing each result to `writer`."""
    for lineno, line in enumerate(reader, start=1):
        if jsonl:
            writer.write(_normalize_jsonl_line(line, pipe, field=field, lineno=lineno))
        else:
            writer.write(_normalize_text_line(line, pipe))


@contextlib.contextmanager
def _open_reader(path: Path | None) -> Generator[TextIO, None, None]:
    """Yield the input stream: `path` (UTF-8, universal newlines), or stdin if None or ``-``."""
    if path is None or str(path) == "-":
        yield sys.stdin
    else:
        with open(path, encoding="utf-8") as stream:
            yield stream


@contextlib.contextmanager
def _open_writer(path: Path | None) -> Generator[TextIO, None, None]:
    """Yield the output stream: `path` (UTF-8), or stdout if it is None."""
    if path is None:
        yield sys.stdout
    else:
        with open(path, "w", encoding="utf-8", newline="") as stream:
            yield stream


def build_app() -> typer.Typer:
    """Build the Typer application; requires the ``[cli]`` extra (else `CLIExtraNotInstalledError`).

    Exposed (not just `main`) so the test suite can drive the app with Typer's `CliRunner`.
    """
    try:
        import typer
    except ImportError as exc:
        raise CLIExtraNotInstalledError(_CLI_EXTRA_HINT) from exc

    app = typer.Typer(
        add_completion=False,
        no_args_is_help=True,
        help="araclean — Arabic text normalization and cleaning.",
    )

    # An (empty) callback makes the single `normalize` command addressable by name, so the
    # documented `araclean normalize ...` invocation works rather than collapsing into the app root.
    @app.callback()
    def _root() -> None:  # pyright: ignore[reportUnusedFunction]  # registered via the decorator
        """araclean — clean Arabic text from the shell."""

    @app.command(name="normalize")
    def _normalize(  # pyright: ignore[reportUnusedFunction]  # registered via the decorator
        input_path: Path | None = typer.Argument(
            None, metavar="[INPUT]", help="Input file; reads stdin if omitted or '-'."
        ),
        profile: ProfileName = typer.Option(
            ProfileName.LIGHT, "--profile", "-p", help="Named profile to apply."
        ),
        output: Path | None = typer.Option(
            None, "--output", "-o", help="Write to this file instead of stdout."
        ),
        jsonl: bool = typer.Option(
            False, "--jsonl", help="Treat input as JSONL; normalize --field of each record."
        ),
        field: str = typer.Option(
            "text", "--field", help="JSON field to normalize in --jsonl mode."
        ),
        map_digits: bool | None = typer.Option(
            None, "--map-digits/--no-map-digits", help="ML: also fold digits to ASCII."
        ),
        remove_stopwords: bool | None = typer.Option(
            None,
            "--remove-stopwords/--no-remove-stopwords",
            help="SEARCH: also remove the bundled stopword list (after the folds).",
        ),
        emoji: EmojiMode | None = typer.Option(
            None, "--emoji", help="SOCIAL: keep/strip/demojize."
        ),
        elongation_cap: int | None = typer.Option(
            None, "--elongation-cap", help="SOCIAL: max repeated letters kept."
        ),
        url_mode: CleanMode | None = typer.Option(None, "--url-mode", help="SOCIAL: URL handling."),
        url_token: str | None = typer.Option(None, "--url-token", help="SOCIAL: URL placeholder."),
        mention_mode: CleanMode | None = typer.Option(
            None, "--mention-mode", help="SOCIAL: @mention handling."
        ),
        mention_token: str | None = typer.Option(
            None, "--mention-token", help="SOCIAL: @mention placeholder."
        ),
        hashtag_mode: HashtagMode | None = typer.Option(
            None, "--hashtag-mode", help="SOCIAL: segment/delete/placeholder/keep."
        ),
        hashtag_token: str | None = typer.Option(
            None, "--hashtag-token", help="SOCIAL: #hashtag placeholder."
        ),
        teh_marbuta: TehMarbutaTarget | None = typer.Option(
            None, "--teh-marbuta", help="SEARCH: fold teh marbuta to heh/teh, or keep."
        ),
        tashkeel_classes: str | None = typer.Option(
            None,
            "--tashkeel-classes",
            help="SEARCH/ML/SOCIAL: comma-separated mark classes to remove "
            "(harakat,tanween,shadda,madda,dagger_alef,quranic).",
        ),
        collapse_lines: bool | None = typer.Option(
            None,
            "--collapse-lines/--no-collapse-lines",
            help="Flatten line breaks to spaces, or keep line structure (ADR-0010).",
        ),
    ) -> None:
        """Normalize Arabic text from a file or stdin, writing to a file or stdout."""
        overrides: dict[str, object] = {}
        for key, value in (
            ("map_digits", map_digits),
            ("remove_stopwords", remove_stopwords),
            ("emoji", emoji),
            ("elongation_cap", elongation_cap),
            ("url_mode", url_mode),
            ("url_token", url_token),
            ("mention_mode", mention_mode),
            ("mention_token", mention_token),
            ("hashtag_mode", hashtag_mode),
            ("hashtag_token", hashtag_token),
            ("teh_marbuta", teh_marbuta),
            # The comma-separated CLI string becomes the list the config boundary validates into
            # MarkClass members, so a bad class name fails there with the pydantic error.
            (
                "tashkeel_classes",
                tashkeel_classes and [c.strip() for c in tashkeel_classes.split(",")],
            ),
            ("collapse_lines", collapse_lines),
        ):
            if value is not None:
                overrides[key] = value

        try:
            pipe = build_pipeline(profile.value, overrides)
        except (ValidationError, ValueError, EmojiSupportNotInstalledError) as exc:
            typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=2) from exc

        try:
            with _open_reader(input_path) as reader, _open_writer(output) as writer:
                _run(reader, writer, pipe, jsonl=jsonl, field=field)
        except (_CLIRunError, OSError) as exc:
            typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from exc

    return app


def main() -> None:
    """Console-script entry point (``araclean``). Builds the app and runs it.

    If the ``[cli]`` extra is absent, prints the actionable install hint to stderr and exits
    non-zero instead of dumping an ImportError traceback.
    """
    try:
        app = build_app()
    except CLIExtraNotInstalledError as exc:
        sys.stderr.write(f"{exc}\n")
        raise SystemExit(2) from exc
    app()
