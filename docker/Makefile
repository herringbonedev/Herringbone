.PHONY: update

ELEMENT ?= element

FULL_UPGRADE_ELEMENTS := \
	herringbone-auth \
	herringbone-search \
	herringbone-logs \
	parser-cardset \
	parser-extractor \
	parser-enrichment \
	detectionengine-matcher \
	detectionengine-ruleset \
	incidents-incidentset \
	incidents-correlator \
	incidents-orchestrator \
	detectionengine-detector \
	operations-center \
	logingestion-receiver

FULL_UPGRADE_STOP_ELEMENTS := \
	logingestion-receiver \
	operations-center \
	detectionengine-detector \
	incidents-orchestrator \
	incidents-correlator \
	incidents-incidentset \
	detectionengine-ruleset \
	detectionengine-matcher \
	parser-enrichment \
	parser-extractor \
	parser-cardset \
	herringbone-logs \
	herringbone-search \
	herringbone-auth

FULL_UPGRADE_ALIASES := full-upgrade full-ugrade all
IS_FULL_UPGRADE := $(filter $(ELEMENT),$(FULL_UPGRADE_ALIASES))

update:
	@if [ -n "$(IS_FULL_UPGRADE)" ]; then \
		echo "[make] Full Herringbone upgrade requested: ELEMENT=$(ELEMENT)"; \
		echo "[make] MongoDB is intentionally not stopped."; \
		for element in $(FULL_UPGRADE_STOP_ELEMENTS); do \
			echo "[make] Stopping $$element ..."; \
			hbctl stop --element $$element || true; \
		done; \
		echo "[make] Pruning unused Docker objects ..."; \
		docker system prune -f; \
		for element in $(FULL_UPGRADE_ELEMENTS); do \
			echo "[make] Starting $$element ..."; \
			hbctl start --element $$element --no-token-create; \
		done; \
		echo "[make] Full upgrade complete."; \
	else \
		echo "[make] Updating single element: $(ELEMENT)"; \
		hbctl stop --element $(ELEMENT); \
		docker system prune -f; \
		hbctl start --element $(ELEMENT) --no-token-create; \
	fi