import HelloCore
import Testing

@Test func greetsByName() {
    #expect(Greeting.text(for: "Ada") == "Hello, Ada!")
    #expect(Greeting.text(for: "") == "Hello!")
}
