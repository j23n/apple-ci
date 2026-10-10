import HelloCore
import Testing

/// Runs in the iOS Simulator through xcodebuild, as an app's own tests do.
@Test func greetsInTheSimulator() {
    #expect(Greeting.text(for: "Simulator") == "Hello, Simulator!")
}
