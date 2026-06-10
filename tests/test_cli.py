"""Behavior of the `araclean` CLI (issue 0020) — a thin adapter at the facade seam.

The CLI holds no normalization logic: it parses arguments, builds the effective pipeline once via
the config trust boundary, and streams text through it. So the tests invoke the app on real
stdin/files and assert the bytes that come out (and that they agree with the `normalize` facade),
never the CLI's internals.
"""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

import araclean.cli as cli
from araclean import normalize

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
app = cli.build_app()

TATWEEL_WORD = "محـــمد"  # محمد written with three tatweel; LIGHT removes them.


def test_normalize_reads_stdin_and_writes_stdout() -> None:
    # The headline story: pipe text in, get normalized text out (no file needed).
    result = runner.invoke(app, ["normalize", "--profile", "light"], input=TATWEEL_WORD + "\n")
    assert result.exit_code == 0
    assert result.stdout == normalize(TATWEEL_WORD, profile="light") + "\n"


def test_no_profile_defaults_to_light() -> None:
    result = runner.invoke(app, ["normalize"], input=TATWEEL_WORD + "\n")
    assert result.exit_code == 0
    assert result.stdout == normalize(TATWEEL_WORD) + "\n"  # default == LIGHT


def test_normalizes_a_file_argument(tmp_path: Path) -> None:
    # `araclean normalize --profile search FILE` normalizes the file's content (story 45).
    line = "على " + TATWEEL_WORD  # search folds maqsura (على->علي) and removes the tatweel
    src = tmp_path / "corpus.txt"
    src.write_text(line + "\n", encoding="utf-8")
    result = runner.invoke(app, ["normalize", "--profile", "search", str(src)])
    assert result.exit_code == 0
    assert result.stdout == normalize(line, profile="search") + "\n"


def test_writes_to_an_output_file(tmp_path: Path) -> None:
    out = tmp_path / "out.txt"
    result = runner.invoke(app, ["normalize", "-o", str(out)], input=TATWEEL_WORD + "\n")
    assert result.exit_code == 0
    assert result.stdout == ""  # nothing on stdout when -o is given
    assert out.read_text(encoding="utf-8") == normalize(TATWEEL_WORD) + "\n"


def test_streams_each_line_independently() -> None:
    # A multi-line corpus is normalized line by line and agrees with the facade per line.
    lines = [TATWEEL_WORD, "على", "abc"]
    result = runner.invoke(app, ["normalize", "--profile", "search"], input="\n".join(lines) + "\n")
    assert result.exit_code == 0
    assert result.stdout == "".join(normalize(line, profile="search") + "\n" for line in lines)


def test_invalid_profile_exits_nonzero_with_a_clear_message() -> None:
    result = runner.invoke(app, ["normalize", "--profile", "nope"], input="x\n")
    assert result.exit_code != 0
    assert "profile" in result.output.lower()


def test_override_that_does_not_apply_exits_nonzero() -> None:
    # `--emoji` on LIGHT has no step to configure: the boundary rejects it (never a silent no-op).
    result = runner.invoke(
        app, ["normalize", "--profile", "light", "--emoji", "strip"], input="x\n"
    )
    assert result.exit_code != 0
    assert "emoji" in result.output


def test_map_digits_override_passes_through_to_the_facade() -> None:
    result = runner.invoke(app, ["normalize", "--profile", "ml", "--map-digits"], input="١٢٣\n")
    assert result.exit_code == 0
    assert result.stdout == normalize("١٢٣", profile="ml", map_digits=True) + "\n"


def test_emoji_override_passes_through_to_the_facade() -> None:
    text = "جميل 😍"
    result = runner.invoke(
        app, ["normalize", "--profile", "social", "--emoji", "strip"], input=text + "\n"
    )
    assert result.exit_code == 0
    assert result.stdout == normalize(text, profile="social", emoji="strip") + "\n"


def test_jsonl_normalizes_the_text_field_and_preserves_the_record() -> None:
    line = json.dumps({"text": TATWEEL_WORD, "id": 7}, ensure_ascii=False) + "\n"
    result = runner.invoke(app, ["normalize", "--jsonl"], input=line)
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"text": normalize(TATWEEL_WORD), "id": 7}


def test_jsonl_honors_a_custom_field() -> None:
    line = json.dumps({"body": TATWEEL_WORD}, ensure_ascii=False) + "\n"
    result = runner.invoke(app, ["normalize", "--jsonl", "--field", "body"], input=line)
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"body": normalize(TATWEEL_WORD)}


def test_jsonl_invalid_json_exits_nonzero_naming_the_line() -> None:
    result = runner.invoke(app, ["normalize", "--jsonl"], input='{"text": "ok"}\nnot json\n')
    assert result.exit_code != 0
    assert "line 2" in result.output


def test_build_app_without_the_cli_extra_raises_a_clear_error() -> None:
    # With Typer unavailable, building the app fails fast with an actionable error naming the extra.
    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(sys.modules, "typer", None)  # make `import typer` fail
        with pytest.raises(cli.CLIExtraNotInstalledError, match=r"araclean\[cli\]"):
            cli.build_app()


def test_main_without_the_cli_extra_exits_nonzero_clearly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(sys.modules, "typer", None)
        with pytest.raises(SystemExit) as excinfo:
            cli.main()
    assert excinfo.value.code != 0
    assert "araclean[cli]" in capsys.readouterr().err
