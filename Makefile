# The user documentation: a fresh build with every tutorial executed against the real
# Pulse engine, then opened in the browser. It runs in .venv, the only environment that
# can import PyPulse, so it uses `uv run --no-sync` (never `uv sync`; see README.md).
DOCS_SRC = documentation
DOCS_OUT = documentation/_build
DOCS_INDEX = $(CURDIR)/$(DOCS_OUT)/html/index.html

.PHONY: docs docs-build docs-deps
docs: docs-build
	uv run --no-sync python -m webbrowser -t "file://$(DOCS_INDEX)"

docs-build: docs-deps
	rm -rf $(DOCS_OUT)
	uv run --no-sync sphinx-build -W --keep-going -b html $(DOCS_SRC) $(DOCS_OUT)/html

docs-deps:
	uv pip install --python .venv/bin/python --group docs
