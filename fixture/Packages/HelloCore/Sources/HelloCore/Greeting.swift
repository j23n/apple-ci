/// A greeting, so the fixture has a package to test on Linux and a library for its app.
public enum Greeting {
    public static func text(for name: String) -> String {
        name.isEmpty ? "Hello!" : "Hello, \(name)!"
    }
}
