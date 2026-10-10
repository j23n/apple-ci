# apple-ci

The build contract, shared Make rules and reusable CI workflows of j23n's Apple apps (caniretireyet, maestro, makeitrain, omnomnom); README.md describes them.

- The apps call the workflows and actions at `@main`, so every change here reaches all four apps on their next run. Keep inputs backward compatible: add inputs with defaults, never rename or remove one without changing every caller in the same piece of work.
- `make/apple.mk` must stay GNU Make 3.81 compatible (macOS's own make): no `.ONESHELL`, `!=` or `$(file ...)`. After changing it, copy it to `fixture/.apple-ci/apple.mk` (the self-test checks they match) and run `make update-apple-ci` in each app.
- The self-test workflow (`.github/workflows/self-test.yml`) runs both workflows on `fixture/`. A change isn't done until it passes.
- Defaults for Swift and Xcode follow the hosted runners: the *Runner inventory* workflow lists what they have. Linux's Swift matches the Swift of the macOS runner's default Xcode.
