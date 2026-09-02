#!/usr/bin/env python3
"""
Hermes: simple orchestration script that drives a Codex-style model with a test-feedback loop.
- Requires OPENAI_API_KEY in the environment.
- Expects the model to return a JSON object mapping relative file paths to file contents.

Usage:
  python scripts\hermes\hermes.py --task "Fix failing tests in module X" --max-iter 3

This is a template/starting point — adapt prompts, file selection, and test commands to your repo.
"""

import os
import sys
import subprocess
import json
import argparse

try:
    import openai
except Exception:
    openai = None


def call_model(prompt: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    if openai is None:
        print("ERROR: openai package not installed. Run: pip install openai", file=sys.stderr)
        sys.exit(1)
    openai.api_key = api_key
    model = os.getenv("HERMES_MODEL", "code-davinci-002")
    resp = openai.Completion.create(
        model=model,
        prompt=prompt,
        max_tokens=int(os.getenv("HERMES_MAX_TOKENS", "1500")),
        temperature=float(os.getenv("HERMES_TEMP", "0.2")),
        n=1,
    )
    return resp.choices[0].text


def run_tests() -> (int, str):
    # Run pytest if available; adapt to your repo's test command
    try:
        p = subprocess.run([sys.executable, "-m", "pytest", "-q"], capture_output=True, text=True, timeout=300)
        return p.returncode, p.stdout + p.stderr
    except FileNotFoundError:
        return 0, "pytest not found; skipping tests."
    except subprocess.TimeoutExpired:
        return 1, "Tests timed out."


def apply_code_from_response(text: str) -> (bool, str):
    # Expect the model to return a JSON object mapping file paths to contents.
    body = text.strip()
    # If wrapped in triple-backticks, try to extract inner content
    if body.startswith("```"):
        parts = body.split("```")
        if len(parts) >= 3:
            body = parts[1]
    try:
        data = json.loads(body)
        for path, content in data.items():
            # Ensure the directory exists
            full = os.path.abspath(path)
            d = os.path.dirname(full)
            if d and not os.path.exists(d):
                os.makedirs(d, exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
        return True, ""
    except Exception as e:
        return False, str(e)


def gather_context(max_chars=2000) -> str:
    # Read a small slice of files useful for context (README + tests if present)
    files = ["README.md"]
    ctx = []
    for f in files:
        if os.path.exists(f):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    txt = fh.read()[:max_chars]
                    ctx.append(f"--- {f} ---\n{txt}")
            except Exception:
                pass
    return "\n\n".join(ctx)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--max-iter", type=int, default=3)
    args = parser.parse_args()

    context = gather_context()
    prompt_template = (
        "You are an expert software engineer. Respond ONLY with a valid JSON object whose keys are relative file paths and values are the full contents for those files.\n"
        "Task: {task}\n\nContext:\n{context}\n\nWhen tests fail, produce replacement files to fix the failures. Only return JSON.\n"
    )

    feedback = ""
    last_output = ""
    for i in range(1, args.max_iter + 1):
        prompt = prompt_template.format(task=args.task, context=context)
        if feedback:
            prompt += "\nPrevious test feedback:\n" + feedback
        print(f"[Hermes] Iteration {i}: calling model...", file=sys.stderr)
        resp_text = call_model(prompt)
        ok, err = apply_code_from_response(resp_text)
        if not ok:
            feedback = f"Failed to apply model output: {err}\nModel output:\n{resp_text}"
            print("[Hermes] Apply failed:", err, file=sys.stderr)
            continue
        rc, out = run_tests()
        last_output = out
        if rc == 0:
            print("[Hermes] Tests passed.")
            print(out)
            return
        feedback = f"Exit {rc}. Test output:\n{out}\nPlease produce JSON mapping file paths to file contents that fix the failures." 
        print(f"[Hermes] Tests failed (exit {rc}). Continuing...", file=sys.stderr)

    print("[Hermes] Max iterations reached. Last test output:\n")
    print(last_output)


if __name__ == "__main__":
    main()
