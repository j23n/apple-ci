# apple-ci

The build and CI setup j23n's Apple apps share: [caniretireyet](https://github.com/j23n/caniretireyet), [maestro](https://github.com/j23n/maestro), [makeitrain](https://github.com/j23n/makeitrain) and [omnomnom](https://github.com/j23n/omnomnom). It holds:

- **The build contract:** every app is an XcodeGen project with a Makefile that has the same targets (below).
- **`make/apple.mk`:** the rules the Makefiles share, which each app keeps a copy of.
- **Two reusable workflows:** `linux.yml` and `macos.yml`. An app's CI calls them, and they run `make ci-linux` and `make ci-macos`.
- **`actions/select-xcode`:** picks an installed Xcode by version, or fails with a list of what the runner has.
- **Shared Claude instructions** in `claude/`: the rules every j23n repository's CLAUDE.md imports, and the ones the apps add (below).

## The build contract

- **The project is generated.** The Xcode project comes from an XcodeGen spec (`project.yml`) and is gitignored. Build settings live in the spec or in its `.xcconfig` files, and sources are synchronized folders.
- **`make` is the interface.** Contributors, agents and CI run the same commands, so CI is a `make` call:

| Target | What it does | Where |
| --- | --- | --- |
| `make bootstrap` | First run: the tools (XcodeGen), the project and anything generated the app needs | Mac |
| `make project` | Generates the Xcode project from the spec when the spec is newer | Mac |
| `make test` | The fast tests: the Swift packages and the app's tools | Mac and Linux |
| `make build` | The app for every platform it runs on, unsigned (`build-ios`, `build-mac`) | Mac |
| `make test-app` | The app's own tests in the iOS Simulator or on the Mac; when one fails, the failures with their messages (from the result bundle in `.build/TestResults`, since `-quiet` names the failing tests only) | Mac |
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

**When CI runs:** each job runs once per commit, and macOS only where it's worth it. An app's `ci.yml` triggers on `push`, `pull_request` and `workflow_dispatch`, and the workflows decide:

| | Push to `main` | Push to another branch | Pull request from a branch here | Pull request from a fork | Run by hand |
| --- | --- | --- | --- | --- | --- |
| `linux.yml` | runs | runs | skipped: the push ran it | runs | runs |
| `macos.yml` | runs | skipped: the pull request runs it | runs | runs | runs |

So a work branch gets Linux on every push, the Mac once it has a pull request, and a branch without one can have the Mac by hand (Actions › CI › Run workflow). A skipped job starts no runner. The pull request's merge result isn't tested on Linux, only its branch's last commit.

**Versions:**
- Linux: Swift 6.3, the Swift of the macOS runner's default Xcode.
- macOS: the `macos-26` runner's default Xcode, 26.6 in October 2026.
- A job can pin a version (`xcode: "26.4"`), and fails, listing the installed Xcodes, if the runner doesn't have it. The *Runner inventory* workflow lists what the runners have.
- An app that needs an Xcode the hosted runners don't have yet, such as one built against the iOS 27 SDK, can ask for it with `xcode-missing: skip`. The job then passes with a warning and a note in its summary instead of running, and runs by itself once the runners have that Xcode.
- Moving every app to a new Xcode or Swift is a change of the defaults here.

**Cost:** the hosted runners are free for public repositories. A private one spends its plan's included minutes (2,000 a month on GitHub Free), where a macOS minute counts ten times and every job is rounded up to a whole minute, so a macOS job that only finds its Xcode missing still costs ten minutes. The workflows already run macOS only where it's worth it ("When CI runs"). To turn a job off, use an `if:` on the calling job, which starts no runner, rather than `xcode-missing: skip`, which does: maestro and omnomnom gate their Xcode 27 jobs on a repository variable, `HOSTED_XCODE_27`, until the runners have it.

**Self-test:** apple-ci's own CI runs both workflows on the fixture and tests the Xcode selector, so a change here is checked before the apps pick it up from `main`.

## Claude

Every j23n repository's CLAUDE.md starts with the same shared rules, and the apps add a second layer. The repository's own CLAUDE.md follows them, and only holds what's specific to it:

```markdown
@.apple-ci/claude/j23n.md
@.apple-ci/claude/apps.md

# The app
…
```

| File here | Copy in each repository | What it holds |
| --- | --- | --- |
| `claude/j23n.md` | `.apple-ci/claude/j23n.md` | Every repository: language (US English), commits, branches, issues, pull requests, secrets |
| `claude/apps.md` | `.apple-ci/claude/apps.md` (apps only) | The apps: `make` and CI, the generated project, Swift, signing, FeedbackKit, issues from feedback, Claude on GitHub |
| `claude/link-pr.sh` | `.apple-ci/claude/link-pr.sh` | Links a pull request to the issue it finishes, and checks the link |
| `claude/pull_request_template.md` | `.github/pull_request_template.md` | The pull request description's three sections |

CLAUDE.md can only import files inside its repository, and Claude on GitHub and in cloud sessions sees only the checkout, so each repository keeps copies, as it does of `apple.mk`. Don't edit them: change the files here, then refresh the copies.

- **In an app:** `make update-apple-ci` refreshes `apple.mk` and the Claude files, `apps.md` included.
- **In any other repository** (feedback, feedbackkit): run `curl -fsSL https://raw.githubusercontent.com/j23n/apple-ci/main/claude/update.sh | sh`.
- **Checking:** `… | sh -s -- --check` says which copies differ from apple-ci's. The Linux workflow runs it and warns.

Claude on GitHub runs `link-pr.sh` too, so each app's `claude.yml` allows it next to `gh pr create`. `claude/test-link-pr.sh` tests it with a stand-in for `gh`.
