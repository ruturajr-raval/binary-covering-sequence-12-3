#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace {

constexpr int kN = 12;
constexpr int kRadius = 3;
constexpr int kUniverse = 1 << kN;
constexpr int kBitsetWords = kUniverse / 64;
constexpr int kBallSize = 299;
constexpr uint64_t kChunkSize = 1ULL << 16;

int popcount(uint16_t value) {
    return __builtin_popcount(static_cast<unsigned int>(value));
}

uint64_t mix64(uint64_t value) {
    value += 0x9e3779b97f4a7c15ULL;
    value = (value ^ (value >> 30U)) * 0xbf58476d1ce4e5b9ULL;
    value = (value ^ (value >> 27U)) * 0x94d049bb133111ebULL;
    return value ^ (value >> 31U);
}

uint64_t rotateLeft(uint64_t value, int amount) {
    if (amount == 0) {
        return value;
    }
    return (value << amount) | (value >> (64 - amount));
}

std::string sequenceString(uint64_t bits, int length) {
    std::string result;
    result.reserve(static_cast<std::size_t>(length));
    for (int index = 0; index < length; ++index) {
        result.push_back((bits >> index) & 1ULL ? '1' : '0');
    }
    return result;
}

class CoveringBalls {
public:
    CoveringBalls() {
        bitsets_.fill(0ULL);
        int masks = 0;
        for (int mask = 0; mask < kUniverse; ++mask) {
            if (popcount(static_cast<uint16_t>(mask)) > kRadius) {
                continue;
            }
            ++masks;
            for (int center = 0; center < kUniverse; ++center) {
                const int target = center ^ mask;
                word(center, target >> 6) |=
                    1ULL << (target & 63);
            }
        }
        if (masks != kBallSize) {
            throw std::runtime_error("unexpected radius-3 ball size");
        }
    }

    const uint64_t* bitset(int center) const {
        return bitsets_.data() +
               static_cast<std::size_t>(center) * kBitsetWords;
    }

private:
    uint64_t& word(int center, int block) {
        return bitsets_[
            static_cast<std::size_t>(center) * kBitsetWords + block];
    }

    std::array<uint64_t, kUniverse * kBitsetWords> bitsets_{};
};

bool transformedIsSmaller(
    uint64_t bits,
    int length,
    int offset,
    bool reverse,
    bool complement) {
    for (int index = 0; index < length; ++index) {
        int transformedIndex = 0;
        if (reverse) {
            transformedIndex = offset - index;
            if (transformedIndex < 0) {
                transformedIndex += length;
            }
        } else {
            transformedIndex = offset + index;
            if (transformedIndex >= length) {
                transformedIndex -= length;
            }
        }
        const int current = (bits >> index) & 1ULL;
        const int transformed =
            ((bits >> transformedIndex) & 1ULL) ^
            static_cast<int>(complement);
        if (current != transformed) {
            return transformed < current;
        }
    }
    return false;
}

bool isCanonicalFullSymmetry(uint64_t bits, int length) {
    for (int offset = 1; offset < length; ++offset) {
        if (transformedIsSmaller(
                bits, length, offset, false, false)) {
            return false;
        }
    }
    for (int offset = 0; offset < length; ++offset) {
        if (transformedIsSmaller(
                bits, length, offset, true, false)) {
            return false;
        }
    }
    for (int offset = 0; offset < length; ++offset) {
        if (transformedIsSmaller(
                bits, length, offset, false, true) ||
            transformedIsSmaller(
                bits, length, offset, true, true)) {
            return false;
        }
    }
    return true;
}

std::vector<uint16_t> cyclicWindows(uint64_t bits, int length) {
    std::vector<uint16_t> windows(
        static_cast<std::size_t>(length), 0);
    uint16_t window = 0;
    for (int offset = 0; offset < kN; ++offset) {
        const int position = offset % length;
        window = static_cast<uint16_t>(
            (window << 1U) | ((bits >> position) & 1ULL));
    }
    for (int start = 0; start < length; ++start) {
        windows[static_cast<std::size_t>(start)] = window;
        const int next = (start + kN) % length;
        window = static_cast<uint16_t>(
            ((window << 1U) & (kUniverse - 1)) |
            ((bits >> next) & 1ULL));
    }
    return windows;
}

int uncoveredCount(
    uint64_t bits,
    int length,
    const CoveringBalls& balls) {
    std::array<uint64_t, kBitsetWords> covered{};
    const std::vector<uint16_t> windows =
        cyclicWindows(bits, length);
    for (const uint16_t window : windows) {
        const uint64_t* ball = balls.bitset(window);
        for (int block = 0; block < kBitsetWords; ++block) {
            covered[block] |= ball[block];
        }
    }

    int uncovered = 0;
    for (const uint64_t block : covered) {
        uncovered += __builtin_popcountll(~block);
    }
    return uncovered;
}

struct WorkerResult {
    uint64_t scanned = 0;
    uint64_t canonical = 0;
    uint64_t hashSum = 0;
    uint64_t hashXor = 0;
    int bestUncovered = kUniverse;
    uint64_t bestBits = 0;
    bool foundCover = false;
};

WorkerResult runLength(
    int length,
    int threadCount,
    const CoveringBalls& balls) {
    const uint64_t limit = 1ULL << length;
    std::atomic<uint64_t> next{0};
    std::atomic<uint64_t> scanned{0};
    std::atomic<bool> stop{false};
    std::mutex outputMutex;
    std::vector<WorkerResult> results(
        static_cast<std::size_t>(threadCount));

    const auto worker = [&](int workerIndex) {
        WorkerResult& result =
            results[static_cast<std::size_t>(workerIndex)];
        while (!stop.load(std::memory_order_relaxed)) {
            const uint64_t begin =
                next.fetch_add(kChunkSize, std::memory_order_relaxed);
            if (begin >= limit) {
                break;
            }
            const uint64_t finish =
                std::min(begin + kChunkSize, limit);
            uint64_t processed = 0;
            for (uint64_t bits = begin; bits < finish; ++bits) {
                ++processed;
                ++result.scanned;
                if (!isCanonicalFullSymmetry(bits, length)) {
                    continue;
                }
                ++result.canonical;
                const int uncovered =
                    uncoveredCount(bits, length, balls);
                const uint64_t digest = mix64(
                    bits ^
                    (static_cast<uint64_t>(uncovered) << 48U) ^
                    (static_cast<uint64_t>(length) << 56U));
                result.hashSum += digest;
                result.hashXor ^= rotateLeft(
                    digest,
                    static_cast<int>(bits & 63ULL));
                if (uncovered < result.bestUncovered ||
                    (uncovered == result.bestUncovered &&
                     bits < result.bestBits)) {
                    result.bestUncovered = uncovered;
                    result.bestBits = bits;
                }
                if (uncovered == 0) {
                    result.foundCover = true;
                    stop.store(true, std::memory_order_relaxed);
                    std::lock_guard<std::mutex> lock(outputMutex);
                    std::cout
                        << "{\"event\":\"cover\""
                        << ",\"length\":" << length
                        << ",\"sequence_id\":" << bits
                        << ",\"sequence\":\""
                        << sequenceString(bits, length) << "\""
                        << "}\n"
                        << std::flush;
                    break;
                }
            }
            scanned.fetch_add(
                processed, std::memory_order_relaxed);
        }
    };

    const auto started = std::chrono::steady_clock::now();
    std::vector<std::thread> threads;
    threads.reserve(static_cast<std::size_t>(threadCount));
    for (int index = 0; index < threadCount; ++index) {
        threads.emplace_back(worker, index);
    }

    if (limit >= (1ULL << 28)) {
        uint64_t lastProgress = 0;
        while (!stop.load(std::memory_order_relaxed) &&
               scanned.load(std::memory_order_relaxed) < limit) {
            std::this_thread::sleep_for(std::chrono::seconds(10));
            const uint64_t current =
                scanned.load(std::memory_order_relaxed);
            if (current != lastProgress) {
                const double elapsed =
                    std::chrono::duration<double>(
                        std::chrono::steady_clock::now() - started)
                    .count();
                std::cout
                    << "{\"event\":\"progress\""
                    << ",\"length\":" << length
                    << ",\"scanned\":" << current
                    << ",\"total\":" << limit
                    << ",\"elapsed_seconds\":" << elapsed
                    << "}\n"
                    << std::flush;
                lastProgress = current;
            }
        }
    }
    for (std::thread& thread : threads) {
        thread.join();
    }

    WorkerResult total;
    for (const WorkerResult& result : results) {
        total.scanned += result.scanned;
        total.canonical += result.canonical;
        total.hashSum += result.hashSum;
        total.hashXor ^= result.hashXor;
        if (result.bestUncovered < total.bestUncovered ||
            (result.bestUncovered == total.bestUncovered &&
             result.bestBits < total.bestBits)) {
            total.bestUncovered = result.bestUncovered;
            total.bestBits = result.bestBits;
        }
        total.foundCover = total.foundCover || result.foundCover;
    }
    const double elapsed =
        std::chrono::duration<double>(
            std::chrono::steady_clock::now() - started)
        .count();
    std::cout
        << "{\"event\":\"length_summary\""
        << ",\"length\":" << length
        << ",\"scanned\":" << total.scanned
        << ",\"canonical\":" << total.canonical
        << ",\"hash_sum\":" << total.hashSum
        << ",\"hash_xor\":" << total.hashXor
        << ",\"best_uncovered\":" << total.bestUncovered
        << ",\"best_sequence\":\""
        << sequenceString(total.bestBits, length) << "\""
        << ",\"found_cover\":"
        << (total.foundCover ? "true" : "false")
        << ",\"elapsed_seconds\":" << elapsed
        << "}\n"
        << std::flush;
    return total;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 4) {
            std::cerr
                << "usage: exhaustive MIN_LENGTH "
                << "MAX_LENGTH THREADS\n";
            return 2;
        }
        const int minimumLength = std::stoi(argv[1]);
        const int maximumLength = std::stoi(argv[2]);
        const int threadCount = std::stoi(argv[3]);
        if (minimumLength < 1 ||
            maximumLength < minimumLength ||
            maximumLength > 35) {
            throw std::invalid_argument("invalid length range");
        }
        if (threadCount < 1) {
            throw std::invalid_argument("threads must be positive");
        }

        const CoveringBalls balls;
        uint64_t totalScanned = 0;
        uint64_t totalCanonical = 0;
        for (int length = minimumLength;
             length <= maximumLength;
             ++length) {
            const WorkerResult result =
                runLength(length, threadCount, balls);
            totalScanned += result.scanned;
            totalCanonical += result.canonical;
            if (result.foundCover) {
                break;
            }
        }
        std::cout
            << "{\"event\":\"summary\""
            << ",\"minimum_length\":" << minimumLength
            << ",\"maximum_length\":" << maximumLength
            << ",\"scanned\":" << totalScanned
            << ",\"canonical\":" << totalCanonical
            << "}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "error: " << error.what() << '\n';
        return 2;
    }
}
