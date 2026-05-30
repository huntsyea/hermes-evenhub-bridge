// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "g2-asr-sidecar",
    platforms: [.macOS(.v14)],
    dependencies: [
        .package(url: "https://github.com/FluidInference/FluidAudio.git", "0.14.7"..<"0.15.0"),
    ],
    targets: [
        .executableTarget(
            name: "g2-asr-sidecar",
            dependencies: [.product(name: "FluidAudio", package: "FluidAudio")]
        )
    ]
)
