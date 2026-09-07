use std::env;
use std::process;

use binary_covering_sequence_exhaustive::{
    MAX_SEQUENCE_LENGTH, MAX_THREADS, exhaustive_check, summaries_to_json,
};

const USAGE: &str = "\
Independent exhaustive checker for binary cyclic (12,3) covering sequences

Usage:
  binary-covering-sequence-exhaustive --length N [--threads N]
  binary-covering-sequence-exhaustive --range START:END [--threads N]
  binary-covering-sequence-exhaustive --range START..=END [--threads N]

The range is inclusive. Output is one JSON document on standard output.
Lengths must be between 1 and 63.";

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct Arguments {
    range_start: u8,
    range_end: u8,
    threads: usize,
}

fn main() {
    let arguments = match parse_arguments(env::args().skip(1)) {
        Ok(Some(arguments)) => arguments,
        Ok(None) => {
            println!("{USAGE}");
            return;
        }
        Err(message) => {
            eprintln!("error: {message}\n\n{USAGE}");
            process::exit(2);
        }
    };

    let mut summaries = Vec::new();
    for length in arguments.range_start..=arguments.range_end {
        match exhaustive_check(length, arguments.threads) {
            Ok(summary) => summaries.push(summary),
            Err(error) => {
                eprintln!("error: {error}");
                process::exit(1);
            }
        }
    }

    println!(
        "{}",
        summaries_to_json(
            arguments.range_start,
            arguments.range_end,
            arguments.threads,
            &summaries
        )
    );
}

fn parse_arguments(
    arguments: impl IntoIterator<Item = String>,
) -> Result<Option<Arguments>, String> {
    let mut arguments = arguments.into_iter();
    let mut range = None;
    let mut threads = None;

    while let Some(argument) = arguments.next() {
        match argument.as_str() {
            "-h" | "--help" => return Ok(None),
            "--length" => {
                if range.is_some() {
                    return Err("specify exactly one of --length or --range".to_owned());
                }
                let value = required_value(&mut arguments, "--length")?;
                let length = parse_length(&value)?;
                range = Some((length, length));
            }
            "--range" => {
                if range.is_some() {
                    return Err("specify exactly one of --length or --range".to_owned());
                }
                let value = required_value(&mut arguments, "--range")?;
                range = Some(parse_range(&value)?);
            }
            "--threads" => {
                if threads.is_some() {
                    return Err("--threads may be specified only once".to_owned());
                }
                let value = required_value(&mut arguments, "--threads")?;
                let parsed = value
                    .parse::<usize>()
                    .map_err(|_| format!("invalid thread count: {value}"))?;
                if !(1..=MAX_THREADS).contains(&parsed) {
                    return Err(format!(
                        "thread count must be between 1 and {MAX_THREADS}, got {parsed}"
                    ));
                }
                threads = Some(parsed);
            }
            _ => return Err(format!("unknown argument: {argument}")),
        }
    }

    let (range_start, range_end) =
        range.ok_or_else(|| "specify exactly one of --length or --range".to_owned())?;
    let threads = threads.unwrap_or_else(default_thread_count);

    Ok(Some(Arguments {
        range_start,
        range_end,
        threads,
    }))
}

fn required_value(
    arguments: &mut impl Iterator<Item = String>,
    option: &str,
) -> Result<String, String> {
    arguments
        .next()
        .ok_or_else(|| format!("missing value for {option}"))
}

fn parse_length(value: &str) -> Result<u8, String> {
    let length = value
        .parse::<u8>()
        .map_err(|_| format!("invalid sequence length: {value}"))?;
    if !(1..=MAX_SEQUENCE_LENGTH).contains(&length) {
        return Err(format!(
            "sequence length must be between 1 and {MAX_SEQUENCE_LENGTH}, got {length}"
        ));
    }
    Ok(length)
}

fn parse_range(value: &str) -> Result<(u8, u8), String> {
    let parts = value
        .split_once("..=")
        .or_else(|| value.split_once(':'))
        .ok_or_else(|| "range must use START:END or START..=END".to_owned())?;
    let start = parse_length(parts.0)?;
    let end = parse_length(parts.1)?;
    if start > end {
        return Err(format!("range start {start} exceeds range end {end}"));
    }
    Ok((start, end))
}

fn default_thread_count() -> usize {
    std::thread::available_parallelism()
        .map(|count| count.get())
        .unwrap_or(1)
        .min(MAX_THREADS)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn strings(values: &[&str]) -> Vec<String> {
        values.iter().map(|value| (*value).to_owned()).collect()
    }

    #[test]
    fn parses_one_length() {
        assert_eq!(
            parse_arguments(strings(&["--length", "7", "--threads", "3"])).unwrap(),
            Some(Arguments {
                range_start: 7,
                range_end: 7,
                threads: 3,
            })
        );
    }

    #[test]
    fn parses_both_range_forms() {
        for value in ["3:8", "3..=8"] {
            assert_eq!(
                parse_arguments(strings(&["--range", value, "--threads", "2"])).unwrap(),
                Some(Arguments {
                    range_start: 3,
                    range_end: 8,
                    threads: 2,
                })
            );
        }
    }

    #[test]
    fn rejects_conflicting_or_reversed_ranges() {
        assert!(parse_arguments(strings(&["--length", "3", "--range", "3:4"])).is_err());
        assert!(parse_arguments(strings(&["--range", "8:3"])).is_err());
    }
}
