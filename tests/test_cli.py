import json
from pathlib import Path

from briefquote import cli
from briefquote.llm import FakeClient

ROOT = Path(__file__).parent.parent
SAMPLE_TEXT = (ROOT / "examples" / "sample_extraction.json").read_text(encoding="utf-8")


def test_doctor_absent(monkeypatch, capsys):
    monkeypatch.setenv("OLLAMA_HOST", "127.0.0.1:9")
    code = cli.main(["doctor"])
    out = capsys.readouterr().out
    assert code == 1
    assert "ollama pull" in out


def test_doctor_healthy(monkeypatch, capsys):
    monkeypatch.setattr(
        cli.OllamaClient,
        "health",
        lambda self: {"reachable": True, "models": ["gemma3:4b"], "model_present": True},
    )
    assert cli.main(["doctor"]) == 0


def test_extract_prints_json(monkeypatch, capsys):
    monkeypatch.setattr(cli, "OllamaClient", lambda model=None: FakeClient([SAMPLE_TEXT]))
    code = cli.main(["extract", str(ROOT / "examples" / "briefs" / "saas-dashboard.txt")])
    out = capsys.readouterr().out
    assert code == 0
    assert json.loads(out)["project_type"] == "web"


def test_extract_ollama_absent_clean_error(monkeypatch, capsys):
    monkeypatch.setenv("OLLAMA_HOST", "127.0.0.1:9")
    code = cli.main(["extract", str(ROOT / "examples" / "briefs" / "saas-dashboard.txt")])
    err = capsys.readouterr().err
    assert code == 1
    assert "ollama pull" in err


def test_estimate_no_tabpfn_json(capsys):
    code = cli.main(["estimate", str(ROOT / "examples" / "sample_extraction.json"), "--no-tabpfn", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["estimate"]["method"] == "baseline"


def test_estimate_markdown_default(capsys, monkeypatch):
    # Keep the test fast and offline: pretend TabPFN is unavailable.
    monkeypatch.setattr("builtins.__import__", _block_tabpfn(__import__))
    code = cli.main(["estimate", str(ROOT / "examples" / "sample_extraction.json")])
    assert code == 0
    assert "## Price" in capsys.readouterr().out


def _block_tabpfn(real):
    def fake(name, *a, **k):
        if name == "tabpfn" or name.startswith("tabpfn."):
            raise ImportError("blocked for test")
        return real(name, *a, **k)
    return fake


def test_cli_model_error_no_traceback(monkeypatch, capsys):
    from briefquote.llm import ModelError

    class Boom:
        def complete_json(self, *a, **k):
            raise ModelError("model aborted generation")

    monkeypatch.setattr(cli, "OllamaClient", lambda model=None: Boom())
    code = cli.main(["extract", str(ROOT / "examples" / "briefs" / "saas-dashboard.txt")])
    err = capsys.readouterr().err
    assert code == 1 and err.startswith("error: ") and "Traceback" not in err


def test_force_utf8_output_reconfigures(monkeypatch):
    import io

    buf = io.BytesIO()
    fake = io.TextIOWrapper(buf, encoding="cp1252", errors="strict")
    monkeypatch.setattr(cli.sys, "stdout", fake)
    cli._force_utf8_output()
    print("It\u2019s a scope \u2014 done", file=fake)
    fake.flush()
    assert buf.getvalue().decode("utf-8").strip() == "It\u2019s a scope \u2014 done"


def test_estimate_redirected_stdout_is_utf8(tmp_path):
    import subprocess
    import sys

    out = tmp_path / "out.json"
    with open(out, "wb") as f:
        r = subprocess.run(
            [sys.executable, "-m", "briefquote", "estimate",
             str(ROOT / "examples" / "sample_extraction.json"), "--json", "--no-tabpfn"],
            stdout=f, cwd=ROOT,
        )
    assert r.returncode == 0
    json.loads(out.read_bytes().decode("utf-8"))


def _scope_path():
    return str(ROOT / "examples" / "sample_extraction.json")


def test_bundled_history_warns_on_stderr(capsys):
    code = cli.main(["estimate", _scope_path(), "--no-tabpfn"])
    cap = capsys.readouterr()
    assert code == 0
    assert "--history your_jobs.csv" in cap.err and "synthetic" in cap.err
    assert cap.err.count("\n") == 1
    assert "bundled example jobs (synthetic demo data, replace with your own history)" in cap.out
    assert "synthetic" not in cap.err.split("warning:")[0]


def test_custom_history_no_warning(capsys, tmp_path):
    custom = tmp_path / "mine.csv"
    custom.write_text((ROOT / "data" / "past_jobs.csv").read_text(encoding="utf-8"), encoding="utf-8")
    code = cli.main(["estimate", _scope_path(), "--no-tabpfn", "--history", str(custom)])
    cap = capsys.readouterr()
    assert code == 0
    assert cap.err == ""
    assert "based on 30 past jobs" in cap.out and "synthetic" not in cap.out


def test_serve_warns_for_bundled(monkeypatch, capsys):
    class Srv:
        server_address = ("127.0.0.1", 1)

        def serve_forever(self):
            raise KeyboardInterrupt

        def server_close(self):
            pass

    monkeypatch.setattr("briefquote.web.server.create_server", lambda *a, **k: Srv())
    assert cli.main(["serve", "--demo", "--no-tabpfn"]) == 0
    assert "--history your_jobs.csv" in capsys.readouterr().err
