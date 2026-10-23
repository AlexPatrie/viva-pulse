"""Sphinx configuration for the viva-pulse user documentation.

Build with `make docs` from the repo root. Tutorials are notebooks written in MyST
markdown and executed against the real Pulse engine during the build, in this
project's venv (the only environment that can import PyPulse); a cell that raises
fails the build."""
from importlib.metadata import version as _version

project = "viva-pulse"
author = "Alex Patrie"
copyright = "2026, Alex Patrie. Pulse diagrams: Kitware, Inc. and Contributors (Apache 2.0)"
release = _version("viva-pulse")
version = release

extensions = ["myst_nb", "sphinx.ext.autodoc", "sphinx.ext.napoleon", "sphinx.ext.viewcode"]
exclude_patterns = ["_build", "jupyter_execute", "Thumbs.db", ".DS_Store"]

default_role = "literal"  # the docstrings write `name` for code
autodoc_member_order = "bysource"
autodoc_typehints = "description"
napoleon_google_docstring = False  # the docstrings use numpy-style sections

myst_enable_extensions = ["colon_fence", "deflist"]
myst_heading_anchors = 3
nb_execution_mode = "force"  # every build runs every tutorial against the current code and engine
nb_execution_raise_on_error = True
nb_execution_timeout = 900
nb_execution_show_tb = True
nb_render_markdown_format = "myst"  # Markdown outputs (the generated catalog) contain tables

html_theme = "furo"
html_title = f"viva-pulse {release}"
