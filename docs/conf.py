"""Sphinx configuration for the Winery Adventures documentation."""

import sys
from pathlib import Path

# Make the local package importable during automatic API documentation generation.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

project = "Winery Adventures"
author = "MarrasFederico, FedeFranchini"
release = "0.1.0"

# Autodoc reads docstrings, Napoleon interprets Google style, viewcode
# links documented elements to source code, and MyST integrates Markdown guides.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "myst_parser",
]

# Sphinx processes both reStructuredText API pages and Markdown guides.
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# Generated artifacts must not be treated as Sphinx sources.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

language = "en"
html_theme = "alabaster"
html_static_path = []

# Types are shown alongside parameter descriptions, separating the
# constructor signature from the general class documentation.
autodoc_typehints = "description"
autodoc_class_signature = "separated"
napoleon_google_docstring = True
napoleon_numpy_docstring = False
