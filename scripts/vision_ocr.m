#import <AppKit/AppKit.h>
#import <Foundation/Foundation.h>
#import <Vision/Vision.h>

static void fail(NSString *message) {
    fprintf(stderr, "%s\n", message.UTF8String);
    exit(1);
}

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        NSMutableArray<NSString *> *inputs = [NSMutableArray array];
        NSString *outputPath = nil;
        for (int index = 1; index < argc; index++) {
            NSString *value = [NSString stringWithUTF8String:argv[index]];
            if ([value isEqualToString:@"--output"] && index + 1 < argc) {
                outputPath = [NSString stringWithUTF8String:argv[++index]];
            } else {
                [inputs addObject:value];
            }
        }
        if (inputs.count == 0) {
            fail(@"usage: vision_ocr [--output FILE] IMAGE [IMAGE ...]");
        }

        NSMutableArray *pages = [NSMutableArray array];
        for (NSString *imagePath in inputs) {
            NSURL *imageURL = [NSURL fileURLWithPath:imagePath];

            VNRecognizeTextRequest *request = [[VNRecognizeTextRequest alloc] init];
            request.revision = VNRecognizeTextRequestRevision3;
            request.recognitionLevel = VNRequestTextRecognitionLevelAccurate;
            request.usesLanguageCorrection = NO;
            request.recognitionLanguages = @[@"en-US"];
            request.customWords = @[@"0", @"1", @"2", @"3", @"4", @"5", @"6", @"7", @"8", @"9", @"10", @"12", @"TAB", @"H.P", @"P"];
            request.minimumTextHeight = 0.003;

            VNImageRequestHandler *handler = [[VNImageRequestHandler alloc] initWithURL:imageURL options:@{}];
            NSError *error = nil;
            if (![handler performRequests:@[request] error:&error]) {
                fail([NSString stringWithFormat:@"Vision OCR failed for %@: %@", imagePath, error]);
            }
            NSMutableArray *items = [NSMutableArray array];
            for (VNRecognizedTextObservation *observation in request.results) {
                VNRecognizedText *candidate = [observation topCandidates:1].firstObject;
                if (!candidate) continue;
                CGRect box = observation.boundingBox;
                [items addObject:@{
                    @"text": candidate.string,
                    @"confidence": @(candidate.confidence),
                    @"bbox": @[@(box.origin.x), @(box.origin.y), @(box.size.width), @(box.size.height)]
                }];
            }
            [pages addObject:@{@"file": imagePath, @"items": items}];
        }

        NSDictionary *root = @{@"version": @1, @"pages": pages};
        NSError *jsonError = nil;
        NSData *data = [NSJSONSerialization dataWithJSONObject:root options:NSJSONWritingPrettyPrinted | NSJSONWritingSortedKeys error:&jsonError];
        if (!data) fail([NSString stringWithFormat:@"JSON encoding failed: %@", jsonError]);
        NSMutableData *withNewline = [data mutableCopy];
        [withNewline appendData:[@"\n" dataUsingEncoding:NSUTF8StringEncoding]];
        if (outputPath) {
            if (![withNewline writeToFile:outputPath options:NSDataWritingAtomic error:&jsonError]) {
                fail([NSString stringWithFormat:@"cannot write %@: %@", outputPath, jsonError]);
            }
        } else {
            [[NSFileHandle fileHandleWithStandardOutput] writeData:withNewline];
        }
    }
    return 0;
}
