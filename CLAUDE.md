@claude/j23n.md

# apple-ci

The build contract, shared Make rules, reusable CI workflows and shared Claude instructions of j23n's Apple apps (caniretireyet, maestro, makeitrain, omnomnom); README.md describes them. Here the shared rules above are the source, `claude/j23n.md`: run `claude/link-pr.sh` where they say `.apple-ci/claude/link-pr.sh`.

- The apps call the workflows and actions at `@main`, so every change here reaches all four apps on their next run. Keep inputs backward compatible: add inputs with defaults, never rename or remove one without changing every caller in the same piece of work.
- `make/apple.mk` must stay GNU Make 3.81 compatible (macOS's own make): no `.ONESHELL`, `!=` or `$(file ...)`. After changing it, copy it to `fixture/.apple-ci/apple.mk` (the self-test checks they match) and run `make update-apple-ci` in each app.
- `claude/` holds the shared CLAUDE.md layers (`j23n.md` for every j23n repository, `apps.md` for the apps), `link-pr.sh` and the pull request template; every repository keeps copies (README.md, "Claude"). After changing one, refresh the copies: `make update-apple-ci` in each app, `claude/update.sh` in feedback and feedbackkit. Keep the shared files short and true for every repository that gets them; what's specific to one belongs in its own CLAUDE.md.
- The self-test workflow (`.github/workflows/self-test.yml`) runs both workflows on `fixture/` and tests `claude/update.sh` and `claude/link-pr.sh`. A change isn't done until it passes.
- Defaults for Swift and Xcode follow the hosted runners: the *Runner inventory* workflow lists what they have. Linux's Swift matches the Swift of the macOS runner's default Xcode.
