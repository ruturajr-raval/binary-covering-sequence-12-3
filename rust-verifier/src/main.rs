use std::env;
use std::fs;
use std::io::{self, Read};
use std::path::PathBuf;
use std::process::ExitCode;

const MAX_N: usize = 24;
const USAGE: &str = "\
Usage:
  binary-covering-sequence-verifier --n N --radius R --expected-length L --sequence BITS
  binary-covering-sequence-verifier --n N --radius R --expected-length L --file PATH
  binary-covering-sequence-verifier --n N --radius R --expected-length L < sequence.txt

Options:
  -n, --n N               Cyclic window length, from 1 through 24
  -R, --radius R          Requested covering radius, from 0 through N
  -L, --expected-length L Required cyclic sequence length
  -s, --sequence BITS     Bit sequence supplied on the command line
  -f, --file PATH         File containing the bit sequence
  -h, --help              Show this help

The bit sequence may contain ASCII whitespace. Every other character must be
0 or 1. If neither --sequence nor --file is supplied, input is read from stdin.
";

#[derive(Debug, PartialEq, Eq)]
enum InputSource {
    Inline(String),
    File(PathBuf),
    Stdin,
}

#[derive(Debug, PartialEq, Eq)]
struct Config {
    n: usize,
    radius: usize,
    expected_length: usize,
    input: InputSource,
}

#[derive(Debug, PartialEq, Eq)]
struct Verification {
    sequence_length: usize,
    expected_length: usize,
    cyclic_window_count: usize,
    distinct_window_count: usize,
    ambient_word_count: usize,
    requested_radius: usize,
    covering_radius: usize,
    uncovered_count: usize,
}

impl Verification {
    fn radius_met(&self) -> bool {
        self.uncovered_count == 0
    }
}

fn main() -> ExitCode {
    let config = match parse_config(env::args().skip(1)) {
        Ok(Some(config)) => config,
        Ok(None) => {
            print!("{USAGE}");
            return ExitCode::SUCCESS;
        }
        Err(error) => {
            eprintln!("error: {error}\n\n{USAGE}");
            return ExitCode::from(2);
        }
    };

    let input = match read_input(&config.input) {
        Ok(input) => input,
        Err(error) => {
            eprintln!("error: {error}");
            return ExitCode::from(2);
        }
    };

    let bits = match parse_bits(&input) {
        Ok(bits) => bits,
        Err(error) => {
            eprintln!("error: {error}");
            return ExitCode::from(2);
        }
    };

    let result = match verify(&bits, config.n, config.radius, config.expected_length) {
        Ok(result) => result,
        Err(error) => {
            eprintln!("error: {error}");
            return ExitCode::from(2);
        }
    };

    print_report(&result);
    if result.radius_met() {
        ExitCode::SUCCESS
    } else {
        ExitCode::from(1)
    }
}

fn parse_config<I>(args: I) -> Result<Option<Config>, String>
where
    I: IntoIterator<Item = String>,
{
    let mut args = args.into_iter();
    let mut n = None;
    let mut radius = None;
    let mut expected_length = None;
    let mut input = None;

    while let Some(argument) = args.next() {
        match argument.as_str() {
            "-h" | "--help" => return Ok(None),
            "-n" | "--n" => {
                let value = next_value(&mut args, &argument)?;
                set_number(&mut n, "n", &value)?;
            }
            "-R" | "--radius" => {
                let value = next_value(&mut args, &argument)?;
                set_number(&mut radius, "radius", &value)?;
            }
            "-L" | "--expected-length" => {
                let value = next_value(&mut args, &argument)?;
                set_number(&mut expected_length, "expected-length", &value)?;
            }
            "-s" | "--sequence" => {
                let value = next_value(&mut args, &argument)?;
                set_input(&mut input, InputSource::Inline(value))?;
            }
            "-f" | "--file" => {
                let value = next_value(&mut args, &argument)?;
                set_input(&mut input, InputSource::File(PathBuf::from(value)))?;
            }
            _ => return Err(format!("unknown argument '{argument}'")),
        }
    }

    let n = n.ok_or_else(|| "missing required option --n".to_string())?;
    let radius = radius.ok_or_else(|| "missing required option --radius".to_string())?;
    let expected_length =
        expected_length.ok_or_else(|| "missing required option --expected-length".to_string())?;
    validate_parameters(n, radius)?;
    if expected_length == 0 {
        return Err("expected length must be at least 1".to_string());
    }

    Ok(Some(Config {
        n,
        radius,
        expected_length,
        input: input.unwrap_or(InputSource::Stdin),
    }))
}

fn next_value<I>(args: &mut I, option: &str) -> Result<String, String>
where
    I: Iterator<Item = String>,
{
    args.next()
        .ok_or_else(|| format!("missing value for {option}"))
}

fn set_number(slot: &mut Option<usize>, name: &str, value: &str) -> Result<(), String> {
    if slot.is_some() {
        return Err(format!("option --{name} was supplied more than once"));
    }

    let number = value
        .parse::<usize>()
        .map_err(|_| format!("invalid value '{value}' for --{name}"))?;
    *slot = Some(number);
    Ok(())
}

fn set_input(slot: &mut Option<InputSource>, source: InputSource) -> Result<(), String> {
    if slot.is_some() {
        return Err("supply only one of --sequence and --file".to_string());
    }
    *slot = Some(source);
    Ok(())
}

fn validate_parameters(n: usize, radius: usize) -> Result<(), String> {
    if n == 0 {
        return Err("n must be at least 1".to_string());
    }
    if n > MAX_N {
        return Err(format!("n={n} exceeds the exact verifier limit of {MAX_N}"));
    }
    if radius > n {
        return Err(format!("radius {radius} exceeds n={n}"));
    }
    Ok(())
}

fn read_input(source: &InputSource) -> Result<Vec<u8>, String> {
    match source {
        InputSource::Inline(value) => Ok(value.as_bytes().to_vec()),
        InputSource::File(path) => {
            fs::read(path).map_err(|error| format!("could not read '{}': {error}", path.display()))
        }
        InputSource::Stdin => {
            let mut input = Vec::new();
            io::stdin()
                .read_to_end(&mut input)
                .map_err(|error| format!("could not read stdin: {error}"))?;
            Ok(input)
        }
    }
}

fn parse_bits(input: &[u8]) -> Result<Vec<u8>, String> {
    let mut bits = Vec::with_capacity(input.len());

    for (index, &byte) in input.iter().enumerate() {
        match byte {
            b'0' => bits.push(0),
            b'1' => bits.push(1),
            byte if byte.is_ascii_whitespace() => {}
            byte if byte.is_ascii_graphic() => {
                return Err(format!(
                    "invalid character '{}' at byte {}",
                    char::from(byte),
                    index + 1
                ));
            }
            byte => {
                return Err(format!("invalid byte 0x{byte:02x} at byte {}", index + 1));
            }
        }
    }

    if bits.is_empty() {
        return Err("bit sequence is empty".to_string());
    }
    Ok(bits)
}

fn enumerate_cyclic_windows(bits: &[u8], n: usize) -> Vec<usize> {
    let mut windows = Vec::with_capacity(bits.len());

    for start in 0..bits.len() {
        let mut word = 0usize;
        for offset in 0..n {
            word = (word << 1) | usize::from(bits[(start + offset) % bits.len()]);
        }
        windows.push(word);
    }

    windows
}

fn verify(
    bits: &[u8],
    n: usize,
    requested_radius: usize,
    expected_length: usize,
) -> Result<Verification, String> {
    validate_parameters(n, requested_radius)?;
    if expected_length == 0 {
        return Err("expected length must be at least 1".to_string());
    }
    if bits.is_empty() {
        return Err("bit sequence is empty".to_string());
    }
    if bits.iter().any(|&bit| bit > 1) {
        return Err("bit sequence contains a value other than 0 or 1".to_string());
    }
    if bits.len() != expected_length {
        return Err(format!(
            "sequence length {} does not match expected length {expected_length}",
            bits.len()
        ));
    }

    let ambient_word_count = 1usize << n;
    let windows = enumerate_cyclic_windows(bits, n);
    let mut distances = vec![u8::MAX; ambient_word_count];
    let mut queue = Vec::with_capacity(ambient_word_count);

    for &window in &windows {
        if distances[window] == u8::MAX {
            distances[window] = 0;
            queue.push(window);
        }
    }
    let distinct_window_count = queue.len();

    // Multi-source BFS on the n-cube computes every exact nearest-window distance.
    let mut head = 0usize;
    while head < queue.len() {
        let word = queue[head];
        head += 1;
        let next_distance = distances[word] + 1;

        for bit in 0..n {
            let neighbor = word ^ (1usize << bit);
            if distances[neighbor] == u8::MAX {
                distances[neighbor] = next_distance;
                queue.push(neighbor);
            }
        }
    }

    let covering_radius = distances
        .iter()
        .copied()
        .max()
        .expect("the ambient space is nonempty") as usize;
    let uncovered_count = distances
        .iter()
        .filter(|&&distance| usize::from(distance) > requested_radius)
        .count();

    Ok(Verification {
        sequence_length: bits.len(),
        expected_length,
        cyclic_window_count: windows.len(),
        distinct_window_count,
        ambient_word_count,
        requested_radius,
        covering_radius,
        uncovered_count,
    })
}

fn print_report(result: &Verification) {
    println!("sequence_length={}", result.sequence_length);
    println!("expected_sequence_length={}", result.expected_length);
    println!("cyclic_windows={}", result.cyclic_window_count);
    println!("distinct_windows={}", result.distinct_window_count);
    println!("ambient_words={}", result.ambient_word_count);
    println!("requested_radius={}", result.requested_radius);
    println!("covering_radius={}", result.covering_radius);
    println!("uncovered_count={}", result.uncovered_count);
    println!(
        "result={}",
        if result.radius_met() { "PASS" } else { "FAIL" }
    );
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_bits_with_ascii_whitespace() {
        assert_eq!(parse_bits(b" 01\n10\r\t").unwrap(), vec![0, 1, 1, 0]);
    }

    #[test]
    fn rejects_invalid_or_empty_sequences() {
        assert_eq!(
            parse_bits(b"0102").unwrap_err(),
            "invalid character '2' at byte 4"
        );
        assert_eq!(parse_bits(b" \n\t").unwrap_err(), "bit sequence is empty");
    }

    #[test]
    fn enumerates_cyclic_windows_with_wraparound() {
        let bits = parse_bits(b"0011").unwrap();
        assert_eq!(enumerate_cyclic_windows(&bits, 2), vec![0, 1, 3, 2]);
    }

    #[test]
    fn verifies_a_binary_de_bruijn_cycle_at_radius_zero() {
        let bits = parse_bits(b"0011").unwrap();
        let result = verify(&bits, 2, 0, 4).unwrap();

        assert_eq!(result.cyclic_window_count, 4);
        assert_eq!(result.distinct_window_count, 4);
        assert_eq!(result.covering_radius, 0);
        assert_eq!(result.uncovered_count, 0);
        assert!(result.radius_met());
    }

    #[test]
    fn computes_exact_radius_and_uncovered_count() {
        let result = verify(&[0], 3, 1, 1).unwrap();

        assert_eq!(result.distinct_window_count, 1);
        assert_eq!(result.ambient_word_count, 8);
        assert_eq!(result.covering_radius, 3);
        assert_eq!(result.uncovered_count, 4);
        assert!(!result.radius_met());
    }

    #[test]
    fn distinguishes_requested_radius_failure_and_success() {
        let bits = parse_bits(b"01").unwrap();
        let failed = verify(&bits, 2, 0, 2).unwrap();
        let passed = verify(&bits, 2, 1, 2).unwrap();

        assert_eq!(failed.covering_radius, 1);
        assert_eq!(failed.uncovered_count, 2);
        assert!(!failed.radius_met());
        assert_eq!(passed.covering_radius, 1);
        assert_eq!(passed.uncovered_count, 0);
        assert!(passed.radius_met());
    }

    #[test]
    fn parses_inline_configuration() {
        let config = parse_config([
            "--n".to_string(),
            "12".to_string(),
            "--radius".to_string(),
            "3".to_string(),
            "--expected-length".to_string(),
            "4".to_string(),
            "--sequence".to_string(),
            "0101".to_string(),
        ])
        .unwrap()
        .unwrap();

        assert_eq!(
            config,
            Config {
                n: 12,
                radius: 3,
                expected_length: 4,
                input: InputSource::Inline("0101".to_string()),
            }
        );
    }

    #[test]
    fn rejects_an_unexpected_sequence_length() {
        assert_eq!(
            verify(&[0, 0, 1, 1], 2, 0, 3).unwrap_err(),
            "sequence length 4 does not match expected length 3"
        );
    }

    #[test]
    fn rejects_out_of_range_parameters() {
        assert_eq!(
            validate_parameters(0, 0).unwrap_err(),
            "n must be at least 1"
        );
        assert_eq!(
            validate_parameters(MAX_N + 1, 0).unwrap_err(),
            "n=25 exceeds the exact verifier limit of 24"
        );
        assert_eq!(
            validate_parameters(12, 13).unwrap_err(),
            "radius 13 exceeds n=12"
        );
    }
}
