import argparse
import codecs
import os
import re
from datetime import datetime
from importlib.resources import files
from pathlib import Path

import numpy as np
import soundfile as sf
import tomli
from cached_path import cached_path
from omegaconf import OmegaConf

from f5_tts.infer.utils_infer import (
    mel_spec_type,
    target_rms,
    cross_fade_duration,
    nfe_step,
    cfg_strength,
    sway_sampling_coef,
    speed,
    fix_duration,
    infer_process,
    load_model,
    load_vocoder,
    preprocess_ref_audio_text,
    remove_silence_for_generated_wav,
)
from f5_tts.model import DiT, UNetT  # noqa: F401. used for config

parser = argparse.ArgumentParser(
    prog="python3 infer-cli.py",
    description="Commandline interface for E2/F5 TTS with Advanced Batch Processing.",
    epilog="Specify options above to override one or more settings from config.",
)
parser.add_argument(
    "-c",
    "--config",
    type=str,
    default=os.path.join(files("f5_tts").joinpath("infer/examples/basic"), "basic.toml"),
    help="The configuration file, default see infer/examples/basic/basic.toml",
)

parser.add_argument(
    "-m",
    "--model",
    type=str,
    help="The model name: F5TTS_v1_Base | F5TTS_Base | E2TTS_Base | etc.",
)
parser.add_argument(
    "-mc",
    "--model_cfg",
    type=str,
    help="The path to F5-TTS model config file .yaml",
)
parser.add_argument(
    "-p",
    "--ckpt_file",
    type=str,
    help="The path to model checkpoint .pt, leave blank to use default",
)
parser.add_argument(
    "-v",
    "--vocab_file",
    type=str,
    help="The path to vocab file .txt, leave blank to use default",
)
parser.add_argument(
    "-r",
    "--ref_audio",
    type=str,
    help="The reference audio file.",
)
parser.add_argument(
    "-s",
    "--ref_text",
    type=str,
    help="The transcript/subtitle for the reference audio",
)
parser.add_argument(
    "-t",
    "--gen_text",
    type=str,
    help="The text to make model synthesize a speech",
)
parser.add_argument(
    "-f",
    "--gen_file",
    type=str,
    help="The file with text to generate, will ignore --gen_text",
)
parser.add_argument(
    "-o",
    "--output_dir",
    type=str,
    help="The path to output folder",
)
parser.add_argument(
    "-w",
    "--output_file",
    type=str,
    help="The name of output file",
)
parser.add_argument(
    "--save_chunk",
    action="store_true",
    help="To save each audio chunks during inference",
)
parser.add_argument(
    "--remove_silence",
    action="store_true",
    help="To remove long silence found in ouput",
)
parser.add_argument(
    "--load_vocoder_from_local",
    action="store_true",
    help="To load vocoder from local dir, default to ../checkpoints/vocos-mel-24khz",
)
parser.add_argument(
    "--vocoder_name",
    type=str,
    choices=["vocos", "bigvgan"],
    help=f"Used vocoder name: vocos | bigvgan, default {mel_spec_type}",
)
parser.add_argument(
    "--target_rms",
    type=float,
    help=f"Target output speech loudness normalization value, default {target_rms}",
)
parser.add_argument(
    "--cross_fade_duration",
    type=float,
    help=f"Duration of cross-fade between audio segments in seconds, default {cross_fade_duration}",
)
parser.add_argument(
    "--nfe_step",
    type=int,
    help=f"The number of function evaluation (denoising steps), default {nfe_step}. Higher = better quality but slower (recommended: 32-64 for best quality)",
)
parser.add_argument(
    "--cfg_strength",
    type=float,
    help=f"Classifier-free guidance strength, default {cfg_strength}. Higher = more adherence to prompt (recommended: 2.0-3.0)",
)
parser.add_argument(
    "--sway_sampling_coef",
    type=float,
    help=f"Sway Sampling coefficient, default {sway_sampling_coef}. Negative values (-1.0) can improve quality",
)
parser.add_argument(
    "--speed",
    type=float,
    help=f"The speed of the generated audio, default {speed}",
)
parser.add_argument(
    "--fix_duration",
    type=float,
    help=f"Fix the total duration (ref and gen audios) in seconds, default {fix_duration}",
)
parser.add_argument(
    "--whisper_language",
    type=str,
    default="vi",
    help="Language code for Whisper transcription (e.g., 'vi', 'en'), default is 'vi'",
)
parser.add_argument(
    "--ref_audio_min_duration",
    type=float,
    default=3.0,
    help="Minimum duration (seconds) for reference audio. Audio shorter than this will be rejected (default: 3.0)",
)
parser.add_argument(
    "--ref_audio_max_duration",
    type=float,
    default=15.0,
    help="Maximum duration (seconds) for reference audio. Longer audio will be trimmed (default: 15.0)",
)
parser.add_argument(
    "--enhance_quality",
    action="store_true",
    help="Enable quality enhancement mode (increases nfe_step to 64, cfg_strength to 2.5, and uses optimal sway_sampling_coef)",
)
args = parser.parse_args()

# config file
config = tomli.load(open(args.config, "rb"))

# command-line interface parameters
model = args.model or config.get("model", "F5TTS_v1_Base")
ckpt_file = args.ckpt_file or config.get("ckpt_file", "")
vocab_file = args.vocab_file or config.get("vocab_file", "")

ref_audio = args.ref_audio or config.get("ref_audio", "infer/examples/basic/basic_ref_en.wav")

# Fixed: Simplified ref_text logic
if args.ref_text is not None:
    ref_text = args.ref_text
else:
    ref_text = config.get("ref_text", None)

gen_text = args.gen_text or config.get("gen_text", "Here we generate something just for test.")
gen_file = args.gen_file or config.get("gen_file", "")

output_dir = args.output_dir or config.get("output_dir", "tests")
output_file = args.output_file or config.get(
    "output_file", f"infer_cli_{datetime.now().strftime(r'%Y%m%d_%H%M%S')}.wav"
)

save_chunk = args.save_chunk or config.get("save_chunk", False)
remove_silence = args.remove_silence or config.get("remove_silence", False)
load_vocoder_from_local = args.load_vocoder_from_local or config.get("load_vocoder_from_local", False)

vocoder_name = args.vocoder_name or config.get("vocoder_name", mel_spec_type)
target_rms = args.target_rms or config.get("target_rms", target_rms)
cross_fade_duration = args.cross_fade_duration or config.get("cross_fade_duration", cross_fade_duration)

# Quality enhancement mode
enhance_quality = args.enhance_quality or config.get("enhance_quality", False)

if enhance_quality:
    # Override with optimal quality settings
    nfe_step = args.nfe_step or config.get("nfe_step", 64)  # Increased for better quality
    cfg_strength = args.cfg_strength or config.get("cfg_strength", 2.5)  # Better guidance
    sway_sampling_coef = args.sway_sampling_coef or config.get("sway_sampling_coef", -1.0)  # Improved sampling
    print("🎯 Quality Enhancement Mode ENABLED")
else:
    nfe_step = args.nfe_step or config.get("nfe_step", nfe_step)
    cfg_strength = args.cfg_strength or config.get("cfg_strength", cfg_strength)
    sway_sampling_coef = args.sway_sampling_coef or config.get("sway_sampling_coef", sway_sampling_coef)

speed = args.speed or config.get("speed", speed)
fix_duration = args.fix_duration or config.get("fix_duration", fix_duration)
whisper_language = args.whisper_language or config.get("whisper_language", "vi")
ref_audio_min_duration = args.ref_audio_min_duration or config.get("ref_audio_min_duration", 3.0)
ref_audio_max_duration = args.ref_audio_max_duration or config.get("ref_audio_max_duration", 15.0)

# patches for pip pkg user
if "infer/examples/" in ref_audio:
    ref_audio = str(files("f5_tts").joinpath(f"{ref_audio}"))
if "infer/examples/" in gen_file:
    gen_file = str(files("f5_tts").joinpath(f"{gen_file}"))
if "voices" in config:
    for voice in config["voices"]:
        voice_ref_audio = config["voices"][voice]["ref_audio"]
        if "infer/examples/" in voice_ref_audio:
            config["voices"][voice]["ref_audio"] = str(files("f5_tts").joinpath(f"{voice_ref_audio}"))

# ignore gen_text if gen_file provided
if gen_file:
    if not os.path.exists(gen_file):
        raise FileNotFoundError(f"Generation text file not found: {gen_file}")
    gen_text = codecs.open(gen_file, "r", "utf-8").read()

# Validate ref_audio exists
if not os.path.exists(ref_audio):
    raise FileNotFoundError(f"Reference audio file not found: {ref_audio}")

# output path
wave_path = Path(output_dir) / output_file
if save_chunk:
    output_chunk_dir = os.path.join(output_dir, f"{Path(output_file).stem}_chunks")
    if not os.path.exists(output_chunk_dir):
        os.makedirs(output_chunk_dir)

# load vocoder
if vocoder_name == "vocos":
    vocoder_local_path = "../checkpoints/vocos-mel-24khz"
elif vocoder_name == "bigvgan":
    vocoder_local_path = "../checkpoints/bigvgan_v2_24khz_100band_256x"

vocoder = load_vocoder(vocoder_name=vocoder_name, is_local=load_vocoder_from_local, local_path=vocoder_local_path)

# load TTS model
model_cfg = OmegaConf.load(
    args.model_cfg or config.get("model_cfg", str(files("f5_tts").joinpath(f"configs/{model}.yaml")))
).model
model_cls = globals()[model_cfg.backbone]

repo_name, ckpt_step, ckpt_type = "F5-TTS", 1250000, "safetensors"

if model != "F5TTS_Base":
    assert vocoder_name == model_cfg.mel_spec.mel_spec_type

# override for previous models
if model == "F5TTS_Base":
    if vocoder_name == "vocos":
        ckpt_step = 1200000
    elif vocoder_name == "bigvgan":
        model = "F5TTS_Base_bigvgan"
        ckpt_type = "pt"
elif model == "E2TTS_Base":
    repo_name = "E2-TTS"
    ckpt_step = 1200000

if not ckpt_file:
    ckpt_file = str(cached_path(f"hf://SWivid/{repo_name}/{model}/model_{ckpt_step}.{ckpt_type}"))

print(f"Using {model}...")
ema_model = load_model(model_cls, model_cfg.arch, ckpt_file, mel_spec_type=vocoder_name, vocab_file=vocab_file)

# inference process
from faster_whisper import WhisperModel
import librosa


def sanitize_filename(text):
    """Remove or replace characters that are invalid in filenames."""
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', text)
    sanitized = sanitized.strip()
    if len(sanitized) > 200:
        sanitized = sanitized[:200]
    return sanitized


def validate_and_process_audio(audio_path, min_duration=3.0, max_duration=15.0):
    """
    Validate reference audio quality and duration.
    Returns: (is_valid, message, processed_audio_path)
    """
    try:
        # Load audio to check duration and quality
        audio_data, sr = sf.read(audio_path)

        # Convert to mono if stereo
        if len(audio_data.shape) > 1:
            audio_data = np.mean(audio_data, axis=1)

        duration = len(audio_data) / sr

        # Check minimum duration
        if duration < min_duration:
            return False, f"Audio too short ({duration:.2f}s < {min_duration}s). Use longer reference audio.", None

        # Trim if too long
        if duration > max_duration:
            print(
                f"  ⚠ Audio duration ({duration:.2f}s) exceeds max ({max_duration}s). Trimming to first {max_duration}s...")
            audio_data = audio_data[:int(max_duration * sr)]
            duration = max_duration

        # Check for silence/low volume
        rms = np.sqrt(np.mean(audio_data ** 2))
        if rms < 0.01:  # Very low volume
            print(f"  ⚠ Warning: Audio has very low volume (RMS: {rms:.4f}). Consider using louder reference audio.")

        # Save processed audio if modifications were made
        processed_path = audio_path
        if duration != len(audio_data) / sr:
            processed_path = audio_path.replace(".wav", "_processed.wav")
            sf.write(processed_path, audio_data, sr)
            print(f"  ✓ Saved processed audio to: {processed_path}")

        return True, f"Valid audio ({duration:.2f}s, RMS: {rms:.4f})", processed_path

    except Exception as e:
        return False, f"Failed to validate audio: {str(e)}", None


def transcribe_with_whisper(whisper_model, audio_path, language="vi"):
    """Transcribe audio file with error handling and quality checks."""
    try:
        print(f"  -> Transcribing {audio_path} with Faster-Whisper (language: {language})...")

        # Transcribe with word-level timestamps for better accuracy
        segments, info = whisper_model.transcribe(
            audio_path,
            language=language,
            word_timestamps=True,
            vad_filter=True,  # Use VAD to filter out non-speech
            vad_parameters=dict(min_silence_duration_ms=500)
        )

        transcription = "".join([segment.text for segment in segments]).strip()

        if not transcription:
            raise ValueError(f"Transcription is empty for {audio_path}. Audio may contain no speech.")

        # Clean up transcription
        transcription = re.sub(r'\s+', ' ', transcription)  # Remove extra spaces

        print(f"  -> Transcribed successfully: {transcription[:100]}{'...' if len(transcription) > 100 else ''}")
        return transcription

    except Exception as e:
        raise RuntimeError(f"Whisper transcription failed for {audio_path}: {str(e)}")


def normalize_text_for_tts(text):
    """Normalize text for better TTS quality."""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # Add proper punctuation if missing (helps with prosody)
    if text and text[-1] not in '.!?,;:':
        text = text + '.'

    return text


def main():
    # Load Whisper model with better settings
    try:
        print("Loading Faster-Whisper model...")
        # Use 'large-v3' for better accuracy if available, else 'base'
        whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
        print("✓ Whisper model loaded successfully.\n")
    except Exception as e:
        raise RuntimeError(f"Failed to load Whisper model: {str(e)}")

    main_voice = {"ref_audio": ref_audio, "ref_text": ref_text}
    if "voices" not in config:
        voices = {"main": main_voice}
    else:
        voices = config["voices"]
        voices["main"] = main_voice

    if "main" not in voices:
        raise ValueError("No 'main' voice configured.")

    # ----- LOG global config -----
    print("\n" + "=" * 50)
    print("CONFIGURATION")
    print("=" * 50)
    print(f"Model           : {model}")
    print(f"Vocoder         : {vocoder_name}")
    print(f"Output          : {output_dir}/{output_file}")
    print(f"NFE Steps       : {nfe_step} {'(QUALITY MODE ✓)' if enhance_quality else ''}")
    print(f"CFG Strength    : {cfg_strength}")
    print(f"Sway Coef       : {sway_sampling_coef}")
    print(f"Speed           : {speed}")
    print(f"Target RMS      : {target_rms}")
    print(f"Cross Fade      : {cross_fade_duration}s")
    print(f"Whisper Lang    : {whisper_language}")
    print(f"Ref Audio Range : {ref_audio_min_duration}s - {ref_audio_max_duration}s")
    print("=" * 50 + "\n")

    # ----- Process voices + Whisper -----
    for voice in voices:
        print(f"📢 Processing voice: {voice}")
        voice_ref_audio = voices[voice]["ref_audio"]
        voice_ref_text = voices[voice].get("ref_text")

        print(f"  Audio source: {voice_ref_audio}")

        # Validate reference audio exists
        if not os.path.exists(voice_ref_audio):
            raise FileNotFoundError(f"Reference audio for voice '{voice}' not found: {voice_ref_audio}")

        # Validate audio quality and duration
        is_valid, message, processed_path = validate_and_process_audio(
            voice_ref_audio,
            min_duration=ref_audio_min_duration,
            max_duration=ref_audio_max_duration
        )

        if not is_valid:
            raise ValueError(f"Invalid reference audio for voice '{voice}': {message}")

        print(f"  ✓ {message}")

        # Use processed audio path
        if processed_path != voice_ref_audio:
            voices[voice]["ref_audio"] = processed_path

        # Auto-transcribe if ref_text is not provided
        if not voice_ref_text:
            voices[voice]["ref_text"] = transcribe_with_whisper(
                whisper_model,
                voices[voice]["ref_audio"],
                language=whisper_language
            )
        else:
            # Normalize provided text
            voices[voice]["ref_text"] = normalize_text_for_tts(voice_ref_text)
            print(f"  ✓ Using provided ref_text: {voices[voice]['ref_text'][:100]}...")

        # Preprocess audio and text
        try:
            voices[voice]["ref_audio"], voices[voice]["ref_text"] = preprocess_ref_audio_text(
                voices[voice]["ref_audio"],
                voices[voice]["ref_text"]
            )
        except Exception as e:
            raise RuntimeError(f"Failed to preprocess voice '{voice}': {str(e)}")

        print(f"  ✓ Preprocessed successfully\n")

    # ----- Generate audio -----
    generated_audio_segments = []
    reg1 = r"(?=\[\w+\])"
    chunks = re.split(reg1, gen_text)
    reg2 = r"\[(\w+)\]"

    print(f"🎙️ Starting generation ({len([c for c in chunks if c.strip()])} chunks)...\n")

    for idx, text in enumerate(chunks):
        if not text.strip():
            continue

        match = re.match(reg2, text)
        if match:
            voice = match[1]
        else:
            voice = "main"

        if voice not in voices:
            print(f"⚠ Voice '{voice}' not found, using 'main'")
            voice = "main"

        text = re.sub(reg2, "", text)
        ref_audio_ = voices[voice]["ref_audio"]
        ref_text_ = voices[voice]["ref_text"]
        gen_text_ = normalize_text_for_tts(text.strip())

        if not gen_text_:
            continue

        # ----- LOG batch -----
        print(f"[Batch {idx + 1}] Voice: {voice}")
        print(f"  Text: {gen_text_[:80]}{'...' if len(gen_text_) > 80 else ''}")

        try:
            audio_segment, final_sample_rate, spectragram = infer_process(
                ref_audio_,
                ref_text_,
                gen_text_,
                ema_model,
                vocoder,
                mel_spec_type=vocoder_name,
                target_rms=target_rms,
                cross_fade_duration=cross_fade_duration,
                nfe_step=nfe_step,
                cfg_strength=cfg_strength,
                sway_sampling_coef=sway_sampling_coef,
                speed=speed,
                fix_duration=fix_duration,
            )
            generated_audio_segments.append(audio_segment)

            duration = len(audio_segment) / final_sample_rate
            print(f"  ✓ Generated {duration:.2f}s")

            if save_chunk:
                safe_name = sanitize_filename(gen_text_)
                chunk_filename = f"{len(generated_audio_segments) - 1:03d}_{safe_name}.wav"
                chunk_path = os.path.join(output_chunk_dir, chunk_filename)
                sf.write(chunk_path, audio_segment, final_sample_rate)
                print(f"  ✓ Saved chunk: {chunk_filename}")

        except Exception as e:
            print(f"  ✗ ERROR: {str(e)}")
            print(f"  → Skipping chunk and continuing...\n")
            continue

    if not generated_audio_segments:
        raise RuntimeError("No audio segments generated. Check input text and configuration.")

    # Concatenate all segments
    final_wave = np.concatenate(generated_audio_segments)

    # Create output directory
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Save final output
    with open(wave_path, "wb") as f:
        sf.write(f.name, final_wave, final_sample_rate)

        duration = len(final_wave) / final_sample_rate

        print("\n" + "=" * 50)
        print("GENERATION COMPLETE")
        print("=" * 50)
        print(f"Output file  : {f.name}")
        print(f"Sample rate  : {final_sample_rate} Hz")
        print(f"Duration     : {duration:.2f}s")
        print(f"Segments     : {len(generated_audio_segments)}")

        if remove_silence:
            print("\nRemoving silence...")
            try:
                remove_silence_for_generated_wav(f.name)
                print("✓ Silence removed")
            except Exception as e:
                print(f"⚠ Warning: Failed to remove silence: {str(e)}")

        print("=" * 50)
        print("✓ SUCCESS!\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n{'=' * 50}")
        print(f"✗ ERROR: {str(e)}")
        print(f"{'=' * 50}\n")
        raise