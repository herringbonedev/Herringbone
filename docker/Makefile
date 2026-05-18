.PHONY: update

ELEMENT ?= element

update:
	hbctl stop --element $(ELEMENT);
	docker system prune -f;
	hbctl start --element $(ELEMENT) --no-token-create;
