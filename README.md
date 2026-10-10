# apple-ci

The build and CI setup j23n's Apple apps share: [caniretireyet](https://github.com/j23n/caniretireyet), [maestro](https://github.com/j23n/maestro), [makeitrain](https://github.com/j23n/makeitrain) and [omnomnom](https://github.com/j23n/omnomnom). It holds:

- **The build contract:** every app is an XcodeGen project with a Makefile that has the same targets (below).
- **`make/apple.mk`:** the rules the Makefiles share, which each app keeps a copy of.
- **Two reusable workflows:** `linux.yml` and `macos.yml`. An app's CI calls them, and they run `make ci-linux` and `make ci-macos`.
- **`actions/select-xcode`:** picks an installed Xcode by version, or fails with a list of what the runner has.

## The build contract

- **The project is generated.** The Xcode project comes from an XcodeGen spec (`project.yml`) and is gitignored. Build settings live in the spec or in its `.xcconfig` files, and sources are synchronized folders.
- **`make` is the interface.** Contributors, agents and CI run the same commands, so CI is a `make` call:

| Target | What it does | Where |
| --- | --- | --- |
| `make bootstrap` | First run: the tools (XcodeGen), the project and anything generated the app needs | Mac |
| `make project` | Generates the Xcode project from the spec when the spec is newer | Mac |
| `make test` | The fast tests: the Swift packages and the app's tools | Mac and Linux |
| `make build` | The app for every platform it runs on, unsigned (`build-ios`, `build-mac`) | Mac |
| `make test-app` | The app's own tests in the iOS Simulator or on the Mac | Mac |
| `make ci-linux` | What CI runs on Linux: `test`, plus checks of the app's own | Linux |
| `make ci-macos` | What CI runs on the Mac: `test`, `build`, `test-app`, plus checks of the app's own | Mac |
| `make update-apple-ci` | Replaces `.apple-ci/apple.mk` with apple-ci's current copy | anywhere |

An app adds its own targets next to these, such as `make screenshots`, maestro's content pipeline or omnomnom's food database.

- **Builds are unsigned:** `CODE_SIGNING_ALLOWED=NO`. Mac tests are signed to run locally without a team. Teams, bundle IDs and signing stay with the owner, in gitignored local `.xcconfig` files.
- **In-app feedback** ([FeedbackKit](https://github.com/j23n/feedbackkit)) is compiled in only in Debug builds, behind the `FEEDBACK` compilation condition.

## The Makefile

```make
SHELL := /bin/bash

PROJECT_SPEC := project.yml
XCODEPROJ := App.xcodeproj
SCHEME := App
PLATFORMS := ios mac
SWIFT_PACKAGES := Packages/AppCore

include .apple-ci/apple.mk

test: swift-test
ci-linux: test
ci-macos: test build test-app
```

`.apple-ci/apple.mk` is a copy of [make/apple.mk](make/apple.mk); its header lists the settings an app can change, such as `TEST_APP_PLATFORMS`, `TEST_APP_FLAGS`, `PROJECT_PREREQUISITES` and `IOS_SIMULATOR`. Don't edit the copy. Change it here, then run `make update-apple-ci` in each app. The Linux workflow warns when an app's copy differs from apple-ci's. It's GNU Make 3.81 compatible, since that's the version macOS ships. [fixture/](fixture) is a working example.

## CI

```yaml
jobs:
  linux:
    uses: j23n/apple-ci/.github/workflows/linux.yml@main
  macos:
    uses: j23n/apple-ci/.github/workflows/macos.yml@main
```

[templates/ci.yml](templates/ci.yml) is the whole file. The inputs, with their defaults:

**`linux.yml`** runs `make ci-linux` in `swift:<swift>-noble`. The image comes from Amazon ECR Public's mirror of Docker's official images, because Docker Hub's pull limit used to fail these jobs.

| Input | Default |
| --- | --- |
| `swift` | `6.3` |
| `run` | `make ci-linux` |
| `working-directory` | `.` |
| `apt-packages` | none |
| `uv` | `false` |
| `lfs` | `false` |
| `cache-path` / `cache-key` / `cache-hash-files` | none |
| `name` | `Linux` |

**`macos.yml`** runs `make ci-macos`, after installing XcodeGen with Homebrew and selecting the Xcode.

| Input | Default |
| --- | --- |
| `runner` | `macos-26` |
| `xcode` | `default` (the runner's) |
| `xcode-missing` | `fail` |
| `run` | `make ci-macos` |
| `brew` | `xcodegen` |
| `uv` | `false` |
| `lfs` | `false` |
| `ui-automation` | `false` |
| `artifact-name` / `artifact-path` | none |
| `timeout-minutes` | `60` |

A slower job, such as UI tests with screenshots, is a second `macos.yml` call with its own `run` and artifact.

**Versions:**
- Linux: Swift 6.3, the Swift of the macOS runner's default Xcode.
- macOS: the `macos-26` runner's default Xcode, 26.6 in October 2026.
- A job can pin a version (`xcode: "26.4"`), and fails, listing the installed Xcodes, if the runner doesn't have it. The *Runner inventory* workflow lists what the runners have.
- An app that needs an Xcode the hosted runners don't have yet, such as one built against the iOS 27 SDK, can ask for it with `xcode-missing: skip`. The job then passes with a warning and a note in its summary instead of running, and runs by itself once the runners have that Xcode.
- Moving every app to a new Xcode or Swift is a change of the defaults here.

**Cost:** the hosted runners are free for public repositories. A private one spends its plan's included minutes (2,000 a month on GitHub Free), where a macOS minute counts ten times and every job is rounded up to a whole minute, so a macOS job that only finds its Xcode missing still costs ten minutes. In a private repository, run the Linux job on every push and the macOS jobs only where they're worth it (pushes to `main`, pull requests), and turn a job off with an `if:` on the calling job, which starts no runner, rather than with `xcode-missing: skip`, which does. maestro's CI does both, with a repository variable (`HOSTED_XCODE_27`) for the Xcode it waits for.

**Self-test:** apple-ci's own CI runs both workflows on the fixture and tests the Xcode selector, so a change here is checked before the apps pick it up from `main`.
