# apple-ci

The build and CI setup j23n's Apple apps share: [caniretireyet](https://github.com/j23n/caniretireyet), [maestro](https://github.com/j23n/maestro), [makeitrain](https://github.com/j23n/makeitrain) and [omnomnom](https://github.com/j23n/omnomnom). It holds:

- **The build contract:** every app is an XcodeGen project with a Makefile that has the same targets (below).
- **`make/apple.mk`:** the rules the Makefiles share, which each app keeps a copy of.
- **Two reusable workflows:** `linux.yml` and `macos.yml`. An app's CI calls them, and they run `make ci-linux` and `make ci-macos`.
- **`actions/select-xcode`:** picks an installed Xcode by version, or fails with a list of what the runner has.
- **Shared Claude instructions** in `claude/`: the rules every j23n repository's CLAUDE.md imports, and the ones the apps add (below).

## The build contract

- **The project is generated.** The Xcode project comes from an XcodeGen spec, `project.yml` at the repository's root, so `xcodegen` there (or `make project`) writes it, next to the spec; it's gitignored. Build settings live in the spec or in its `.xcconfig` files, and sources are synchronized folders.
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
| `make signing TEAM=…` | Writes your Apple Developer team into `Signing.xcconfig` (gitignored; "Signing" below) | anywhere |
| `make build-number` | Prints the build number the next build gets: the number of commits on `HEAD` ("Build numbers" below) | anywhere |
| `make update-apple-ci` | Replaces `.apple-ci/` (`apple.mk`, `build-number.sh`, the shared Claude instructions) with apple-ci's current copies | anywhere |

An app adds its own targets next to these, such as `make screenshots`, maestro's content pipeline or omnomnom's food database.

- **Builds are unsigned:** `CODE_SIGNING_ALLOWED=NO`. Mac tests are signed to run locally without a team. The owner's team stays out of git, in `Signing.xcconfig` ("Signing" below).
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

## Signing

Your Apple Developer team lives in `Signing.xcconfig` at the app's root. Git ignores it, XcodeGen never writes it, and every configuration of every target includes it last, so pulling, switching branches and regenerating the project all keep your team, and nothing you'd have to revert ever changes.

- **Once per clone:** `make signing TEAM=ABCDE12345`. It writes the team and keeps whatever else the file holds (maestro's signed entitlements, say).
- **Once per Mac:** put `export J23N_TEAM=ABCDE12345` in your shell's profile. `make project` then writes `Signing.xcconfig` wherever it's missing, in every app.
- **Never by an agent.** In a Claude Code session (`CLAUDECODE` is set) `make signing` refuses and `make project` doesn't write the file, so an agent never sees your team.
- **Not in Xcode's Signing & Capabilities.** A team picked there goes into the generated project, which the next `xcodegen` replaces.
- **How an app includes it:** the `.xcconfig` that every configuration uses (the project's, or the target's) ends with `#include? "<path to the root>/Signing.xcconfig"`, and no target in `project.yml` sets `DEVELOPMENT_TEAM` itself, since a target's own setting would win over the file. The `?` makes the file optional: CI and agents have none, and build unsigned. The fixture's `Config/Project.xcconfig` is the example.
- **Files from before:** an app lists where it used to keep these settings in `SIGNING_OLD`, and `make project` warns while such a file still exists.

## Build numbers

Every build's build number (`CFBundleVersion`) is the number of commits on `HEAD`, so each later commit builds with a higher one, in Xcode, from `make` and in an archive for TestFlight alike. `make build-number` prints it.

- **How:** `.apple-ci/build-number.sh` (a copy of `make/build-number.sh`) runs as the last build phase of every target that ships a bundle (the app and its extensions, which App Store Connect requires to share the app's build number). It sets `CFBundleVersion` in the product's Info.plist with `git rev-list --count HEAD`. `MARKETING_VERSION` stays the version people see.
- **In project.yml,** on each such target:

  ```yaml
      settings:
        base:
          ENABLE_USER_SCRIPT_SANDBOXING: "NO"   # the script reads .git
      postBuildScripts:
        - name: Build number
          script: '"$SRCROOT/.apple-ci/build-number.sh"'
          inputFiles:
            - $(TARGET_BUILD_DIR)/$(INFOPLIST_PATH)   # runs it after Xcode writes the Info.plist
          basedOnDependencyAnalysis: false            # on every build
  ```
- **Archive from `main`.** A branch counts its own commits, so its number can match one `main` gets later. CI's shallow checkouts count only the commits they have, which doesn't matter for builds nobody uploads.
- Without git history the script leaves the number as the project sets it, with a warning.

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

**When CI runs:** Linux once per commit, and macOS only when it's asked for. An app's `ci.yml` triggers on `push`, `pull_request` (with `labeled` among its types) and `workflow_dispatch`, and the workflows decide:

| | Push to `main` | Push to another branch | Pull request from a branch here | Pull request from a fork | Run by hand |
| --- | --- | --- | --- | --- | --- |
| `linux.yml` | runs | runs | skipped: the push ran it | runs | runs |
| `macos.yml` | runs | skipped | runs when it's labeled `ci:mac` | runs when it's labeled `ci:mac` | runs |

- **On a pull request, the review agent decides.** `claude-review.yml` adds the `ci:mac` label when its verdict is pass and the diff touches what only the Mac builds (the app's Swift, `project.yml`, `.xcconfig` files, entitlements, resources, the app's tests). The label's `labeled` event runs the Mac's jobs once, on the pull request's current head. A later push doesn't run them again; the next review relabels it when it's worth it. You can add the label yourself, or run the workflow by hand on any branch (Actions › CI › Run workflow).
- **`main` always gets the Mac,** on every push, so a merge is built and tested there.
- A skipped job starts no runner. The pull request's merge result isn't tested on Linux, only its branch's last commit.
- An app's `ci.yml` puts the label in its concurrency group (`ci-${{ github.ref }}-${{ github.event.label.name }}`), so adding another label to the pull request doesn't cancel the Mac's run. `pull-request-label` names another label.

**Versions:**
- Linux: Swift 6.3, the Swift of the macOS runner's default Xcode.
- macOS: the `macos-26` runner's default Xcode, 26.6 in October 2026.
- A job can pin a version (`xcode: "26.4"`), and fails, listing the installed Xcodes, if the runner doesn't have it. The *Runner inventory* workflow lists what the runners have.
- An app that needs an Xcode the hosted runners don't have yet, such as one built against the iOS 27 SDK, can ask for it with `xcode-missing: skip`. The job then passes with a warning and a note in its summary instead of running, and runs by itself once the runners have that Xcode.
- Moving every app to a new Xcode or Swift is a change of the defaults here.

**Cost:** the hosted runners are free for public repositories. A private one spends its plan's included minutes (2,000 a month on GitHub Free), where a macOS minute counts ten times and every job is rounded up to a whole minute, so a macOS job that only finds its Xcode missing still costs ten minutes. The workflows run macOS only on `main` and when asked for ("When CI runs"). To turn a job off, use an `if:` on the calling job, which starts no runner, rather than `xcode-missing: skip`, which does: maestro and omnomnom gate their Xcode 27 jobs on a repository variable, `HOSTED_XCODE_27`, until the runners have it.

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
| `claude/pull_request_template.md` | `.github/pull_request_template.md` | The pull request description's three sections |

CLAUDE.md can only import files inside its repository, and Claude on GitHub and in cloud sessions sees only the checkout, so each repository keeps copies, as it does of `apple.mk`. Don't edit them: change the files here, then refresh the copies.

- **In an app:** `make update-apple-ci` refreshes `apple.mk` and the Claude files, `apps.md` included.
- **In any other repository** (feedback, feedbackkit): run `curl -fsSL https://raw.githubusercontent.com/j23n/apple-ci/main/claude/update.sh | sh`.
- **Checking:** `… | sh -s -- --check` says which copies differ from apple-ci's. The Linux workflow runs it and warns.
