import Foundation
import FluidAudio

// Frame = [4-byte big-endian length][payload]. Mirrors asr/ipc.py.

func readN(_ n: Int) -> Data? {
    var data = Data()
    data.reserveCapacity(n)
    let h = FileHandle.standardInput
    while data.count < n {
        let chunk = h.readData(ofLength: n - data.count)
        if chunk.isEmpty { return nil }
        data.append(chunk)
    }
    return data
}

func readFrame() -> Data? {
    guard let header = readN(4) else { return nil }
    let len = header.withUnsafeBytes { $0.load(as: UInt32.self).bigEndian }
    return readN(Int(len))
}

func writeFrame(_ payload: Data) {
    var len = UInt32(payload.count).bigEndian
    var out = Data(bytes: &len, count: 4)
    out.append(payload)
    FileHandle.standardOutput.write(out)
}

func writeJSON(_ obj: [String: Any]) {
    if let data = try? JSONSerialization.data(withJSONObject: obj) {
        writeFrame(data)
    }
}

let args = CommandLine.arguments

func argValue(_ flag: String) -> String? {
    guard let i = args.firstIndex(of: flag), i + 1 < args.count else { return nil }
    return args[i + 1]
}

let versionArg = argValue("--model-version") ?? "v2"

// PCM s16le -> [Float] in [-1, 1]
func pcmToFloats(_ data: Data) -> [Float] {
    data.withUnsafeBytes { raw -> [Float] in
        let s16 = raw.bindMemory(to: Int16.self)
        return s16.map { Float(Int16(littleEndian: $0)) / 32768.0 }
    }
}

@main
struct Sidecar {
    static func main() async {
        do {
            let modelVersion: AsrModelVersion = (versionArg == "v3") ? .v3 : .v2
            let models = try await AsrModels.downloadAndLoad(version: modelVersion)
            let asr = AsrManager(config: .default, models: models)
            var decoderState = TdtDecoderState.make(decoderLayers: models.version.decoderLayers)

            if args.contains("--check") { exit(0) }
            if args.contains("--download") { exit(0) }  // download happened above

            writeJSON(["ready": true, "model": "parakeet-tdt-0.6b-\(versionArg)"])

            while let pcm = readFrame() {
                do {
                    let samples = pcmToFloats(pcm)
                    let result = try await asr.transcribe(samples, decoderState: &decoderState)
                    writeJSON(["text": result.text])
                } catch {
                    writeJSON(["error": "\(error)"])
                }
            }
        } catch {
            if args.contains("--check") || args.contains("--download") { exit(1) }
            writeJSON(["error": "init failed: \(error)"])
            exit(1)
        }
    }
}
