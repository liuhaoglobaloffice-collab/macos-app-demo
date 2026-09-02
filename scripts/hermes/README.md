Hermes — Codex orchestration

What this does
- Provides a minimal orchestration script (scripts/hermes/hermes.py) that calls an OpenAI-style coding model and runs tests in a feedback loop.

Quick start
1. Install dependencies: pip install openai pytest
2. Set API key: set OPENAI_API_KEY=your_key (Windows) or export OPENAI_API_KEY=your_key (macOS/Linux)
3. Run:
   python scripts\hermes\hermes.py --task "Fix failing tests in module X" --max-iter 3

Notes
- The model is expected to return a JSON object mapping file paths to contents. The prompt forces this but real models may include extra text — the script attempts to extract JSON from code fences.
- Adapt the test command in hermes.py (run_tests) to your project's test runner and add any static analysis steps you need.
- Do NOT commit API keys or secrets to the repo. Use repository secrets for CI.
