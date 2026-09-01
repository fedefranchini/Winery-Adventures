"""Configurazione Sphinx della documentazione di Winery Adventures."""

import sys
from pathlib import Path

# Rende importabile il package locale durante la generazione automatica dell'API.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

project = "Winery Adventures"
author = "MarrasFederico, FedeFranchini"
release = "0.1.0"

# Autodoc legge le docstring, Napoleon interpreta lo stile Google e viewcode
# collega ogni elemento documentato al relativo sorgente Python.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

# Gli artefatti generati non devono essere trattati come sorgenti Sphinx.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

language = "it"
html_theme = "alabaster"
html_static_path = []

# I tipi vengono mostrati insieme alla descrizione dei parametri, separando la
# firma del costruttore dalla documentazione generale della classe.
autodoc_typehints = "description"
autodoc_class_signature = "separated"
napoleon_google_docstring = True
napoleon_numpy_docstring = False
