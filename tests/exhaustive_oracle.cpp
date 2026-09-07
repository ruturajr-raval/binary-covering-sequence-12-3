#define main exhaustiveProgramMain
#include "../src/exhaustive.cpp"
#undef main

namespace {

std::vector<uint16_t> directWindows(uint64_t bits, int length) {
    std::vector<uint16_t> windows;
    windows.reserve(static_cast<std::size_t>(length));
    for (int start = 0; start < length; ++start) {
        uint16_t window = 0;
        for (int offset = 0; offset < kN; ++offset) {
            const int position = (start + offset) % length;
            window = static_cast<uint16_t>(
                (window << 1U) | ((bits >> position) & 1ULL));
        }
        windows.push_back(window);
    }
    return windows;
}

int directUncovered(uint64_t bits, int length) {
    const std::vector<uint16_t> windows = directWindows(bits, length);
    int uncovered = 0;
    for (int target = 0; target < kUniverse; ++target) {
        bool covered = false;
        for (const uint16_t window : windows) {
            if (popcount(static_cast<uint16_t>(target) ^ window) <=
                kRadius) {
                covered = true;
                break;
            }
        }
        if (!covered) {
            ++uncovered;
        }
    }
    return uncovered;
}

std::string transformedSequence(
    uint64_t bits,
    int length,
    int offset,
    bool reverse,
    bool complement) {
    std::string result;
    result.reserve(static_cast<std::size_t>(length));
    for (int index = 0; index < length; ++index) {
        const int transformedIndex = reverse
            ? (offset - index + length) % length
            : (offset + index) % length;
        const int value =
            ((bits >> transformedIndex) & 1ULL) ^
            static_cast<int>(complement);
        result.push_back(value ? '1' : '0');
    }
    return result;
}

bool directCanonical(uint64_t bits, int length) {
    const std::string original = sequenceString(bits, length);
    for (const bool reverse : {false, true}) {
        for (const bool complement : {false, true}) {
            for (int offset = 0; offset < length; ++offset) {
                if (transformedSequence(
                        bits,
                        length,
                        offset,
                        reverse,
                        complement) < original) {
                    return false;
                }
            }
        }
    }
    return true;
}

}  // namespace

int main() {
    try {
        const CoveringBalls balls;
        uint64_t checked = 0;
        for (int length = 1; length <= 8; ++length) {
            const uint64_t limit = 1ULL << length;
            for (uint64_t bits = 0; bits < limit; ++bits) {
                if (cyclicWindows(bits, length) !=
                    directWindows(bits, length)) {
                    throw std::runtime_error(
                        "cyclic window oracle mismatch");
                }
                if (uncoveredCount(bits, length, balls) !=
                    directUncovered(bits, length)) {
                    throw std::runtime_error(
                        "coverage oracle mismatch");
                }
                if (isCanonicalFullSymmetry(bits, length) !=
                    directCanonical(bits, length)) {
                    throw std::runtime_error(
                        "canonicality oracle mismatch");
                }
                ++checked;
            }
        }
        std::cout
            << "{\"status\":\"self_test_passed\""
            << ",\"maximum_length\":8"
            << ",\"sequences_checked\":" << checked
            << "}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "error: " << error.what() << '\n';
        return 1;
    }
}
