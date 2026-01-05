use dive_deco::{BuehlmannConfig, BuehlmannModel, Deco, DecoModel, DecoStageType, Gas};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::io::{self, Read};

#[derive(Debug, Deserialize)]
struct InputGas {
    o2: f64,
    he: f64,
}

#[derive(Debug, Deserialize)]
struct InputSegment {
    depth_m: f64,
    duration_min: f64,
}

#[derive(Debug, Deserialize)]
struct InputPayload {
    segments: Vec<InputSegment>,
    gas: InputGas,
    gf_low: f64,
    gf_high: f64,
}

#[derive(Debug, Serialize)]
struct OutputStop {
    depth_m: f64,
    duration_min: f64,
}

#[derive(Debug, Serialize)]
struct OutputPayload {
    tool: &'static str,
    tool_version: &'static str,
    model: &'static str,
    gf_low: f64,
    gf_high: f64,

    ceiling_m: f64,
    tts_min: f64,
    ndl_min: Option<u64>,
    deco_required: bool,
    stops: Vec<OutputStop>,

    max_depth_m: f64,
    runtime_min: f64,
    input_hash: String,

    #[serde(skip_serializing_if = "Vec::is_empty")]
    warnings: Vec<String>,

    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
}

fn sha256_hex(s: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(s.as_bytes());
    let digest = hasher.finalize();
    format!("sha256:{}", hex::encode(digest))
}

fn main() {
    // --version support
    let args: Vec<String> = std::env::args().collect();
    if args.len() == 2 && args[1] == "--version" {
        println!("0.1.0");
        return;
    }

    // Read stdin JSON
    let mut input_json = String::new();
    if io::stdin().read_to_string(&mut input_json).is_err() {
        eprintln!("failed to read stdin");
        std::process::exit(2);
    }

    let input_hash = sha256_hex(&input_json);

    let payload: InputPayload = match serde_json::from_str(&input_json) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("invalid json: {e}");
            std::process::exit(3);
        }
    };

    // Basic validation
    if payload.segments.is_empty() {
        eprintln!("no segments");
        std::process::exit(4);
    }
    if !(0.0..=1.0).contains(&payload.gas.o2) || !(0.0..=1.0).contains(&payload.gas.he) {
        eprintln!("invalid gas fractions");
        std::process::exit(5);
    }
    if payload.gas.o2 + payload.gas.he > 1.0 {
        eprintln!("gas fractions exceed 1.0");
        std::process::exit(6);
    }

    // Compute basic metrics
    let max_depth_m = payload
        .segments
        .iter()
        .map(|s| s.depth_m)
        .fold(0.0_f64, f64::max);

    let runtime_min: f64 = payload.segments.iter().map(|s| s.duration_min).sum();

    // Convert gradient factors from fractions (0.0-1.0) to integers (0-100)
    let gf_low = (payload.gf_low * 100.0).round() as u8;
    let gf_high = (payload.gf_high * 100.0).round() as u8;

    // Configure Bühlmann model with gradient factors
    let config = BuehlmannConfig::new().gradient_factors(gf_low, gf_high);
    let mut model = BuehlmannModel::new(config);

    // Create gas mix
    let gas = Gas::new(payload.gas.o2, payload.gas.he);

    // Record each segment (step takes depth in meters, duration in seconds)
    for seg in &payload.segments {
        let seconds = (seg.duration_min * 60.0).round() as usize;
        model.step(&seg.depth_m, &seconds, &gas);
    }

    // Get ceiling (meters) - this is the depth we cannot ascend above
    let ceiling_m = model.ceiling();
    let deco_required = ceiling_m > 0.0;

    // Get NDL (no-deco limit in minutes) - only meaningful if not in deco
    let ndl_min: Option<u64> = if !deco_required {
        let ndl = model.ndl();
        // NDL returns Minutes::MAX for surface/shallow, cap at 999
        if ndl > 999 {
            Some(999)
        } else {
            Some(ndl as u64)
        }
    } else {
        None
    };

    // Calculate deco schedule and TTS
    let available_gases = vec![gas.clone()];
    let Deco { deco_stages, tts } = model.deco(available_gases);

    // TTS is in seconds, convert to minutes
    let tts_min = tts as f64 / 60.0;

    // Extract deco stops (filter out ascent stages, keep only DecoStop)
    let stops: Vec<OutputStop> = deco_stages
        .iter()
        .filter(|stage| matches!(stage.stage_type, DecoStageType::DecoStop))
        .filter(|stage| stage.duration > 0)
        .map(|stage| OutputStop {
            depth_m: stage.start_depth,
            duration_min: stage.duration as f64 / 60.0,
        })
        .collect();

    let out = OutputPayload {
        tool: "diveops-deco-validate",
        tool_version: "0.1.0",
        model: "Bühlmann ZHL-16C",
        gf_low: payload.gf_low,
        gf_high: payload.gf_high,
        ceiling_m,
        tts_min,
        ndl_min,
        deco_required,
        stops,
        max_depth_m,
        runtime_min,
        input_hash,
        warnings: vec![],
        error: None,
    };

    match serde_json::to_string(&out) {
        Ok(s) => println!("{s}"),
        Err(e) => {
            eprintln!("failed to serialize output: {e}");
            std::process::exit(7);
        }
    }
}
