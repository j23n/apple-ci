# Hello: what apple-ci's workflows are tested on, and the build contract's example (README.md).
# Every app's Makefile has this shape: its settings, the shared rules, then test, ci-linux and
# ci-macos, and anything of its own.

SHELL := /bin/bash

PROJECT_SPEC := project.yml
XCODEPROJ := Hello.xcodeproj
SCHEME := Hello
PLATFORMS := ios mac
SWIFT_PACKAGES := Packages/HelloCore

include .apple-ci/apple.mk

.PHONY: help bootstrap test ci-linux ci-macos clean

help:
	@echo "make test       the packages' tests (macOS and Linux)"
	@echo "make build      the app for the iOS Simulator and the Mac, unsigned"
	@echo "make test-app   the app's tests in the iOS Simulator"
	@echo "make ci-linux | ci-macos   what CI runs"

bootstrap: tools project

test: swift-test

ci-linux: test

ci-macos: test build test-app

clean:
	rm -rf $(XCODEPROJ) .build
