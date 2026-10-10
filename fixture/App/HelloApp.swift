import HelloCore
import SwiftUI

@main
struct HelloApp: App {
    var body: some Scene {
        WindowGroup {
            Text(Greeting.text(for: "apple-ci"))
                .padding()
                .accessibilityIdentifier("hello.greeting")
        }
    }
}
