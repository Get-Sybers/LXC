SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := conform
MAKEFLAGS += --warn-undefined-variables --no-builtin-rules
SANITY_ENV ?= sanity-py3.13-2.21
.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'
.PHONY: deps
deps:
	python3 -m pip install --quiet -r test-requirements.txt
	ansible-galaxy collection install -r requirements.yml
.PHONY: lint
lint:
	prek run --all-files --show-diff-on-failure
.PHONY: pins
pins:
	python3 scripts/check_pins.py --resolve-git
.PHONY: boundary
boundary:
	python3 scripts/check_lxc_boundary.py
.PHONY: sanity
sanity:
	tox --ansible -e $(SANITY_ENV) --conf tox-ansible.ini
.PHONY: molecule
molecule:
	molecule test --all
.PHONY: changelog
changelog:
	antsibull-changelog lint
.PHONY: build
build:
	ansible-galaxy collection build --force --output-path dist/
.PHONY: conform
conform: lint pins boundary sanity molecule changelog build
	@echo "conform: OK"
.PHONY: upgrade
upgrade:
	python3 scripts/upgrade_pins.py
	$(MAKE) conform
