# Thin wrapper for machines that have make; on Windows use `python run.py film` directly.
PY ?= python
film:      ; $(PY) run.py film
radio:     ; $(PY) run.py radio
smoke:     ; $(PY) run.py smoke
validate:  ; $(PY) run.py validate
setup:     ; $(PY) -m pip install -r requirements.txt
.PHONY: film radio smoke validate setup
