PYTHON ?= python3
CXX ?= c++
CXXFLAGS ?= -std=c++20 -O3 -DNDEBUG -Wall -Wextra -Wpedantic -Werror
CARGO ?= cargo
FULL_REPLAY_MIN ?= 1
FULL_REPLAY_MAX ?= 35
FULL_REPLAY_THREADS ?= 4
SOURCE_DATE_EPOCH ?= 0
FORCE_SOURCE_DATE ?= 1
RELEASE_REF ?= HEAD
RELEASE_TAG ?=

.PHONY: all test test-python test-rust test-search test-exhaustive \
	test-exhaustive-sanitize \
	test-evidence full-replay full-replay-cpp full-replay-rust \
	verify-baseline verify-exact-result \
	sat-smoke sat-compact-smoke sat-guarded-smoke compact-sat-35 \
	guarded-sat-35 check-text paper \
	release-manifest verify-release-manifest \
	release-assets verify-release-assets clean

all: build/search build/exhaustive \
	rust-verifier/target/release/binary-covering-sequence-verifier \
	rust-exhaustive/target/release/binary-covering-sequence-exhaustive

build/search: src/search.cpp
	mkdir -p build
	$(CXX) $(CXXFLAGS) $< -o $@

build/exhaustive: src/exhaustive.cpp
	mkdir -p build
	$(CXX) $(CXXFLAGS) -pthread $< -o $@

build/test-exhaustive-oracle: tests/exhaustive_oracle.cpp src/exhaustive.cpp
	mkdir -p build
	$(CXX) $(CXXFLAGS) -pthread tests/exhaustive_oracle.cpp -o $@

rust-verifier/target/release/binary-covering-sequence-verifier: \
		rust-verifier/Cargo.toml rust-verifier/Cargo.lock \
		rust-verifier/src/main.rs
	$(CARGO) build --release --manifest-path rust-verifier/Cargo.toml

rust-exhaustive/target/release/binary-covering-sequence-exhaustive: \
		rust-exhaustive/Cargo.toml rust-exhaustive/Cargo.lock \
		rust-exhaustive/src/lib.rs rust-exhaustive/src/main.rs
	$(CARGO) build --release --manifest-path rust-exhaustive/Cargo.toml

test: test-python test-rust test-search test-exhaustive \
	test-exhaustive-sanitize test-evidence sat-smoke sat-compact-smoke \
	sat-guarded-smoke check-text

test-python:
	$(PYTHON) -m unittest discover -s tests -v

test-rust:
	$(CARGO) test --manifest-path rust-verifier/Cargo.toml
	$(CARGO) clippy --manifest-path rust-verifier/Cargo.toml -- -D warnings
	$(CARGO) fmt --manifest-path rust-verifier/Cargo.toml -- --check
	$(CARGO) test --manifest-path rust-exhaustive/Cargo.toml
	$(CARGO) clippy --manifest-path rust-exhaustive/Cargo.toml \
		--all-targets -- -D warnings
	$(CARGO) fmt --manifest-path rust-exhaustive/Cargo.toml -- --check

test-search: build/search
	build/search --self-test --seed 20260907
	! build/search --length 12 --verify 000000000000 >/dev/null
	! build/search --length 35 \
		--verify 010100011011000110111110101110010000 >/dev/null

test-exhaustive: build/exhaustive build/test-exhaustive-oracle \
		rust-exhaustive/target/release/binary-covering-sequence-exhaustive
	build/test-exhaustive-oracle
	build/exhaustive 1 18 2 > build/cpp-exhaustive-smoke.jsonl
	$(PYTHON) tools/check_exhaustive_evidence.py \
		--log build/cpp-exhaustive-smoke.jsonl \
		--min-length 1 --max-length 18
	rust-exhaustive/target/release/binary-covering-sequence-exhaustive \
		--range 1:18 --threads 2 > build/rust-exhaustive-smoke.json
	$(PYTHON) tools/check_rust_exhaustive_evidence.py \
		--log build/rust-exhaustive-smoke.json \
		--min-length 1 --max-length 18

test-exhaustive-sanitize:
	mkdir -p build
	$(CXX) -std=c++20 -O1 -g \
		-fsanitize=address,undefined -fno-omit-frame-pointer \
		-Wall -Wextra -Wpedantic -Werror -pthread \
		src/exhaustive.cpp -o build/exhaustive-sanitize
	ASAN_OPTIONS=detect_leaks=0 \
		build/exhaustive-sanitize 1 20 2 \
		> build/exhaustive-sanitize.jsonl
	$(PYTHON) tools/check_exhaustive_evidence.py \
		--log build/exhaustive-sanitize.jsonl \
		--min-length 1 --max-length 20

test-evidence: build/search \
		rust-verifier/target/release/binary-covering-sequence-verifier
	$(PYTHON) tools/check_exhaustive_evidence.py \
		--log evidence/cpp-exhaustive-1-35.jsonl \
		--metadata evidence/cpp-exhaustive-1-35.json \
		--min-length 1 --max-length 35
	$(PYTHON) tools/check_rust_exhaustive_evidence.py \
		--log evidence/rust-exhaustive-1-35.json \
		--metadata evidence/rust-exhaustive-1-35.metadata.json \
		--min-length 1 --max-length 35
	$(PYTHON) tools/check_result_summary.py

full-replay: full-replay-cpp full-replay-rust

full-replay-cpp: build/exhaustive
	mkdir -p build
	build/exhaustive $(FULL_REPLAY_MIN) $(FULL_REPLAY_MAX) \
		$(FULL_REPLAY_THREADS) > build/full-replay-cpp.jsonl
	$(PYTHON) tools/check_exhaustive_evidence.py \
		--log build/full-replay-cpp.jsonl \
		--min-length $(FULL_REPLAY_MIN) \
		--max-length $(FULL_REPLAY_MAX)

full-replay-rust: \
		rust-exhaustive/target/release/binary-covering-sequence-exhaustive
	mkdir -p build
	rust-exhaustive/target/release/binary-covering-sequence-exhaustive \
		--range $(FULL_REPLAY_MIN):$(FULL_REPLAY_MAX) \
		--threads $(FULL_REPLAY_THREADS) \
		> build/full-replay-rust.json
	$(PYTHON) tools/check_rust_exhaustive_evidence.py \
		--log build/full-replay-rust.json \
		--min-length $(FULL_REPLAY_MIN) \
		--max-length $(FULL_REPLAY_MAX)

verify-baseline: all
	$(PYTHON) src/verify.py data/baseline-36.txt \
		--n 12 --radius 3 --expected-length 36 --json
	rust-verifier/target/release/binary-covering-sequence-verifier \
		--n 12 --radius 3 --expected-length 36 \
		--file data/baseline-36.txt
	build/search --length 36 \
		--verify 010100011011000110111110101110010000

verify-exact-result: verify-baseline test-evidence

sat-smoke:
	mkdir -p build
	$(PYTHON) src/encode_sat.py --n 3 --radius 1 --length 2 \
		--output build/smoke.cnf --map build/smoke.map.json
	$(PYTHON) src/encode_sat.py --n 3 --radius 1 --length 2 \
		--check-sequence 01

sat-compact-smoke:
	mkdir -p build
	$(PYTHON) src/encode_sat_compact.py --n 3 --radius 1 --length 2 \
		--output build/compact-smoke.cnf \
		--map build/compact-smoke.map.json
	$(PYTHON) src/encode_sat_compact.py --n 3 --radius 1 --length 2 \
		--check-sequence 01

compact-sat-35:
	mkdir -p build
	$(PYTHON) src/encode_sat_compact.py --n 12 --radius 3 --length 35 \
		--output build/L12R3-35-compact.cnf \
		--map build/L12R3-35-compact.map.json

sat-guarded-smoke:
	mkdir -p build
	$(PYTHON) src/encode_sat_guarded.py --n 3 --radius 1 --length 2 \
		--output build/guarded-smoke.cnf \
		--map build/guarded-smoke.map.json
	$(PYTHON) src/encode_sat_guarded.py --n 3 --radius 1 --length 2 \
		--check-sequence 01

guarded-sat-35:
	mkdir -p build
	$(PYTHON) src/encode_sat_guarded.py --n 12 --radius 3 --length 35 \
		--output build/L12R3-35-guarded.cnf \
		--map build/L12R3-35-guarded.map.json

check-text:
	$(PYTHON) tools/check_repository_text.py

paper:
	mkdir -p build/paper
	SOURCE_DATE_EPOCH=$(SOURCE_DATE_EPOCH) \
		FORCE_SOURCE_DATE=$(FORCE_SOURCE_DATE) \
		pdflatex -halt-on-error -interaction=nonstopmode \
		-output-directory=build/paper paper/main.tex
	SOURCE_DATE_EPOCH=$(SOURCE_DATE_EPOCH) \
		FORCE_SOURCE_DATE=$(FORCE_SOURCE_DATE) \
		pdflatex -halt-on-error -interaction=nonstopmode \
		-output-directory=build/paper paper/main.tex

release-manifest:
	$(PYTHON) tools/release_manifest.py --write

verify-release-manifest:
	$(PYTHON) tools/release_manifest.py --check

release-assets: all paper
	$(PYTHON) tools/build_release_assets.py \
		--ref "$(RELEASE_REF)" \
		$(if $(RELEASE_TAG),--tag "$(RELEASE_TAG)")

verify-release-assets:
	$(PYTHON) tools/build_release_assets.py --check \
		--ref "$(RELEASE_REF)" \
		$(if $(RELEASE_TAG),--tag "$(RELEASE_TAG)")

clean:
	rm -rf build rust-verifier/target rust-exhaustive/target
