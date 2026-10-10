# <App>: every command a contributor, an agent and CI run (j23n/apple-ci, README.md).
# The settings, the shared rules (.apple-ci/apple.mk, a copy of apple-ci's make/apple.mk), then
# test, ci-linux and ci-macos, and anything of the app's own.

SHELL := /bin/bash

PROJECT_SPEC := project.yml
XCODEPROJ := App.xcodeproj
SCHEME := App
PLATFORMS := ios mac
SWIFT_PACKAGES := Packages/AppCore

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
