// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "HelloCore",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [.library(name: "HelloCore", targets: ["HelloCore"])],
    targets: [
        .target(name: "HelloCore"),
        .testTarget(name: "HelloCoreTests", dependencies: ["HelloCore"]),
    ]
)
