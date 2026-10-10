import Foundation
import HelloCore
import Testing

/// Runs in the iOS Simulator through xcodebuild, as an app's own tests do.
@Test func greetsInTheSimulator() {
    #expect(Greeting.text(for: "Simulator") == "Hello, Simulator!")
}

/// Fails on purpose when the self-test asks it to (`TEST_RUNNER_HELLO_FAIL=1`), to check that
/// `make test-app` prints why a test failed.
@Test func failsWhenAsked() {
    let asked = ProcessInfo.processInfo.environment["HELLO_FAIL"] == "1"
    #expect(!asked, "failed on purpose for apple-ci's self-test")
}
