use std::fmt;
use std::sync::OnceLock;
use std::thread;
use std::time::Instant;

pub const WINDOW_LENGTH: usize = 12;
pub const COVERING_RADIUS: u32 = 3;
pub const TARGET_COUNT: usize = 1 << WINDOW_LENGTH;
pub const MAX_SEQUENCE_LENGTH: u8 = 63;
pub const MAX_THREADS: usize = 1024;

const COVERAGE_WORDS: usize = TARGET_COUNT / u64::BITS as usize;
type CoverageBitset = [u64; COVERAGE_WORDS];

static COVERAGE_TABLE: OnceLock<Box<[CoverageBitset]>> = OnceLock::new();

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct LengthSummary {
    pub length: u8,
    pub total_sequences: u128,
    pub symmetry_representatives: u128,
    pub covering_representatives: u128,
    pub covering_sequences: u128,
    pub witness: Option<String>,
    pub elapsed_millis: u128,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum CheckError {
    InvalidLength(u8),
    InvalidThreadCount(usize),
    WorkerSpawn(String),
    WorkerPanicked,
}

impl fmt::Display for CheckError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidLength(length) => write!(
                formatter,
                "sequence length must be between 1 and {MAX_SEQUENCE_LENGTH}, got {length}"
            ),
            Self::InvalidThreadCount(count) => write!(
                formatter,
                "thread count must be between 1 and {MAX_THREADS}, got {count}"
            ),
            Self::WorkerSpawn(message) => {
                write!(formatter, "failed to start exhaustive worker: {message}")
            }
            Self::WorkerPanicked => write!(formatter, "an exhaustive worker panicked"),
        }
    }
}

impl std::error::Error for CheckError {}

#[derive(Default)]
struct WorkerSummary {
    symmetry_representatives: u64,
    covering_representatives: u64,
    covering_sequences: u64,
    witness: Option<u64>,
}

pub fn exhaustive_check(length: u8, requested_threads: usize) -> Result<LengthSummary, CheckError> {
    validate_inputs(length, requested_threads)?;

    let started = Instant::now();
    let total_sequences = 1_u64 << length;
    let available_sequences = usize::try_from(total_sequences).unwrap_or(usize::MAX);
    let worker_count = requested_threads.min(available_sequences);
    let coverage_table = coverage_table();
    let mut handles = Vec::with_capacity(worker_count);

    for worker_index in 0..worker_count {
        let start = partition_point(total_sequences, worker_count, worker_index);
        let end = partition_point(total_sequences, worker_count, worker_index + 1);
        let handle = thread::Builder::new()
            .name(format!("exhaustive-{length}-{worker_index}"))
            .spawn(move || check_partition(length, start, end, coverage_table))
            .map_err(|error| CheckError::WorkerSpawn(error.to_string()))?;
        handles.push(handle);
    }

    let mut combined = WorkerSummary::default();
    for handle in handles {
        let worker = handle.join().map_err(|_| CheckError::WorkerPanicked)?;
        combined.symmetry_representatives += worker.symmetry_representatives;
        combined.covering_representatives += worker.covering_representatives;
        combined.covering_sequences += worker.covering_sequences;
        combined.witness = minimum_option(combined.witness, worker.witness);
    }

    Ok(LengthSummary {
        length,
        total_sequences: u128::from(total_sequences),
        symmetry_representatives: u128::from(combined.symmetry_representatives),
        covering_representatives: u128::from(combined.covering_representatives),
        covering_sequences: u128::from(combined.covering_sequences),
        witness: combined
            .witness
            .map(|sequence| sequence_to_string(sequence, length)),
        elapsed_millis: started.elapsed().as_millis(),
    })
}

pub fn cyclic_windows(sequence: u64, length: u8) -> Vec<u16> {
    assert!((1..=MAX_SEQUENCE_LENGTH).contains(&length));
    assert!(sequence < (1_u64 << length));

    let mut windows = Vec::with_capacity(usize::from(length));
    for start in 0..usize::from(length) {
        let mut window = 0_u16;
        for offset in 0..WINDOW_LENGTH {
            let index = (start + offset) % usize::from(length);
            window = (window << 1) | u16::from(sequence_bit(sequence, length, index));
        }
        windows.push(window);
    }
    windows.sort_unstable();
    windows.dedup();
    windows
}

pub fn covered_target_count(sequence: u64, length: u8) -> usize {
    validate_sequence(sequence, length);
    covered_target_count_with_table(sequence, length, coverage_table())
}

pub fn is_covering(sequence: u64, length: u8) -> bool {
    validate_sequence(sequence, length);
    is_covering_with_table(sequence, length, coverage_table())
}

pub fn canonical_form(sequence: u64, length: u8) -> u64 {
    assert!((1..=MAX_SEQUENCE_LENGTH).contains(&length));
    assert!(sequence < (1_u64 << length));

    let reversed = reverse_sequence(sequence, length);
    let mask = sequence_mask(length);
    let mut minimum = sequence;

    for orientation in [sequence, reversed] {
        for polarity in [orientation, (!orientation) & mask] {
            for shift in 0..usize::from(length) {
                minimum = minimum.min(rotate_sequence(polarity, length, shift));
            }
        }
    }

    minimum
}

pub fn orbit_size(sequence: u64, length: u8) -> usize {
    orbit_members(sequence, length).len()
}

pub fn orbit_members(sequence: u64, length: u8) -> Vec<u64> {
    assert!((1..=MAX_SEQUENCE_LENGTH).contains(&length));
    assert!(sequence < (1_u64 << length));

    let reversed = reverse_sequence(sequence, length);
    let mask = sequence_mask(length);
    let mut members = Vec::with_capacity(4 * usize::from(length));

    for orientation in [sequence, reversed] {
        for polarity in [orientation, (!orientation) & mask] {
            for shift in 0..usize::from(length) {
                members.push(rotate_sequence(polarity, length, shift));
            }
        }
    }

    members.sort_unstable();
    members.dedup();
    members
}

pub fn parse_sequence(text: &str) -> Result<(u64, u8), String> {
    if text.is_empty() {
        return Err("sequence must not be empty".to_owned());
    }
    if text.len() > usize::from(MAX_SEQUENCE_LENGTH) {
        return Err(format!(
            "sequence length must not exceed {MAX_SEQUENCE_LENGTH}"
        ));
    }

    let mut sequence = 0_u64;
    for character in text.bytes() {
        sequence <<= 1;
        match character {
            b'0' => {}
            b'1' => sequence |= 1,
            _ => return Err("sequence must contain only 0 and 1".to_owned()),
        }
    }

    Ok((sequence, text.len() as u8))
}

pub fn sequence_to_string(sequence: u64, length: u8) -> String {
    assert!((1..=MAX_SEQUENCE_LENGTH).contains(&length));
    assert!(sequence < (1_u64 << length));

    (0..usize::from(length))
        .map(|index| {
            if sequence_bit(sequence, length, index) == 0 {
                '0'
            } else {
                '1'
            }
        })
        .collect()
}

pub fn summaries_to_json(
    range_start: u8,
    range_end: u8,
    threads: usize,
    summaries: &[LengthSummary],
) -> String {
    let mut output = String::new();
    output.push_str("{\n");
    output.push_str(
        "  \"problem\": {\"alphabet\": \"binary\", \"window_length\": 12, \"radius\": 3},\n",
    );
    output.push_str(&format!(
        "  \"range\": {{\"start\": {range_start}, \"end\": {range_end}}},\n"
    ));
    output.push_str(&format!("  \"threads\": {threads},\n"));
    output.push_str("  \"results\": [\n");

    for (index, summary) in summaries.iter().enumerate() {
        let witness = summary
            .witness
            .as_ref()
            .map_or_else(|| "null".to_owned(), |value| format!("\"{value}\""));
        output.push_str("    {");
        output.push_str(&format!(
            "\"length\": {}, \"total_sequences\": {}, \"symmetry_representatives\": {}, \
             \"covering_representatives\": {}, \"covering_sequences\": {}, \"witness\": {}, \
             \"elapsed_millis\": {}",
            summary.length,
            summary.total_sequences,
            summary.symmetry_representatives,
            summary.covering_representatives,
            summary.covering_sequences,
            witness,
            summary.elapsed_millis
        ));
        output.push('}');
        if index + 1 != summaries.len() {
            output.push(',');
        }
        output.push('\n');
    }

    output.push_str("  ]\n");
    output.push('}');
    output
}

fn validate_inputs(length: u8, threads: usize) -> Result<(), CheckError> {
    if !(1..=MAX_SEQUENCE_LENGTH).contains(&length) {
        return Err(CheckError::InvalidLength(length));
    }
    if !(1..=MAX_THREADS).contains(&threads) {
        return Err(CheckError::InvalidThreadCount(threads));
    }
    Ok(())
}

fn partition_point(total: u64, partitions: usize, index: usize) -> u64 {
    ((u128::from(total) * index as u128) / partitions as u128) as u64
}

fn check_partition(
    length: u8,
    start: u64,
    end: u64,
    coverage_table: &[CoverageBitset],
) -> WorkerSummary {
    let mut summary = WorkerSummary::default();

    for sequence in start..end {
        if !is_canonical_representative(sequence, length) {
            continue;
        }

        summary.symmetry_representatives += 1;
        if is_covering_with_table(sequence, length, coverage_table) {
            summary.covering_representatives += 1;
            summary.covering_sequences += orbit_size(sequence, length) as u64;
            summary.witness = minimum_option(summary.witness, Some(sequence));
        }
    }

    summary
}

fn minimum_option(left: Option<u64>, right: Option<u64>) -> Option<u64> {
    match (left, right) {
        (Some(left), Some(right)) => Some(left.min(right)),
        (Some(value), None) | (None, Some(value)) => Some(value),
        (None, None) => None,
    }
}

fn sequence_mask(length: u8) -> u64 {
    (1_u64 << length) - 1
}

fn validate_sequence(sequence: u64, length: u8) {
    assert!((1..=MAX_SEQUENCE_LENGTH).contains(&length));
    assert!(sequence < (1_u64 << length));
}

fn sequence_bit(sequence: u64, length: u8, index: usize) -> u8 {
    let shift = usize::from(length) - 1 - index;
    ((sequence >> shift) & 1) as u8
}

fn is_canonical_representative(sequence: u64, length: u8) -> bool {
    for reversed in [false, true] {
        for complemented in [false, true] {
            for shift in 0..usize::from(length) {
                if !reversed && !complemented && shift == 0 {
                    continue;
                }
                if transformed_sequence_is_smaller(sequence, length, shift, reversed, complemented)
                {
                    return false;
                }
            }
        }
    }

    true
}

fn transformed_sequence_is_smaller(
    sequence: u64,
    length: u8,
    shift: usize,
    reversed: bool,
    complemented: bool,
) -> bool {
    let length_usize = usize::from(length);
    let mut source_index = shift;

    for output_index in 0..length_usize {
        let oriented_index = if reversed {
            length_usize - 1 - source_index
        } else {
            source_index
        };
        let transformed_bit =
            sequence_bit(sequence, length, oriented_index) ^ u8::from(complemented);
        let original_bit = sequence_bit(sequence, length, output_index);

        if transformed_bit != original_bit {
            return transformed_bit < original_bit;
        }

        source_index += 1;
        if source_index == length_usize {
            source_index = 0;
        }
    }

    false
}

fn rotate_sequence(sequence: u64, length: u8, shift: usize) -> u64 {
    let length_usize = usize::from(length);
    let shift = shift % length_usize;
    let mut rotated = 0_u64;

    for index in 0..length_usize {
        rotated = (rotated << 1)
            | u64::from(sequence_bit(
                sequence,
                length,
                (index + shift) % length_usize,
            ));
    }

    rotated
}

fn reverse_sequence(sequence: u64, length: u8) -> u64 {
    let mut reversed = 0_u64;

    for index in (0..usize::from(length)).rev() {
        reversed = (reversed << 1) | u64::from(sequence_bit(sequence, length, index));
    }

    reversed
}

fn coverage_table() -> &'static [CoverageBitset] {
    COVERAGE_TABLE
        .get_or_init(|| {
            let mut table = Vec::with_capacity(TARGET_COUNT);

            for window in 0..TARGET_COUNT as u16 {
                let mut covered = [0_u64; COVERAGE_WORDS];
                mark_covered(&mut covered, window);

                for first in 0..WINDOW_LENGTH {
                    mark_covered(&mut covered, window ^ (1_u16 << first));
                }
                for first in 0..WINDOW_LENGTH {
                    for second in (first + 1)..WINDOW_LENGTH {
                        mark_covered(&mut covered, window ^ (1_u16 << first) ^ (1_u16 << second));
                    }
                }
                for first in 0..WINDOW_LENGTH {
                    for second in (first + 1)..WINDOW_LENGTH {
                        for third in (second + 1)..WINDOW_LENGTH {
                            mark_covered(
                                &mut covered,
                                window ^ (1_u16 << first) ^ (1_u16 << second) ^ (1_u16 << third),
                            );
                        }
                    }
                }

                table.push(covered);
            }

            table.into_boxed_slice()
        })
        .as_ref()
}

fn covered_target_count_with_table(
    sequence: u64,
    length: u8,
    coverage_table: &[CoverageBitset],
) -> usize {
    covered_targets_with_table(sequence, length, coverage_table)
        .iter()
        .map(|word| word.count_ones() as usize)
        .sum()
}

fn is_covering_with_table(sequence: u64, length: u8, coverage_table: &[CoverageBitset]) -> bool {
    covered_targets_with_table(sequence, length, coverage_table)
        .iter()
        .all(|&word| word == u64::MAX)
}

fn covered_targets_with_table(
    sequence: u64,
    length: u8,
    coverage_table: &[CoverageBitset],
) -> CoverageBitset {
    let length_usize = usize::from(length);
    let mut covered = [0_u64; COVERAGE_WORDS];
    let mut window = 0_u16;

    for offset in 0..WINDOW_LENGTH {
        let index = offset % length_usize;
        window = (window << 1) | u16::from(sequence_bit(sequence, length, index));
    }

    for start in 0..length_usize {
        for (covered_word, window_word) in covered
            .iter_mut()
            .zip(coverage_table[usize::from(window)].iter())
        {
            *covered_word |= *window_word;
        }

        if start + 1 != length_usize {
            let next_index = (start + WINDOW_LENGTH) % length_usize;
            window = ((window << 1) & (TARGET_COUNT as u16 - 1))
                | u16::from(sequence_bit(sequence, length, next_index));
        }
    }

    covered
}

fn mark_covered(covered: &mut CoverageBitset, target: u16) {
    let target = usize::from(target);
    covered[target / u64::BITS as usize] |= 1_u64 << (target % u64::BITS as usize);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cyclic_windows_repeat_short_sequences() {
        let (sequence, length) = parse_sequence("01").unwrap();
        assert_eq!(
            cyclic_windows(sequence, length),
            vec![0b010101010101, 0b101010101010]
        );
    }

    #[test]
    fn optimized_coverage_matches_direct_hamming_checks() {
        for length in 1..=8 {
            for sequence in 0..(1_u64 << length) {
                assert_eq!(
                    covered_target_count(sequence, length),
                    direct_covered_target_count(sequence, length),
                    "coverage mismatch for {}",
                    sequence_to_string(sequence, length)
                );
            }
        }
    }

    #[test]
    fn optimized_coverage_matches_direct_hamming_checks_at_larger_lengths() {
        for text in [
            "010100011011",
            "000010010100001101101011",
            "00001001010000110110101111001101110",
            "010100011011000110111110101110010000",
        ] {
            let (sequence, length) = parse_sequence(text).unwrap();
            assert_eq!(
                covered_target_count(sequence, length),
                direct_covered_target_count(sequence, length),
                "coverage mismatch for {text}"
            );
        }
    }

    #[test]
    fn known_length_36_fixture_covers_every_target() {
        let (sequence, length) = parse_sequence("010100011011000110111110101110010000").unwrap();
        assert_eq!(length, 36);
        assert_eq!(covered_target_count(sequence, length), TARGET_COUNT);
        assert!(is_covering(sequence, length));
    }

    #[test]
    fn canonical_form_is_constant_across_complete_orbits() {
        for length in 1..=9 {
            for sequence in 0..(1_u64 << length) {
                let canonical = canonical_form(sequence, length);
                assert!(
                    orbit_members(sequence, length)
                        .into_iter()
                        .all(|member| canonical_form(member, length) == canonical)
                );
            }
        }
    }

    #[test]
    fn optimized_canonicality_matches_canonical_form() {
        for length in 1..=12 {
            for sequence in 0..(1_u64 << length) {
                assert_eq!(
                    is_canonical_representative(sequence, length),
                    canonical_form(sequence, length) == sequence,
                    "canonicality mismatch for {}",
                    sequence_to_string(sequence, length)
                );
            }
        }
    }

    #[test]
    fn small_symmetry_orbit_counts_match_burnside_counts() {
        let expected = [1_u64, 2, 2, 4, 4, 8, 9, 18, 23, 44];

        for (offset, expected_count) in expected.into_iter().enumerate() {
            let length = (offset + 1) as u8;
            let enumerated = (0..(1_u64 << length))
                .filter(|&sequence| canonical_form(sequence, length) == sequence)
                .count() as u64;
            assert_eq!(enumerated, expected_count, "length {length}");
            assert_eq!(enumerated, burnside_orbit_count(length), "length {length}");
        }
    }

    #[test]
    fn threaded_enumeration_has_stable_counts() {
        for length in 1..=8 {
            let serial = exhaustive_check(length, 1).unwrap();
            let parallel = exhaustive_check(length, 3).unwrap();
            assert_eq!(
                serial.symmetry_representatives,
                parallel.symmetry_representatives
            );
            assert_eq!(
                serial.covering_representatives,
                parallel.covering_representatives
            );
            assert_eq!(serial.covering_sequences, parallel.covering_sequences);
            assert_eq!(serial.witness, parallel.witness);
        }
    }

    #[test]
    fn json_summary_contains_counts_and_null_witness() {
        let mut summary = exhaustive_check(4, 2).unwrap();
        summary.elapsed_millis = 7;
        let json = summaries_to_json(4, 4, 2, &[summary]);

        assert!(json.starts_with("{\n"));
        assert!(json.contains("\"symmetry_representatives\": 4"));
        assert!(json.contains("\"covering_representatives\": 0"));
        assert!(json.contains("\"witness\": null"));
        assert!(json.ends_with('}'));
    }

    fn direct_covered_target_count(sequence: u64, length: u8) -> usize {
        let mut covered = 0;

        for target in 0..TARGET_COUNT as u16 {
            let target_is_covered = (0..usize::from(length)).any(|start| {
                let mut window = 0_u16;
                for offset in 0..WINDOW_LENGTH {
                    let index = (start + offset) % usize::from(length);
                    window = (window << 1) | u16::from(sequence_bit(sequence, length, index));
                }
                (window ^ target).count_ones() <= COVERING_RADIUS
            });
            covered += usize::from(target_is_covered);
        }

        covered
    }

    fn burnside_orbit_count(length: u8) -> u64 {
        let length = usize::from(length);
        let mut fixed_sum = 0_u64;

        for offset in 0..length {
            fixed_sum += fixed_assignments(length, |index| (index + offset) % length);
            fixed_sum += fixed_assignments(length, |index| (offset + length - index) % length);
        }

        fixed_sum / (4 * length) as u64
    }

    fn fixed_assignments(length: usize, permutation: impl Fn(usize) -> usize) -> u64 {
        let mut seen = vec![false; length];
        let mut cycle_count = 0_u32;
        let mut all_cycles_even = true;

        for start in 0..length {
            if seen[start] {
                continue;
            }
            cycle_count += 1;
            let mut cycle_length = 0;
            let mut position = start;
            while !seen[position] {
                seen[position] = true;
                cycle_length += 1;
                position = permutation(position);
            }
            all_cycles_even &= cycle_length % 2 == 0;
        }

        let ordinary = 1_u64 << cycle_count;
        let complemented = if all_cycles_even { ordinary } else { 0 };
        ordinary + complemented
    }
}
