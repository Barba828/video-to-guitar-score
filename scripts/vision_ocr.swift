#!/usr/bin/env swift
import AppKit
import Foundation
import Vision

var inputs = Array(CommandLine.arguments.dropFirst())
var outputPath: String? = nil
if inputs.count >= 2 && inputs[0] == "--output" {
    outputPath = inputs[1]
    inputs.removeFirst(2)
}
guard !inputs.isEmpty else {
    fputs("usage: vision_ocr.swift [--output FILE] IMAGE [IMAGE ...]\n", stderr)
    exit(2)
}

var pages: [[String: Any]] = []
for imagePath in inputs {
    let url = URL(fileURLWithPath: imagePath)
    guard let image = NSImage(contentsOf: url),
          let data = image.tiffRepresentation,
          let bitmap = NSBitmapImageRep(data: data),
          let cgImage = bitmap.cgImage else {
        fputs("cannot decode \(imagePath)\n", stderr)
        exit(1)
    }
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false
    request.recognitionLanguages = ["en-US"]
    request.customWords = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "12", "TAB", "H.P", "P"]
    request.minimumTextHeight = 0.003
    let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
    do {
        try handler.perform([request])
    } catch {
        fputs("Vision OCR failed for \(imagePath): \(error)\n", stderr)
        exit(1)
    }
    let observations = request.results ?? []
    var items: [[String: Any]] = []
    for observation in observations {
        guard let candidate = observation.topCandidates(1).first else { continue }
        let box = observation.boundingBox
        items.append([
            "text": candidate.string,
            "confidence": Double(candidate.confidence),
            "bbox": [Double(box.origin.x), Double(box.origin.y), Double(box.size.width), Double(box.size.height)]
        ])
    }
    pages.append(["file": imagePath, "items": items])
}

var output = try JSONSerialization.data(withJSONObject: ["version": 1, "pages": pages], options: [.prettyPrinted, .sortedKeys])
output.append(Data("\n".utf8))
if let outputPath {
    try output.write(to: URL(fileURLWithPath: outputPath))
} else {
    FileHandle.standardOutput.write(output)
}
