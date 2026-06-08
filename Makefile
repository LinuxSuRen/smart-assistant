VENV := .venv
PYTHON := $(VENV)/bin/python
UVICORN := $(VENV)/bin/uvicorn
PORT ?= 8000
HOST ?= 0.0.0.0

.PHONY: help install setup-env download-models setup run dev clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: $(VENV) ## Install dependencies (with TTS support)
	$(PYTHON) -m pip install -e ".[tts]"

$(VENV):
	python3 -m venv $(VENV)

setup-env: ## Create .env from .env.example if not present
	@test -f .env || cp .env.example .env
	@echo ".env is ready"

download-models: ## Download ASR and diarization models
	$(PYTHON) scripts/download_models.py

setup: install setup-env download-models ## Full setup (install + env + models)

run: ## Start the server
	$(UVICORN) src.main:app --host $(HOST) --port $(PORT)

dev: ## Start the server with reload
	$(UVICORN) src.main:app --host $(HOST) --port $(PORT) --reload

clean: ## Remove virtual environment
	rm -rf $(VENV)
