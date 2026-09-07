#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <exception>
#include <functional>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace {

constexpr int kWordLength = 12;
constexpr int kRadius = 3;
constexpr int kUniverseSize = 1 << kWordLength;
constexpr int kBitsetWords = kUniverseSize / 64;
constexpr int kExpectedBallSize = 299;
constexpr uint64_t kGoldenRatio = 0x9e3779b97f4a7c15ULL;

int popcount16(uint16_t value) {
    return __builtin_popcount(static_cast<unsigned int>(value));
}

int popcount64(uint64_t value) {
    return __builtin_popcountll(value);
}

int trailingZeroes(uint64_t value) {
    return __builtin_ctzll(value);
}

uint64_t splitmix64(uint64_t& state) {
    uint64_t value = (state += kGoldenRatio);
    value = (value ^ (value >> 30U)) * 0xbf58476d1ce4e5b9ULL;
    value = (value ^ (value >> 27U)) * 0x94d049bb133111ebULL;
    return value ^ (value >> 31U);
}

class DeterministicRng {
public:
    explicit DeterministicRng(uint64_t seed) {
        uint64_t state = seed;
        for (uint64_t& word : state_) {
            word = splitmix64(state);
        }
        if ((state_[0] | state_[1] | state_[2] | state_[3]) == 0) {
            state_[0] = kGoldenRatio;
        }
    }

    uint64_t next() {
        const uint64_t result = rotateLeft(state_[1] * 5ULL, 7) * 9ULL;
        const uint64_t temporary = state_[1] << 17U;

        state_[2] ^= state_[0];
        state_[3] ^= state_[1];
        state_[1] ^= state_[2];
        state_[0] ^= state_[3];
        state_[2] ^= temporary;
        state_[3] = rotateLeft(state_[3], 45);
        return result;
    }

    uint64_t bounded(uint64_t bound) {
        if (bound == 0) {
            throw std::invalid_argument("random bound must be positive");
        }
        const uint64_t threshold = static_cast<uint64_t>(-bound) % bound;
        for (;;) {
            const uint64_t value = next();
            if (value >= threshold) {
                return value % bound;
            }
        }
    }

    bool chance(uint64_t numerator, uint64_t denominator) {
        if (numerator > denominator || denominator == 0) {
            throw std::invalid_argument("invalid probability");
        }
        return bounded(denominator) < numerator;
    }

    template <typename T>
    void shuffle(std::vector<T>& values) {
        for (std::size_t index = values.size(); index > 1; --index) {
            const std::size_t other =
                static_cast<std::size_t>(bounded(index));
            std::swap(values[index - 1], values[other]);
        }
    }

private:
    static uint64_t rotateLeft(uint64_t value, int amount) {
        return (value << amount) | (value >> (64 - amount));
    }

    std::array<uint64_t, 4> state_{};
};

uint64_t restartSeed(uint64_t baseSeed, uint64_t restart) {
    uint64_t state = baseSeed ^ (kGoldenRatio * (restart + 1ULL));
    return splitmix64(state);
}

class CoveringBalls {
public:
    CoveringBalls() {
        std::vector<uint16_t> masks;
        masks.reserve(kExpectedBallSize);
        for (int mask = 0; mask < kUniverseSize; ++mask) {
            if (popcount16(static_cast<uint16_t>(mask)) <= kRadius) {
                masks.push_back(static_cast<uint16_t>(mask));
            }
        }
        if (static_cast<int>(masks.size()) != kExpectedBallSize) {
            throw std::runtime_error("unexpected radius-3 ball size");
        }

        members_.resize(
            static_cast<std::size_t>(kUniverseSize) * kExpectedBallSize);
        bitsets_.assign(
            static_cast<std::size_t>(kUniverseSize) * kBitsetWords, 0ULL);

        for (int center = 0; center < kUniverseSize; ++center) {
            uint16_t* output =
                members_.data() +
                static_cast<std::size_t>(center) * kExpectedBallSize;
            uint64_t* bits =
                bitsets_.data() +
                static_cast<std::size_t>(center) * kBitsetWords;
            for (std::size_t index = 0; index < masks.size(); ++index) {
                const uint16_t target =
                    static_cast<uint16_t>(center ^ masks[index]);
                output[index] = target;
                bits[target >> 6U] |= 1ULL << (target & 63U);
            }
        }
    }

    const uint16_t* members(int center) const {
        return members_.data() +
               static_cast<std::size_t>(center) * kExpectedBallSize;
    }

    const uint64_t* bitset(int center) const {
        return bitsets_.data() +
               static_cast<std::size_t>(center) * kBitsetWords;
    }

private:
    std::vector<uint16_t> members_;
    std::vector<uint64_t> bitsets_;
};

struct Options {
    int length = 35;
    uint64_t seed = 1;
    uint64_t restarts = 32;
    uint64_t stepsPerRestart = 10000;
    int candidates = 16;
    uint64_t stagnationSteps = 500;
    uint64_t tabuTenure = 7;
    uint64_t fullScanPeriod = 64;
    uint64_t walkPermille = 40;
    uint64_t progressEvery = 1;
    double timeLimitSeconds = 0.0;
    bool quiet = false;
    bool selfTest = false;
    bool showHelp = false;
    std::string initialSequence;
    std::string verifySequence;
};

uint64_t parseUnsigned(const std::string& text, const std::string& option) {
    std::size_t consumed = 0;
    unsigned long long value = 0;
    try {
        value = std::stoull(text, &consumed, 0);
    } catch (const std::exception&) {
        throw std::invalid_argument("invalid value for " + option + ": " + text);
    }
    if (consumed != text.size()) {
        throw std::invalid_argument("invalid value for " + option + ": " + text);
    }
    return static_cast<uint64_t>(value);
}

double parseDouble(const std::string& text, const std::string& option) {
    std::size_t consumed = 0;
    double value = 0.0;
    try {
        value = std::stod(text, &consumed);
    } catch (const std::exception&) {
        throw std::invalid_argument("invalid value for " + option + ": " + text);
    }
    if (consumed != text.size() || value < 0.0) {
        throw std::invalid_argument("invalid value for " + option + ": " + text);
    }
    return value;
}

std::string optionValue(
    int& index,
    int argc,
    char** argv,
    const std::string& argument,
    const std::string& option) {
    const std::string prefix = option + "=";
    if (argument.rfind(prefix, 0) == 0) {
        return argument.substr(prefix.size());
    }
    if (argument == option) {
        if (index + 1 >= argc) {
            throw std::invalid_argument("missing value for " + option);
        }
        ++index;
        return argv[index];
    }
    return {};
}

bool isBinaryString(const std::string& text) {
    return !text.empty() &&
           std::all_of(text.begin(), text.end(), [](char value) {
               return value == '0' || value == '1';
           });
}

Options parseOptions(int argc, char** argv) {
    Options options;
    for (int index = 1; index < argc; ++index) {
        const std::string argument = argv[index];
        std::string value;

        if (argument == "--help" || argument == "-h") {
            options.showHelp = true;
        } else if (argument == "--quiet") {
            options.quiet = true;
        } else if (argument == "--self-test") {
            options.selfTest = true;
        } else if (!(value = optionValue(
                         index, argc, argv, argument, "--length"))
                        .empty()) {
            const uint64_t parsed = parseUnsigned(value, "--length");
            if (parsed > static_cast<uint64_t>(std::numeric_limits<int>::max())) {
                throw std::invalid_argument("--length is too large");
            }
            options.length = static_cast<int>(parsed);
        } else if (!(value = optionValue(
                         index, argc, argv, argument, "--seed"))
                        .empty()) {
            options.seed = parseUnsigned(value, "--seed");
        } else if (!(value = optionValue(
                         index, argc, argv, argument, "--restarts"))
                        .empty()) {
            options.restarts = parseUnsigned(value, "--restarts");
        } else if (!(value = optionValue(
                         index, argc, argv, argument, "--steps"))
                        .empty()) {
            options.stepsPerRestart = parseUnsigned(value, "--steps");
        } else if (!(value = optionValue(
                         index, argc, argv, argument, "--candidates"))
                        .empty()) {
            const uint64_t parsed = parseUnsigned(value, "--candidates");
            if (parsed > static_cast<uint64_t>(std::numeric_limits<int>::max())) {
                throw std::invalid_argument("--candidates is too large");
            }
            options.candidates = static_cast<int>(parsed);
        } else if (!(value = optionValue(
                         index, argc, argv, argument, "--stagnation"))
                        .empty()) {
            options.stagnationSteps = parseUnsigned(value, "--stagnation");
        } else if (!(value = optionValue(
                         index, argc, argv, argument, "--tabu"))
                        .empty()) {
            options.tabuTenure = parseUnsigned(value, "--tabu");
        } else if (!(value = optionValue(
                         index, argc, argv, argument, "--full-scan-period"))
                        .empty()) {
            options.fullScanPeriod =
                parseUnsigned(value, "--full-scan-period");
        } else if (!(value = optionValue(
                         index, argc, argv, argument, "--walk-permille"))
                        .empty()) {
            options.walkPermille = parseUnsigned(value, "--walk-permille");
        } else if (!(value = optionValue(
                         index, argc, argv, argument, "--progress-every"))
                        .empty()) {
            options.progressEvery = parseUnsigned(value, "--progress-every");
        } else if (!(value = optionValue(
                         index, argc, argv, argument, "--time-limit"))
                        .empty()) {
            options.timeLimitSeconds = parseDouble(value, "--time-limit");
        } else if (!(value = optionValue(
                         index, argc, argv, argument, "--seconds"))
                        .empty()) {
            options.timeLimitSeconds = parseDouble(value, "--seconds");
        } else if (!(value = optionValue(
                         index, argc, argv, argument, "--initial"))
                        .empty()) {
            options.initialSequence = value;
        } else if (!(value = optionValue(
                         index, argc, argv, argument, "--verify"))
                        .empty()) {
            options.verifySequence = value;
        } else {
            throw std::invalid_argument("unknown option: " + argument);
        }
    }

    if (options.length < kWordLength) {
        throw std::invalid_argument("--length must be at least 12");
    }
    if (options.length > 1000000) {
        throw std::invalid_argument("--length exceeds the supported limit");
    }
    if (options.restarts == 0) {
        throw std::invalid_argument("--restarts must be positive");
    }
    if (options.stepsPerRestart == 0) {
        throw std::invalid_argument("--steps must be positive");
    }
    if (options.candidates < 1 || options.candidates > 10000) {
        throw std::invalid_argument("--candidates must be between 1 and 10000");
    }
    if (options.walkPermille > 1000) {
        throw std::invalid_argument("--walk-permille must be at most 1000");
    }
    if (!options.initialSequence.empty()) {
        if (!isBinaryString(options.initialSequence)) {
            throw std::invalid_argument("--initial must contain only 0 and 1");
        }
        if (static_cast<int>(options.initialSequence.size()) != options.length) {
            throw std::invalid_argument(
                "--initial length does not match --length");
        }
    }
    if (!options.verifySequence.empty() &&
        !isBinaryString(options.verifySequence)) {
        throw std::invalid_argument("--verify must contain only 0 and 1");
    }
    if (!options.verifySequence.empty() &&
        static_cast<int>(options.verifySequence.size()) < kWordLength) {
        throw std::invalid_argument("--verify sequence must have length at least 12");
    }
    if (!options.verifySequence.empty() &&
        static_cast<int>(options.verifySequence.size()) != options.length) {
        throw std::invalid_argument(
            "--verify sequence length does not match --length");
    }
    return options;
}

void printHelp() {
    std::cout
        << "Cyclic binary (12,3) covering-sequence construction search\n"
        << "\n"
        << "Options:\n"
        << "  --length N             Sequence length, default 35\n"
        << "  --seed N               Base deterministic seed, default 1\n"
        << "  --restarts N           Random restarts, default 32\n"
        << "  --steps N              Steps per restart, default 10000\n"
        << "  --candidates N         Candidate moves per step, default 16\n"
        << "  --stagnation N         Steps between breakout moves, default 500\n"
        << "  --tabu N               Base tabu tenure, default 7\n"
        << "  --full-scan-period N   Period for all single-bit moves, default 64\n"
        << "  --walk-permille N      Random-walk probability per 1000, default 40\n"
        << "  --time-limit SECONDS   Wall-clock limit, 0 means no limit\n"
        << "  --seconds SECONDS      Alias for --time-limit\n"
        << "  --progress-every N     Restart progress interval, default 1\n"
        << "  --initial BITS         Initial sequence for restart zero\n"
        << "  --verify BITS          Verify one cyclic sequence and exit\n"
        << "  --self-test            Check incremental updates and exit\n"
        << "  --quiet                Suppress progress on stderr\n"
        << "  --help                  Show this help\n";
}

std::vector<uint8_t> bitsFromString(const std::string& sequence) {
    std::vector<uint8_t> bits;
    bits.reserve(sequence.size());
    for (const char value : sequence) {
        bits.push_back(static_cast<uint8_t>(value - '0'));
    }
    return bits;
}

std::string bitsToString(const std::vector<uint8_t>& bits) {
    std::string sequence;
    sequence.reserve(bits.size());
    for (const uint8_t bit : bits) {
        sequence.push_back(static_cast<char>('0' + bit));
    }
    return sequence;
}

uint16_t cyclicWindow(const std::vector<uint8_t>& bits, int start) {
    const int length = static_cast<int>(bits.size());
    uint16_t word = 0;
    for (int offset = 0; offset < kWordLength; ++offset) {
        word = static_cast<uint16_t>(
            (word << 1U) | bits[(start + offset) % length]);
    }
    return word;
}

struct Move {
    std::vector<int> flips;
    std::string kind;
};

void normalizeMove(Move& move) {
    std::sort(move.flips.begin(), move.flips.end());
    std::vector<int> normalized;
    normalized.reserve(move.flips.size());
    for (std::size_t index = 0; index < move.flips.size();) {
        std::size_t end = index + 1;
        while (end < move.flips.size() &&
               move.flips[end] == move.flips[index]) {
            ++end;
        }
        if (((end - index) & 1U) != 0U) {
            normalized.push_back(move.flips[index]);
        }
        index = end;
    }
    move.flips = std::move(normalized);
}

class SearchState {
public:
    SearchState(std::vector<uint8_t> initialBits, const CoveringBalls& balls)
        : bits(std::move(initialBits)),
          windows(bits.size(), 0),
          cover(kUniverseSize, 0U),
          uncoveredPosition(kUniverseSize, -1) {
        rebuild(balls);
    }

    void rebuild(const CoveringBalls& balls) {
        std::fill(cover.begin(), cover.end(), 0U);
        uncovered.clear();
        std::fill(
            uncoveredPosition.begin(), uncoveredPosition.end(), -1);

        for (int start = 0; start < static_cast<int>(bits.size()); ++start) {
            windows[start] = cyclicWindow(bits, start);
            const uint16_t* members = balls.members(windows[start]);
            for (int index = 0; index < kExpectedBallSize; ++index) {
                ++cover[members[index]];
            }
        }
        for (int target = 0; target < kUniverseSize; ++target) {
            if (cover[target] == 0U) {
                addUncovered(static_cast<uint16_t>(target));
            }
        }
    }

    void addUncovered(uint16_t target) {
        if (uncoveredPosition[target] >= 0) {
            throw std::runtime_error("duplicate uncovered target");
        }
        uncoveredPosition[target] = static_cast<int>(uncovered.size());
        uncovered.push_back(target);
    }

    void removeUncovered(uint16_t target) {
        const int position = uncoveredPosition[target];
        if (position < 0) {
            throw std::runtime_error("missing uncovered target");
        }
        const uint16_t last = uncovered.back();
        uncovered[static_cast<std::size_t>(position)] = last;
        uncoveredPosition[last] = position;
        uncovered.pop_back();
        uncoveredPosition[target] = -1;
    }

    std::vector<uint8_t> bits;
    std::vector<uint16_t> windows;
    std::vector<uint32_t> cover;
    std::vector<uint16_t> uncovered;
    std::vector<int> uncoveredPosition;
};

struct MoveScratch {
    explicit MoveScratch(int length)
        : xorMasks(static_cast<std::size_t>(length), 0),
          candidateWindows(static_cast<std::size_t>(length), 0) {}

    std::vector<uint16_t> xorMasks;
    std::vector<int> affectedStarts;
    std::vector<uint16_t> candidateWindows;
    std::array<uint64_t, kBitsetWords> coveredBits{};
    std::array<uint64_t, kBitsetWords> coveredTwiceBits{};
    std::array<uint64_t, kBitsetWords> coveredThreeTimesBits{};
};

void buildCandidateWindows(
    const SearchState& state,
    const Move& move,
    MoveScratch& scratch) {
    std::fill(scratch.xorMasks.begin(), scratch.xorMasks.end(), 0);
    scratch.affectedStarts.clear();
    scratch.candidateWindows = state.windows;
    const int length = static_cast<int>(state.bits.size());

    for (const int position : move.flips) {
        if (position < 0 || position >= length) {
            throw std::runtime_error("move position is outside the sequence");
        }
        for (int offset = 0; offset < kWordLength; ++offset) {
            int start = position - offset;
            if (start < 0) {
                start += length;
            }
            if (scratch.xorMasks[start] == 0U) {
                scratch.affectedStarts.push_back(start);
            }
            scratch.xorMasks[start] ^= static_cast<uint16_t>(
                1U << (kWordLength - 1 - offset));
        }
    }

    for (const int start : scratch.affectedStarts) {
        scratch.candidateWindows[start] ^= scratch.xorMasks[start];
    }
}

struct Score {
    uint64_t weightedUncovered = 0;
    int uncovered = 0;
    int distanceExcess = 0;
    int singlyCovered = 0;
    int doublyCovered = 0;
};

bool betterSearchScore(const Score& left, const Score& right) {
    // Weighted breakout may temporarily trade raw holes to escape a plateau.
    // Retained results use betterResultScore, where raw holes rank first.
    if (left.weightedUncovered != right.weightedUncovered) {
        return left.weightedUncovered < right.weightedUncovered;
    }
    if (left.uncovered != right.uncovered) {
        return left.uncovered < right.uncovered;
    }
    if (left.distanceExcess != right.distanceExcess) {
        return left.distanceExcess < right.distanceExcess;
    }
    if (left.singlyCovered != right.singlyCovered) {
        return left.singlyCovered < right.singlyCovered;
    }
    return left.doublyCovered < right.doublyCovered;
}

bool betterResultScore(const Score& left, const Score& right) {
    if (left.uncovered != right.uncovered) {
        return left.uncovered < right.uncovered;
    }
    if (left.distanceExcess != right.distanceExcess) {
        return left.distanceExcess < right.distanceExcess;
    }
    if (left.singlyCovered != right.singlyCovered) {
        return left.singlyCovered < right.singlyCovered;
    }
    return left.doublyCovered < right.doublyCovered;
}

bool equalScore(const Score& left, const Score& right) {
    return left.weightedUncovered == right.weightedUncovered &&
           left.uncovered == right.uncovered &&
           left.distanceExcess == right.distanceExcess &&
           left.singlyCovered == right.singlyCovered &&
           left.doublyCovered == right.doublyCovered;
}

void checkMultiplicityScore(
    const SearchState& state,
    const Score& score) {
    int singlyCovered = 0;
    int doublyCovered = 0;
    for (const uint32_t count : state.cover) {
        singlyCovered += count == 1U;
        doublyCovered += count == 2U;
    }
    if (score.singlyCovered != singlyCovered ||
        score.doublyCovered != doublyCovered) {
        throw std::runtime_error(
            "bitset multiplicities disagree with exact coverage counts");
    }
}

Score scoreWindows(
    const std::vector<uint16_t>& windows,
    const std::vector<uint32_t>& weights,
    const CoveringBalls& balls,
    MoveScratch& scratch) {
    scratch.coveredBits.fill(0ULL);
    scratch.coveredTwiceBits.fill(0ULL);
    scratch.coveredThreeTimesBits.fill(0ULL);
    for (const uint16_t center : windows) {
        const uint64_t* centerBits = balls.bitset(center);
        for (int index = 0; index < kBitsetWords; ++index) {
            scratch.coveredThreeTimesBits[index] |=
                scratch.coveredTwiceBits[index] & centerBits[index];
            scratch.coveredTwiceBits[index] |=
                scratch.coveredBits[index] & centerBits[index];
            scratch.coveredBits[index] |= centerBits[index];
        }
    }

    Score score;
    for (int block = 0; block < kBitsetWords; ++block) {
        score.singlyCovered += popcount64(
            scratch.coveredBits[block] &
            ~scratch.coveredTwiceBits[block]);
        score.doublyCovered += popcount64(
            scratch.coveredTwiceBits[block] &
            ~scratch.coveredThreeTimesBits[block]);
        uint64_t missing = ~scratch.coveredBits[block];
        while (missing != 0ULL) {
            const int bit = trailingZeroes(missing);
            const int target = block * 64 + bit;
            missing &= missing - 1ULL;
            ++score.uncovered;
            score.weightedUncovered += weights[target];

            int minimumDistance = kWordLength + 1;
            for (const uint16_t center : windows) {
                minimumDistance = std::min(
                    minimumDistance,
                    popcount16(static_cast<uint16_t>(center ^ target)));
            }
            const int excess = minimumDistance - kRadius;
            score.distanceExcess += excess * excess;
        }
    }
    return score;
}

Score evaluateMove(
    const SearchState& state,
    const Move& move,
    const std::vector<uint32_t>& weights,
    const CoveringBalls& balls,
    MoveScratch& scratch) {
    buildCandidateWindows(state, move, scratch);
    return scoreWindows(
        scratch.candidateWindows, weights, balls, scratch);
}

void commitMove(
    SearchState& state,
    const Move& move,
    const CoveringBalls& balls,
    MoveScratch& scratch) {
    buildCandidateWindows(state, move, scratch);

    for (const int start : scratch.affectedStarts) {
        const uint16_t oldCenter = state.windows[start];
        const uint16_t* members = balls.members(oldCenter);
        for (int index = 0; index < kExpectedBallSize; ++index) {
            const uint16_t target = members[index];
            if (state.cover[target] == 0U) {
                throw std::runtime_error("coverage underflow");
            }
            --state.cover[target];
            if (state.cover[target] == 0U) {
                state.addUncovered(target);
            }
        }
    }

    for (const int position : move.flips) {
        state.bits[position] ^= 1U;
    }
    for (const int start : scratch.affectedStarts) {
        state.windows[start] = scratch.candidateWindows[start];
    }

    for (const int start : scratch.affectedStarts) {
        const uint16_t newCenter = state.windows[start];
        const uint16_t* members = balls.members(newCenter);
        for (int index = 0; index < kExpectedBallSize; ++index) {
            const uint16_t target = members[index];
            if (state.cover[target] == 0U) {
                state.removeUncovered(target);
            }
            ++state.cover[target];
        }
    }
}

uint16_t pickUncoveredTarget(
    const SearchState& state,
    const std::vector<uint32_t>& weights,
    DeterministicRng& rng) {
    if (state.uncovered.empty()) {
        throw std::runtime_error("cannot choose from an empty uncovered set");
    }
    uint16_t selected = state.uncovered[static_cast<std::size_t>(
        rng.bounded(state.uncovered.size()))];
    const int samples = std::min<int>(
        8, static_cast<int>(state.uncovered.size()));
    for (int sample = 1; sample < samples; ++sample) {
        const uint16_t candidate =
            state.uncovered[static_cast<std::size_t>(
                rng.bounded(state.uncovered.size()))];
        if (weights[candidate] > weights[selected]) {
            selected = candidate;
        }
    }
    return selected;
}

struct WindowChoice {
    int start = 0;
    int distance = kWordLength + 1;
};

WindowChoice chooseCloseWindow(
    const SearchState& state,
    uint16_t target,
    DeterministicRng& rng) {
    int minimumDistance = kWordLength + 1;
    std::vector<int> distances(state.windows.size(), 0);
    for (int start = 0; start < static_cast<int>(state.windows.size()); ++start) {
        distances[start] =
            popcount16(static_cast<uint16_t>(state.windows[start] ^ target));
        minimumDistance = std::min(minimumDistance, distances[start]);
    }

    const int slack = rng.chance(1, 4) ? 1 : 0;
    std::vector<int> choices;
    for (int start = 0; start < static_cast<int>(state.windows.size()); ++start) {
        if (distances[start] <= minimumDistance + slack) {
            choices.push_back(start);
        }
    }
    const int start =
        choices[static_cast<std::size_t>(rng.bounded(choices.size()))];
    return {start, distances[start]};
}

std::vector<int> mismatchPositions(
    const SearchState& state,
    uint16_t target,
    int start) {
    const int length = static_cast<int>(state.bits.size());
    std::vector<int> positions;
    positions.reserve(kWordLength);
    for (int offset = 0; offset < kWordLength; ++offset) {
        const int position = (start + offset) % length;
        const uint8_t targetBit = static_cast<uint8_t>(
            (target >> (kWordLength - 1 - offset)) & 1U);
        if (state.bits[position] != targetBit) {
            positions.push_back(position);
        }
    }
    return positions;
}

Move makeSingleBitMove(
    const SearchState& state,
    DeterministicRng& rng,
    const std::string& kind = "single") {
    Move move;
    move.kind = kind;
    move.flips.push_back(static_cast<int>(rng.bounded(state.bits.size())));
    return move;
}

Move makeTargetRepairMove(
    const SearchState& state,
    const std::vector<uint32_t>& weights,
    DeterministicRng& rng) {
    if (state.uncovered.empty()) {
        return makeSingleBitMove(state, rng, "single");
    }
    const uint16_t target = pickUncoveredTarget(state, weights, rng);
    const WindowChoice choice = chooseCloseWindow(state, target, rng);
    std::vector<int> mismatches =
        mismatchPositions(state, target, choice.start);
    rng.shuffle(mismatches);

    int required = std::max(1, choice.distance - kRadius);
    required = std::min(required, static_cast<int>(mismatches.size()));
    if (required < static_cast<int>(mismatches.size()) &&
        rng.chance(1, 5)) {
        ++required;
    }

    Move move;
    move.kind = "target_repair";
    move.flips.insert(
        move.flips.end(), mismatches.begin(), mismatches.begin() + required);
    normalizeMove(move);
    if (move.flips.empty()) {
        return makeSingleBitMove(state, rng, "single_fallback");
    }
    return move;
}

Move makeTargetedSingleMove(
    const SearchState& state,
    const std::vector<uint32_t>& weights,
    DeterministicRng& rng) {
    if (state.uncovered.empty()) {
        return makeSingleBitMove(state, rng, "single");
    }
    const uint16_t target = pickUncoveredTarget(state, weights, rng);
    const WindowChoice choice = chooseCloseWindow(state, target, rng);
    std::vector<int> mismatches =
        mismatchPositions(state, target, choice.start);
    if (mismatches.empty()) {
        return makeSingleBitMove(state, rng, "single_fallback");
    }
    Move move;
    move.kind = "target_single";
    move.flips.push_back(
        mismatches[static_cast<std::size_t>(rng.bounded(mismatches.size()))]);
    return move;
}

Move makeRandomMultiMove(
    const SearchState& state,
    DeterministicRng& rng,
    int minimumBits,
    int maximumBits,
    const std::string& kind = "multi") {
    const int length = static_cast<int>(state.bits.size());
    maximumBits = std::min(maximumBits, length);
    minimumBits = std::min(minimumBits, maximumBits);
    const int count = minimumBits + static_cast<int>(
        rng.bounded(static_cast<uint64_t>(maximumBits - minimumBits + 1)));

    Move move;
    move.kind = kind;
    std::vector<uint8_t> selected(static_cast<std::size_t>(length), 0);
    const bool clustered = count <= 8 && rng.chance(1, 2);
    const int clusterStart =
        clustered ? static_cast<int>(rng.bounded(state.bits.size())) : 0;
    const int clusterWidth = std::min(length, std::max(count, 12));

    while (static_cast<int>(move.flips.size()) < count) {
        int position = 0;
        if (clustered) {
            position = (clusterStart +
                        static_cast<int>(rng.bounded(
                            static_cast<uint64_t>(clusterWidth)))) %
                       length;
        } else {
            position = static_cast<int>(rng.bounded(state.bits.size()));
        }
        if (selected[position] == 0U) {
            selected[position] = 1U;
            move.flips.push_back(position);
        }
    }
    normalizeMove(move);
    return move;
}

Move makeSegmentMove(
    const SearchState& state,
    DeterministicRng& rng) {
    const int length = static_cast<int>(state.bits.size());
    const int operation = static_cast<int>(rng.bounded(3));
    const int maximumLength = std::min(length, 16);
    const int minimumLength = operation == 0 ? 2 : 3;
    const int segmentLength = minimumLength + static_cast<int>(
        rng.bounded(
            static_cast<uint64_t>(maximumLength - minimumLength + 1)));
    const int start = static_cast<int>(rng.bounded(state.bits.size()));

    Move move;
    if (operation == 0) {
        move.kind = "segment_invert";
        for (int offset = 0; offset < segmentLength; ++offset) {
            move.flips.push_back((start + offset) % length);
        }
    } else if (operation == 1) {
        move.kind = "segment_reverse";
        for (int offset = 0; offset < segmentLength / 2; ++offset) {
            const int left = (start + offset) % length;
            const int right =
                (start + segmentLength - 1 - offset) % length;
            if (state.bits[left] != state.bits[right]) {
                move.flips.push_back(left);
                move.flips.push_back(right);
            }
        }
    } else {
        move.kind = "segment_rotate";
        std::vector<uint8_t> oldBits(
            static_cast<std::size_t>(segmentLength), 0);
        for (int offset = 0; offset < segmentLength; ++offset) {
            oldBits[offset] = state.bits[(start + offset) % length];
        }
        for (int offset = 0; offset < segmentLength; ++offset) {
            const uint8_t newBit =
                oldBits[(offset + 1) % segmentLength];
            const int position = (start + offset) % length;
            if (state.bits[position] != newBit) {
                move.flips.push_back(position);
            }
        }
    }

    normalizeMove(move);
    if (move.flips.empty()) {
        return makeRandomMultiMove(
            state, rng, 2, std::min(5, length), "segment_fallback");
    }
    return move;
}

bool sameMove(const Move& left, const Move& right) {
    return left.flips == right.flips;
}

void addCandidate(std::vector<Move>& candidates, Move move) {
    normalizeMove(move);
    if (move.flips.empty()) {
        return;
    }
    for (const Move& existing : candidates) {
        if (sameMove(existing, move)) {
            return;
        }
    }
    candidates.push_back(std::move(move));
}

std::vector<Move> generateCandidates(
    const SearchState& state,
    const std::vector<uint32_t>& weights,
    const Options& options,
    uint64_t step,
    DeterministicRng& rng) {
    std::vector<Move> candidates;
    candidates.reserve(
        static_cast<std::size_t>(options.candidates) + state.bits.size());

    for (int index = 0; index < options.candidates; ++index) {
        switch (index % 10) {
            case 0:
            case 1:
            case 2:
            case 3:
            case 4:
                addCandidate(
                    candidates,
                    makeTargetRepairMove(state, weights, rng));
                break;
            case 5:
                addCandidate(
                    candidates,
                    makeTargetedSingleMove(state, weights, rng));
                break;
            case 6:
                addCandidate(candidates, makeSingleBitMove(state, rng));
                break;
            case 7:
            case 8:
                addCandidate(
                    candidates,
                    makeRandomMultiMove(state, rng, 2, 6));
                break;
            case 9:
                addCandidate(candidates, makeSegmentMove(state, rng));
                break;
            default:
                break;
        }
    }

    if (options.fullScanPeriod > 0 &&
        step % options.fullScanPeriod == 0) {
        for (int position = 0;
             position < static_cast<int>(state.bits.size());
             ++position) {
            Move move;
            move.kind = "single_scan";
            move.flips.push_back(position);
            addCandidate(candidates, std::move(move));
        }
    }

    if (candidates.empty()) {
        addCandidate(candidates, makeSingleBitMove(state, rng));
    }
    return candidates;
}

bool moveIsTabu(
    const Move& move,
    const std::vector<uint64_t>& tabuUntil,
    uint64_t step) {
    for (const int position : move.flips) {
        if (tabuUntil[position] > step) {
            return true;
        }
    }
    return false;
}

void setMoveTabu(
    const Move& move,
    std::vector<uint64_t>& tabuUntil,
    uint64_t step,
    uint64_t baseTenure,
    DeterministicRng& rng) {
    for (const int position : move.flips) {
        const uint64_t variation =
            baseTenure == 0 ? 0 : rng.bounded(baseTenure + 1);
        tabuUntil[position] = step + baseTenure + variation + 1;
    }
}

struct EvaluatedMove {
    Move move;
    Score score;
    bool tabu = false;
};

std::size_t chooseEvaluatedMove(
    const std::vector<EvaluatedMove>& evaluated,
    int restartBestUncovered,
    const Options& options,
    DeterministicRng& rng) {
    std::vector<std::size_t> allowed;
    allowed.reserve(evaluated.size());
    std::size_t bestAny = 0;
    std::size_t bestAllowed = 0;
    bool hasAllowed = false;

    for (std::size_t index = 0; index < evaluated.size(); ++index) {
        if (betterSearchScore(
                evaluated[index].score, evaluated[bestAny].score)) {
            bestAny = index;
        }
        const bool aspiration =
            evaluated[index].score.uncovered < restartBestUncovered;
        if (!evaluated[index].tabu || aspiration) {
            allowed.push_back(index);
            if (!hasAllowed ||
                betterSearchScore(
                    evaluated[index].score,
                    evaluated[bestAllowed].score)) {
                bestAllowed = index;
                hasAllowed = true;
            }
        }
    }

    if (!hasAllowed) {
        return bestAny;
    }
    if (options.walkPermille > 0 &&
        rng.bounded(1000) < options.walkPermille) {
        return allowed[static_cast<std::size_t>(
            rng.bounded(allowed.size()))];
    }
    return bestAllowed;
}

void increaseUncoveredWeights(
    const SearchState& state,
    std::vector<uint32_t>& weights) {
    uint32_t maximumWeight = 0;
    for (const uint16_t target : state.uncovered) {
        if (weights[target] < 1000000U) {
            ++weights[target];
        }
        maximumWeight = std::max(maximumWeight, weights[target]);
    }
    if (maximumWeight >= 1000000U) {
        for (uint32_t& weight : weights) {
            weight = std::max(1U, (weight + 1U) / 2U);
        }
    }
}

std::vector<uint8_t> randomBits(int length, DeterministicRng& rng) {
    std::vector<uint8_t> bits(static_cast<std::size_t>(length), 0);
    for (uint8_t& bit : bits) {
        bit = static_cast<uint8_t>(rng.next() & 1ULL);
    }
    return bits;
}

void perturbBits(
    std::vector<uint8_t>& bits,
    int count,
    DeterministicRng& rng) {
    count = std::min(count, static_cast<int>(bits.size()));
    std::vector<uint8_t> selected(bits.size(), 0);
    int changed = 0;
    while (changed < count) {
        const int position = static_cast<int>(rng.bounded(bits.size()));
        if (selected[position] == 0U) {
            selected[position] = 1U;
            bits[position] ^= 1U;
            ++changed;
        }
    }
}

struct BestRecord {
    bool initialized = false;
    std::vector<uint8_t> bits;
    Score score;
    uint64_t restart = 0;
    uint64_t step = 0;
    uint64_t restartSeed = 0;
};

bool updateBest(
    BestRecord& best,
    const SearchState& state,
    const Score& score,
    uint64_t restart,
    uint64_t step,
    uint64_t seed) {
    if (!best.initialized || betterResultScore(score, best.score)) {
        best.initialized = true;
        best.bits = state.bits;
        best.score = score;
        best.restart = restart;
        best.step = step;
        best.restartSeed = seed;
        return true;
    }
    return false;
}

uint64_t sequenceHash(const std::vector<uint8_t>& bits) {
    uint64_t hash = 1469598103934665603ULL;
    const std::array<uint8_t, 4> parameters = {
        static_cast<uint8_t>(kWordLength),
        static_cast<uint8_t>(kRadius),
        static_cast<uint8_t>(bits.size() & 0xffU),
        static_cast<uint8_t>((bits.size() >> 8U) & 0xffU)};
    for (const uint8_t value : parameters) {
        hash ^= value;
        hash *= 1099511628211ULL;
    }
    for (const uint8_t bit : bits) {
        hash ^= bit;
        hash *= 1099511628211ULL;
    }
    return hash;
}

std::string hexadecimal(uint64_t value) {
    std::ostringstream output;
    output << std::hex << std::setfill('0') << std::setw(16) << value;
    return output.str();
}

std::string jsonEscape(std::string_view text) {
    std::ostringstream output;
    for (const char value : text) {
        switch (value) {
            case '\\':
                output << "\\\\";
                break;
            case '"':
                output << "\\\"";
                break;
            case '\n':
                output << "\\n";
                break;
            case '\r':
                output << "\\r";
                break;
            case '\t':
                output << "\\t";
                break;
            default:
                if (static_cast<unsigned char>(value) < 0x20U) {
                    output << "\\u"
                           << std::hex << std::setfill('0') << std::setw(4)
                           << static_cast<int>(
                                  static_cast<unsigned char>(value))
                           << std::dec;
                } else {
                    output << value;
                }
                break;
        }
    }
    return output.str();
}

struct SearchOutcome {
    BestRecord best;
    uint64_t completedRestarts = 0;
    uint64_t completedSteps = 0;
    bool timedOut = false;
    double elapsedSeconds = 0.0;
};

double elapsedSeconds(
    const std::chrono::steady_clock::time_point& start) {
    return std::chrono::duration<double>(
               std::chrono::steady_clock::now() - start)
        .count();
}

SearchOutcome runSearch(
    const Options& options,
    const CoveringBalls& balls) {
    const auto startTime = std::chrono::steady_clock::now();
    SearchOutcome outcome;

    for (uint64_t restart = 0; restart < options.restarts; ++restart) {
        if (options.timeLimitSeconds > 0.0 &&
            elapsedSeconds(startTime) >= options.timeLimitSeconds) {
            outcome.timedOut = true;
            break;
        }

        const uint64_t derivedSeed = restartSeed(options.seed, restart);
        DeterministicRng rng(derivedSeed);
        std::vector<uint8_t> initialBits;
        if (restart == 0 && !options.initialSequence.empty()) {
            initialBits = bitsFromString(options.initialSequence);
        } else if (outcome.best.initialized && restart % 3 != 0) {
            initialBits = outcome.best.bits;
            const int maximumPerturbation =
                std::max(3, options.length / 3);
            const int changes = 2 + static_cast<int>(
                rng.bounded(
                    static_cast<uint64_t>(maximumPerturbation - 1)));
            perturbBits(initialBits, changes, rng);
        } else {
            initialBits = randomBits(options.length, rng);
        }

        SearchState state(std::move(initialBits), balls);
        MoveScratch scratch(options.length);
        std::vector<uint32_t> weights(kUniverseSize, 1U);
        std::vector<uint64_t> tabuUntil(
            static_cast<std::size_t>(options.length), 0ULL);
        Score current =
            scoreWindows(state.windows, weights, balls, scratch);
        int restartBestUncovered = current.uncovered;
        uint64_t nextBreakout = options.stagnationSteps;

        if (updateBest(
                outcome.best,
                state,
                current,
                restart,
                0,
                derivedSeed) &&
            !options.quiet) {
            std::cerr << "best restart=" << restart
                      << " step=0 uncovered=" << current.uncovered
                      << " excess=" << current.distanceExcess
                      << " single=" << current.singlyCovered
                      << " double=" << current.doublyCovered << '\n';
        }

        for (uint64_t step = 0;
             step < options.stepsPerRestart;
             ++step) {
            if (state.uncovered.empty()) {
                break;
            }
            if ((step & 63ULL) == 0ULL &&
                options.timeLimitSeconds > 0.0 &&
                elapsedSeconds(startTime) >= options.timeLimitSeconds) {
                outcome.timedOut = true;
                break;
            }

            std::vector<Move> candidates =
                generateCandidates(state, weights, options, step, rng);
            std::vector<EvaluatedMove> evaluated;
            evaluated.reserve(candidates.size());
            for (Move& move : candidates) {
                EvaluatedMove result;
                result.move = std::move(move);
                result.score = evaluateMove(
                    state, result.move, weights, balls, scratch);
                result.tabu =
                    moveIsTabu(result.move, tabuUntil, step);
                evaluated.push_back(std::move(result));
            }

            const std::size_t selectedIndex = chooseEvaluatedMove(
                evaluated, restartBestUncovered, options, rng);
            const EvaluatedMove selected =
                std::move(evaluated[selectedIndex]);
            commitMove(state, selected.move, balls, scratch);
            setMoveTabu(
                selected.move,
                tabuUntil,
                step,
                options.tabuTenure,
                rng);
            current = selected.score;
            ++outcome.completedSteps;

            if (static_cast<int>(state.uncovered.size()) !=
                current.uncovered) {
                throw std::runtime_error(
                    "incremental coverage disagrees with exact score");
            }

            if (current.uncovered < restartBestUncovered) {
                restartBestUncovered = current.uncovered;
                nextBreakout = step + options.stagnationSteps + 1;
            }
            const bool improved = updateBest(
                outcome.best,
                state,
                current,
                restart,
                step + 1,
                derivedSeed);
            if (improved && !options.quiet) {
                std::cerr << "best restart=" << restart
                          << " step=" << (step + 1)
                          << " uncovered=" << current.uncovered
                          << " excess=" << current.distanceExcess
                          << " single=" << current.singlyCovered
                          << " double=" << current.doublyCovered << '\n';
            }
            if (current.uncovered == 0) {
                break;
            }

            if (options.stagnationSteps > 0 &&
                step + 1 >= nextBreakout) {
                increaseUncoveredWeights(state, weights);
                current =
                    scoreWindows(state.windows, weights, balls, scratch);

                const int maximumKick =
                    std::min(8, static_cast<int>(state.bits.size()));
                Move kick = makeRandomMultiMove(
                    state, rng, 2, maximumKick, "breakout");
                const Score kickScore =
                    evaluateMove(state, kick, weights, balls, scratch);
                commitMove(state, kick, balls, scratch);
                setMoveTabu(
                    kick,
                    tabuUntil,
                    step,
                    options.tabuTenure,
                    rng);
                current = kickScore;
                ++outcome.completedSteps;
                nextBreakout = step + options.stagnationSteps + 1;

                if (static_cast<int>(state.uncovered.size()) !=
                    current.uncovered) {
                    throw std::runtime_error(
                        "breakout coverage disagrees with exact score");
                }
                if (current.uncovered < restartBestUncovered) {
                    restartBestUncovered = current.uncovered;
                }
                if (updateBest(
                        outcome.best,
                        state,
                        current,
                        restart,
                        step + 1,
                        derivedSeed) &&
                    !options.quiet) {
                    std::cerr << "best restart=" << restart
                              << " step=" << (step + 1)
                              << " uncovered=" << current.uncovered
                              << " excess=" << current.distanceExcess
                              << " single=" << current.singlyCovered
                              << " double=" << current.doublyCovered
                              << '\n';
                }
            }
        }

        ++outcome.completedRestarts;
        if (!options.quiet && options.progressEvery > 0 &&
            (restart + 1) % options.progressEvery == 0) {
            std::cerr << "restart=" << (restart + 1)
                      << " best_uncovered=" << outcome.best.score.uncovered
                      << " total_steps=" << outcome.completedSteps << '\n';
        }
        if (outcome.best.initialized &&
            outcome.best.score.uncovered == 0) {
            break;
        }
        if (outcome.timedOut) {
            break;
        }
    }

    outcome.elapsedSeconds = elapsedSeconds(startTime);
    if (!outcome.best.initialized) {
        throw std::runtime_error("search did not initialize a candidate");
    }

    SearchState verified(outcome.best.bits, balls);
    if (static_cast<int>(verified.uncovered.size()) !=
        outcome.best.score.uncovered) {
        throw std::runtime_error("final independent coverage check failed");
    }
    return outcome;
}

void printSearchOutcome(
    const SearchOutcome& outcome,
    const Options& options) {
    const bool success = outcome.best.score.uncovered == 0;
    std::cout << std::fixed << std::setprecision(6)
              << "{\"status\":\""
              << (success ? "success" : "not_found")
              << "\",\"word_length\":" << kWordLength
              << ",\"radius\":" << kRadius
              << ",\"length\":" << outcome.best.bits.size()
              << ",\"base_seed\":" << options.seed
              << ",\"restart_seed\":" << outcome.best.restartSeed
              << ",\"restart\":" << outcome.best.restart
              << ",\"step\":" << outcome.best.step
              << ",\"completed_restarts\":"
              << outcome.completedRestarts
              << ",\"completed_steps\":" << outcome.completedSteps
              << ",\"timed_out\":"
              << (outcome.timedOut ? "true" : "false")
              << ",\"uncovered\":" << outcome.best.score.uncovered
              << ",\"distance_excess\":"
              << outcome.best.score.distanceExcess
              << ",\"singly_covered\":"
              << outcome.best.score.singlyCovered
              << ",\"doubly_covered\":"
              << outcome.best.score.doublyCovered
              << ",\"sequence\":\""
              << bitsToString(outcome.best.bits)
              << "\",\"sequence_hash_fnv1a64\":\""
              << hexadecimal(sequenceHash(outcome.best.bits))
              << "\",\"elapsed_seconds\":"
              << outcome.elapsedSeconds << "}\n";
}

std::vector<uint8_t> binaryDeBruijnSequence(int order) {
    std::vector<int> state(static_cast<std::size_t>(order * 2 + 1), 0);
    std::vector<uint8_t> sequence;
    sequence.reserve(static_cast<std::size_t>(1U << order));

    std::function<void(int, int)> generate = [&](int position, int period) {
        if (position > order) {
            if (order % period == 0) {
                for (int index = 1; index <= period; ++index) {
                    sequence.push_back(
                        static_cast<uint8_t>(state[index]));
                }
            }
            return;
        }
        state[position] = state[position - period];
        generate(position + 1, period);
        for (int value = state[position - period] + 1; value < 2; ++value) {
            state[position] = value;
            generate(position + 1, position);
        }
    };
    generate(1, 1);
    return sequence;
}

void compareStates(
    const SearchState& incremental,
    const SearchState& rebuilt) {
    if (incremental.bits != rebuilt.bits ||
        incremental.windows != rebuilt.windows ||
        incremental.cover != rebuilt.cover ||
        incremental.uncovered.size() != rebuilt.uncovered.size()) {
        throw std::runtime_error("incremental state does not match rebuild");
    }
    for (int target = 0; target < kUniverseSize; ++target) {
        const bool left = incremental.cover[target] == 0U;
        const bool right = rebuilt.cover[target] == 0U;
        if (left != right) {
            throw std::runtime_error("uncovered target mismatch");
        }
    }
}

void runSelfTest(const CoveringBalls& balls, uint64_t seed) {
    DeterministicRng rng(seed);
    for (const int length : {12, 13, 35}) {
        SearchState state(randomBits(length, rng), balls);
        MoveScratch scratch(length);
        std::vector<uint32_t> weights(kUniverseSize, 1U);
        for (int target = 0; target < kUniverseSize; ++target) {
            weights[target] =
                1U + static_cast<uint32_t>(target % 11);
        }

        for (int iteration = 0; iteration < 300; ++iteration) {
            Move move;
            switch (iteration % 5) {
                case 0:
                    move = makeSingleBitMove(state, rng);
                    break;
                case 1:
                    move = makeRandomMultiMove(state, rng, 2, 6);
                    break;
                case 2:
                    move = makeSegmentMove(state, rng);
                    break;
                case 3:
                    move = makeTargetedSingleMove(state, weights, rng);
                    break;
                case 4:
                    move = makeTargetRepairMove(state, weights, rng);
                    break;
                default:
                    throw std::runtime_error("invalid self-test move");
            }

            const Score expected =
                evaluateMove(state, move, weights, balls, scratch);
            commitMove(state, move, balls, scratch);
            SearchState rebuilt(state.bits, balls);
            compareStates(state, rebuilt);
            const Score observed =
                scoreWindows(state.windows, weights, balls, scratch);
            if (!equalScore(expected, observed)) {
                throw std::runtime_error(
                    "move evaluation does not match committed state");
            }
            checkMultiplicityScore(state, observed);
        }
    }

    const std::vector<uint8_t> deBruijn =
        binaryDeBruijnSequence(kWordLength);
    if (deBruijn.size() !=
        static_cast<std::size_t>(kUniverseSize)) {
        throw std::runtime_error("de Bruijn self-test length mismatch");
    }
    SearchState coveringState(deBruijn, balls);
    if (!coveringState.uncovered.empty()) {
        throw std::runtime_error(
            "de Bruijn sequence failed the coverage self-test");
    }

    std::cout
        << "{\"status\":\"self_test_passed\",\"word_length\":"
        << kWordLength
        << ",\"radius\":" << kRadius
        << ",\"incremental_trials\":900"
        << ",\"debruijn_length\":" << deBruijn.size()
        << "}\n";
}

bool verifyAndPrint(
    const std::string& sequence,
    const CoveringBalls& balls) {
    SearchState state(bitsFromString(sequence), balls);
    const bool valid = state.uncovered.empty();
    std::cout
        << "{\"status\":\"verification\",\"valid\":"
        << (valid ? "true" : "false")
        << ",\"word_length\":" << kWordLength
        << ",\"radius\":" << kRadius
        << ",\"length\":" << sequence.size()
        << ",\"covered\":" << (kUniverseSize - state.uncovered.size())
        << ",\"uncovered\":" << state.uncovered.size()
        << ",\"sequence\":\"" << sequence
        << "\",\"sequence_hash_fnv1a64\":\""
        << hexadecimal(sequenceHash(state.bits))
        << "\"}\n";
    return valid;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        const Options options = parseOptions(argc, argv);
        if (options.showHelp) {
            printHelp();
            return EXIT_SUCCESS;
        }

        const CoveringBalls balls;
        if (options.selfTest) {
            runSelfTest(balls, options.seed);
            return EXIT_SUCCESS;
        }
        if (!options.verifySequence.empty()) {
            return verifyAndPrint(options.verifySequence, balls)
                ? EXIT_SUCCESS
                : EXIT_FAILURE;
        }

        const SearchOutcome outcome = runSearch(options, balls);
        printSearchOutcome(outcome, options);
        return EXIT_SUCCESS;
    } catch (const std::exception& error) {
        std::cout << "{\"status\":\"error\",\"message\":\""
                  << jsonEscape(error.what()) << "\"}\n";
        return EXIT_FAILURE;
    }
}
