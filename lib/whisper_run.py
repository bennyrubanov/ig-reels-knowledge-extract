"""faster-whisper (default) or openai-whisper fallback. Canonical for lib/whisper-run.sh."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from local_config import REPO_ROOT, config_root, venv_python, venv_whisper
from tooling import probe_duration

HOTWORDS_FILE = REPO_ROOT / "lib" / "whisper-hotwords.txt"


def _load_hotwords(path: Path) -> str:
    if not path.is_file():
        return ""
    terms: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            terms.append(stripped)
    return ", ".join(terms)


def _apply_hotword_env(root: Path) -> None:
    hw_file = Path(os.environ.get("WHISPER_HOTWORDS_FILE", str(root / "lib" / "whisper-hotwords.txt")))
    if "WHISPER_HOTWORDS" not in os.environ or "WHISPER_INITIAL_PROMPT" not in os.environ:
        terms = _load_hotwords(hw_file)
        os.environ.setdefault("WHISPER_HOTWORDS", terms)
        os.environ.setdefault("WHISPER_INITIAL_PROMPT", terms)


def whisper_transcribe(audio: Path, out_dir: Path, model: str = "small") -> Path | None:
    if not audio.is_file():
        print(f"ERROR: audio file not found: {audio}", file=sys.stderr)
        return None

    root = Path(os.environ.get("SCRIPT_DIR") or config_root())
    if not (root / "lib" / "faster_whisper_transcribe.py").is_file():
        root = REPO_ROOT
    _apply_hotword_env(root)

    out_dir.mkdir(parents=True, exist_ok=True)
    base = audio.stem
    log = out_dir / f"{base}.whisper.log"
    txt = out_dir / f"{base}.txt"
    backend = os.environ.get("WHISPER_BACKEND", "faster")
    python_bin = venv_python()
    if not python_bin.is_file():
        python_bin = Path(sys.executable)
    fw_script = root / "lib" / "faster_whisper_transcribe.py"

    duration_sec = int(probe_duration(audio))
    duration_min = (duration_sec + 59) // 60
    rtf = 6
    engine = "faster-whisper"
    if backend == "openai":
        engine = "openai-whisper"
        rtf = 6 if model == "medium" else 3
    else:
        if model == "medium":
            rtf = 6
        elif model == "base":
            rtf = 12
    est_sec = max(15, duration_sec // rtf + 20)
    est_min = (est_sec + 59) // 60

    header = [
        "=== Transcription ===",
        f"Engine:    {engine}",
        f"Audio:     {audio}",
        f"Duration:  {duration_min}m ({duration_sec}s)",
        f"Model:     {model} (expected RTF ~{rtf}x)",
        f"Estimate:  ~{est_min}m ({est_sec}s wall clock)",
        f"Log:       {log}",
        f"Started:   {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "---",
    ]
    text = "\n".join(header) + "\n"
    log.write_text(text, encoding="utf-8")
    print(text, end="", file=sys.stderr)

    t0 = time.time()
    ok = False
    if backend != "openai":
        if not fw_script.is_file():
            print(
                f"WARNING: faster-whisper script missing ({fw_script}) — falling back to openai-whisper",
                file=sys.stderr,
            )
        else:
            proc = subprocess.run(
                [str(python_bin), str(fw_script), str(audio), str(out_dir), model],
                check=False,
            )
            if proc.returncode == 0 and txt.is_file():
                ok = True
                engine = "faster-whisper"
            else:
                print("WARNING: faster-whisper failed — falling back to openai-whisper", file=sys.stderr)
                with log.open("a", encoding="utf-8") as fh:
                    fh.write("WARNING: faster-whisper failed — falling back to openai-whisper\n")

    if not ok:
        whisper_bin = venv_whisper()
        if not whisper_bin.is_file() and not shutil.which("whisper"):
            print("ERROR: no transcription backend available", file=sys.stderr)
            return None
        exe = str(whisper_bin) if whisper_bin.is_file() else "whisper"
        engine = "openai-whisper (fallback)"
        proc = subprocess.run(
            [
                exe,
                str(audio),
                "--model",
                model,
                "--language",
                "en",
                "--output_format",
                "txt",
                "--output_dir",
                str(out_dir),
                "--verbose",
                "True",
            ],
            check=False,
        )
        if proc.returncode != 0:
            print(f"ERROR: whisper failed — see {log}", file=sys.stderr)
            return None

    elapsed = int(time.time() - t0)
    elapsed_min = (elapsed + 59) // 60
    actual_rtf = duration_sec // elapsed if duration_sec > 0 and elapsed > 0 else 0
    if 0 < actual_rtf < 1:
        actual_rtf = 1
    footer = [
        "---",
        f"Engine:    {engine}",
        f"Finished:  {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Elapsed:   {elapsed_min}m {elapsed}s ({elapsed}s wall)",
        f"RTF:       ~{actual_rtf}x (higher = faster than realtime)",
        f"Transcript: {txt}",
    ]
    block = "\n".join(footer) + "\n"
    with log.open("a", encoding="utf-8") as fh:
        fh.write(block)
    print(block, end="", file=sys.stderr)

    if not txt.is_file():
        print(f"ERROR: transcript not created at {txt}", file=sys.stderr)
        return None
    return txt
