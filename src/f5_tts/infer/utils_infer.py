# A unified script for inference process
# Fixed version with Vietnamese optimization
import os
import sys
from concurrent.futures import ThreadPoolExecutor

os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
sys.path.append(f"{os.path.dirname(os.path.abspath(__file__))}/../../third_party/BigVGAN/")

import hashlib
import re
import tempfile
from importlib.resources import files

import matplotlib

matplotlib.use("Agg")
import matplotlib.pylab as plt
import numpy as np
import torch
import torchaudio
import tqdm
from huggingface_hub import snapshot_download, hf_hub_download
from pydub import AudioSegment, silence
from transformers import pipeline
from vocos import Vocos

from f5_tts.model import CFM
from f5_tts.model.utils import (
    get_tokenizer,
    convert_char_to_pinyin,
)

_ref_audio_cache = {}

device = (
    "cuda"
    if torch.cuda.is_available()
    else "xpu"
    if torch.xpu.is_available()
    else "mps"
    if torch.backends.mps.is_available()
    else "cpu"
)

# -----------------------------------------

target_sample_rate = 24000
n_mel_channels = 100
hop_length = 256
win_length = 1024
n_fft = 1024
mel_spec_type = "vocos"
target_rms = 0.1
cross_fade_duration = 0.15
ode_method = "euler"
nfe_step = 32
cfg_strength = 2.0
sway_sampling_coef = -1.0
speed = 1.0
fix_duration = None


# -----------------------------------------


def chunk_text(text, max_chars=200):
    """
    FIXED: Improved Vietnamese text chunking
    - Support multiple punctuation marks
    - Handle abbreviations properly
    - Better sentence merging logic
    """
    if len(text) <= max_chars:
        return [text]

    # Vietnamese abbreviations to protect
    abbreviations = [
        r'TP\.', r'Tp\.', r'Tr\.', r'CN\.', r'T\d+\.', r'Th\d+\.',
        r'BS\.', r'TS\.', r'PGS\.', r'GS\.', r'v\.v\.', r'v\.v\.\.'
    ]

    # Protect abbreviations
    protected_text = text
    placeholders = {}
    for i, abbr in enumerate(abbreviations):
        matches = list(re.finditer(abbr, protected_text))
        for match in matches:
            placeholder = f"__ABBR{i}_{len(placeholders)}__"
            placeholders[placeholder] = match.group()
            protected_text = protected_text[:match.start()] + placeholder + protected_text[match.end():]

    # Split by sentence endings: . ! ? ;
    sentence_pattern = r'([.!?;]+)\s+'
    parts = re.split(sentence_pattern, protected_text)

    # Reconstruct sentences
    sentences = []
    i = 0
    while i < len(parts):
        if i + 1 < len(parts) and re.match(r'^[.!?;]+$', parts[i + 1]):
            sentence = parts[i] + parts[i + 1]
            sentences.append(sentence.strip())
            i += 2
        else:
            if parts[i].strip():
                sentences.append(parts[i].strip())
            i += 1

    if not sentences:
        # Restore and return original
        for placeholder, original in placeholders.items():
            text = text.replace(placeholder, original)
        return [text]

    # Merge sentences intelligently
    merged = []
    current = ""

    for sentence in sentences:
        word_count = len(sentence.split())

        # Merge very short sentences (< 5 words) with previous
        if word_count < 5 and merged and len(merged[-1]) + len(sentence) + 1 <= max_chars:
            merged[-1] += " " + sentence
        # Add to current if fits
        elif len(current) + len(sentence) + 1 <= max_chars:
            current = current + " " + sentence if current else sentence
        # Start new chunk
        else:
            if current:
                merged.append(current)

            # Force split if single sentence too long
            if len(sentence) > max_chars:
                sub_chunks = force_split_sentence(sentence, max_chars)
                merged.extend(sub_chunks[:-1])
                current = sub_chunks[-1]
            else:
                current = sentence

    if current:
        merged.append(current)

    # Restore abbreviations
    for placeholder, original in placeholders.items():
        merged = [chunk.replace(placeholder, original) for chunk in merged]

    # Filter empty
    merged = [chunk for chunk in merged if chunk.strip()]

    return merged if merged else [text]


def force_split_sentence(sentence, max_chars):
    """Force split long sentence by commas or words"""
    if ',' in sentence:
        parts = sentence.split(',')
        chunks = []
        current = ""

        for part in parts:
            part = part.strip()
            if len(current) + len(part) + 2 <= max_chars:
                current = current + ", " + part if current else part
            else:
                if current:
                    chunks.append(current + ',')
                current = part

        if current:
            chunks.append(current)
        return chunks

    # Split by words
    words = sentence.split()
    chunks = []
    current = ""

    for word in words:
        if len(current) + len(word) + 1 <= max_chars:
            current = current + " " + word if current else word
        else:
            if current:
                chunks.append(current)
            current = word

    if current:
        chunks.append(current)

    return chunks


def load_vocoder(vocoder_name="vocos", is_local=False, local_path="", device=device, hf_cache_dir=None):
    if vocoder_name == "vocos":
        if is_local:
            print(f"Load vocos from local path {local_path}")
            config_path = f"{local_path}/config.yaml"
            model_path = f"{local_path}/pytorch_model.bin"
        else:
            print("Download Vocos from huggingface charactr/vocos-mel-24khz")
            repo_id = "charactr/vocos-mel-24khz"
            config_path = hf_hub_download(repo_id=repo_id, cache_dir=hf_cache_dir, filename="config.yaml")
            model_path = hf_hub_download(repo_id=repo_id, cache_dir=hf_cache_dir, filename="pytorch_model.bin")
        vocoder = Vocos.from_hparams(config_path)
        state_dict = torch.load(model_path, map_location="cpu", weights_only=True)
        from vocos.feature_extractors import EncodecFeatures

        if isinstance(vocoder.feature_extractor, EncodecFeatures):
            encodec_parameters = {
                "feature_extractor.encodec." + key: value
                for key, value in vocoder.feature_extractor.encodec.state_dict().items()
            }
            state_dict.update(encodec_parameters)
        vocoder.load_state_dict(state_dict)
        vocoder = vocoder.eval().to(device)
    elif vocoder_name == "bigvgan":
        try:
            from third_party.BigVGAN import bigvgan
        except ImportError:
            print("You need to follow the README to init submodule and change the BigVGAN source code.")
        if is_local:
            vocoder = bigvgan.BigVGAN.from_pretrained(local_path, use_cuda_kernel=False)
        else:
            local_path = snapshot_download(repo_id="nvidia/bigvgan_v2_24khz_100band_256x", cache_dir=hf_cache_dir)
            vocoder = bigvgan.BigVGAN.from_pretrained(local_path, use_cuda_kernel=False)

        vocoder.remove_weight_norm()
        vocoder = vocoder.eval().to(device)
    return vocoder


asr_pipe = None


def initialize_asr_pipeline(device: str = device, dtype=None):
    if dtype is None:
        dtype = (
            torch.float16
            if "cuda" in device
               and torch.cuda.get_device_properties(device).major >= 6
               and not torch.cuda.get_device_name().endswith("[ZLUDA]")
            else torch.float32
        )
    global asr_pipe
    asr_pipe = pipeline(
        "automatic-speech-recognition",
        model="openai/whisper-large-v3-turbo",
        torch_dtype=dtype,
        device=device,
    )


def transcribe(ref_audio, language=None):
    """FIXED: Better transcription with error handling"""
    global asr_pipe
    if asr_pipe is None:
        initialize_asr_pipeline(device=device)

    try:
        result = asr_pipe(
            ref_audio,
            chunk_length_s=30,
            batch_size=128,
            generate_kwargs={"task": "transcribe", "language": language} if language else {"task": "transcribe"},
            return_timestamps=False,
        )
        transcription = result["text"].strip()

        # Normalize text
        transcription = re.sub(r'\s+', ' ', transcription)

        return transcription
    except Exception as e:
        print(f"⚠️ Transcription error: {e}")
        return ""


def load_checkpoint(model, ckpt_path, device: str, dtype=None, use_ema=True):
    if dtype is None:
        dtype = (
            torch.float16
            if "cuda" in device
               and torch.cuda.get_device_properties(device).major >= 6
               and not torch.cuda.get_device_name().endswith("[ZLUDA]")
            else torch.float32
        )
    model = model.to(dtype)

    ckpt_type = ckpt_path.split(".")[-1]
    if ckpt_type == "safetensors":
        from safetensors.torch import load_file
        checkpoint = load_file(ckpt_path, device=device)
    else:
        checkpoint = torch.load(ckpt_path, map_location=device, weights_only=True)

    if use_ema:
        if ckpt_type == "safetensors":
            checkpoint = {"ema_model_state_dict": checkpoint}
        checkpoint["model_state_dict"] = {
            k.replace("ema_model.", ""): v
            for k, v in checkpoint["ema_model_state_dict"].items()
            if k not in ["initted", "step"]
        }

        for key in ["mel_spec.mel_stft.mel_scale.fb", "mel_spec.mel_stft.spectrogram.window"]:
            if key in checkpoint["model_state_dict"]:
                del checkpoint["model_state_dict"][key]

        model.load_state_dict(checkpoint["model_state_dict"])
    else:
        if ckpt_type == "safetensors":
            checkpoint = {"model_state_dict": checkpoint}
        model.load_state_dict(checkpoint["model_state_dict"])

    del checkpoint
    torch.cuda.empty_cache()

    return model.to(device)


def load_model(
        model_cls,
        model_cfg,
        ckpt_path,
        mel_spec_type=mel_spec_type,
        vocab_file="",
        ode_method=ode_method,
        use_ema=True,
        device=device,
):
    if vocab_file == "":
        vocab_file = str(files("f5_tts").joinpath("infer/examples/vocab.txt"))
    tokenizer = "custom"

    print("\nvocab : ", vocab_file)
    print("token : ", tokenizer)
    print("model : ", ckpt_path, "\n")

    vocab_char_map, vocab_size = get_tokenizer(vocab_file, tokenizer)
    model = CFM(
        transformer=model_cls(**model_cfg, text_num_embeds=vocab_size, mel_dim=n_mel_channels),
        mel_spec_kwargs=dict(
            n_fft=n_fft,
            hop_length=hop_length,
            win_length=win_length,
            n_mel_channels=n_mel_channels,
            target_sample_rate=target_sample_rate,
            mel_spec_type=mel_spec_type,
        ),
        odeint_kwargs=dict(
            method=ode_method,
        ),
        vocab_char_map=vocab_char_map,
    ).to(device)

    dtype = torch.float32 if mel_spec_type == "bigvgan" else None
    model = load_checkpoint(model, ckpt_path, device, dtype=dtype, use_ema=use_ema)

    return model


def remove_silence_edges(audio, silence_threshold=-42):
    """FIXED: Better silence removal"""
    try:
        # Remove silence from start
        non_silent_start_idx = silence.detect_leading_silence(audio, silence_threshold=silence_threshold)
        audio = audio[non_silent_start_idx:]

        # Remove silence from end
        non_silent_end_duration = audio.duration_seconds
        for ms in reversed(audio):
            if ms.dBFS > silence_threshold:
                break
            non_silent_end_duration -= 0.001
        trimmed_audio = audio[: int(non_silent_end_duration * 1000)]

        return trimmed_audio
    except Exception as e:
        print(f"⚠️ Error removing silence: {e}")
        return audio


def preprocess_ref_audio_text(ref_audio_orig, ref_text, clip_short=True, show_info=print, device=device):
    """FIXED: Better audio preprocessing with validation"""
    show_info("Converting audio...")

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
            aseg = AudioSegment.from_file(ref_audio_orig)

            # Validate audio duration
            duration_sec = len(aseg) / 1000.0
            if duration_sec < 3.0:
                show_info(f"⚠️ Warning: Audio too short ({duration_sec:.2f}s). Minimum 3s recommended.")

            if clip_short:
                # Try to find long silence for clipping
                non_silent_segs = silence.split_on_silence(
                    aseg, min_silence_len=1000, silence_thresh=-50, keep_silence=1000, seek_step=10
                )
                non_silent_wave = AudioSegment.silent(duration=0)
                for non_silent_seg in non_silent_segs:
                    if len(non_silent_wave) > 6000 and len(non_silent_wave + non_silent_seg) > 15000:
                        show_info("Audio is over 15s, clipping short. (1)")
                        break
                    non_silent_wave += non_silent_seg

                # Try short silence if previous failed
                if len(non_silent_wave) > 15000:
                    non_silent_segs = silence.split_on_silence(
                        aseg, min_silence_len=100, silence_thresh=-40, keep_silence=1000, seek_step=10
                    )
                    non_silent_wave = AudioSegment.silent(duration=0)
                    for non_silent_seg in non_silent_segs:
                        if len(non_silent_wave) > 6000 and len(non_silent_wave + non_silent_seg) > 15000:
                            show_info("Audio is over 15s, clipping short. (2)")
                            break
                        non_silent_wave += non_silent_seg

                aseg = non_silent_wave

                # Hard limit at 15s
                if len(aseg) > 15000:
                    aseg = aseg[:15000]
                    show_info("Audio is over 15s, clipping short. (3)")

            aseg = remove_silence_edges(aseg) + AudioSegment.silent(duration=50)
            aseg.export(f.name, format="wav")
            ref_audio = f.name

    except Exception as e:
        show_info(f"⚠️ Error processing audio: {e}")
        ref_audio = ref_audio_orig

    # Compute hash for caching
    try:
        with open(ref_audio, "rb") as audio_file:
            audio_data = audio_file.read()
            audio_hash = hashlib.md5(audio_data).hexdigest()
    except Exception as e:
        show_info(f"⚠️ Error computing audio hash: {e}")
        audio_hash = None

    # Handle transcription
    if not ref_text.strip():
        global _ref_audio_cache
        if audio_hash and audio_hash in _ref_audio_cache:
            show_info("Using cached reference text...")
            ref_text = _ref_audio_cache[audio_hash]
        else:
            show_info("No reference text provided, transcribing reference audio...")
            ref_text = transcribe(ref_audio)
            if audio_hash and ref_text:
                _ref_audio_cache[audio_hash] = ref_text
    else:
        show_info("Using custom reference text...")

    # Normalize ref_text
    ref_text = ref_text.strip()
    if not ref_text:
        raise ValueError("Reference text is empty after transcription!")

    # Ensure proper ending punctuation
    if not ref_text.endswith(". ") and not ref_text.endswith("。"):
        if ref_text.endswith("."):
            ref_text += " "
        else:
            ref_text += ". "

    show_info(f"ref_text: {ref_text}")

    return ref_audio, ref_text


def infer_process(
        ref_audio,
        ref_text,
        gen_text,
        model_obj,
        vocoder,
        mel_spec_type=mel_spec_type,
        show_info=print,
        progress=tqdm,
        target_rms=target_rms,
        cross_fade_duration=cross_fade_duration,
        nfe_step=nfe_step,
        cfg_strength=cfg_strength,
        sway_sampling_coef=sway_sampling_coef,
        speed=speed,
        fix_duration=fix_duration,
        device=device,
):
    """FIXED: Better audio loading and chunking logic"""
    # Load audio - try with backend first, fallback without
    try:
        audio, sr = torchaudio.load(ref_audio, backend="soundfile")
    except:
        try:
            audio, sr = torchaudio.load(ref_audio)
        except Exception as e:
            show_info(f"⚠️ Error loading audio: {e}")
            raise

    # FIXED: Better max_chars calculation
    audio_duration = audio.shape[-1] / sr
    ref_text_len = len(ref_text.encode("utf-8"))

    # Calculate chars per second from reference
    chars_per_sec = ref_text_len / audio_duration if audio_duration > 0 else 50

    # Set max_chars with reasonable bounds (150-250)
    max_chars = int(chars_per_sec * 10)  # ~10 seconds per chunk
    max_chars = max(150, min(max_chars, 250))  # Clamp between 150-250

    show_info(f"Audio duration: {audio_duration:.2f}s, chars_per_sec: {chars_per_sec:.1f}, max_chars: {max_chars}")

    # Chunk text
    gen_text_batches = chunk_text(gen_text, max_chars=max_chars)

    show_info(f"Generating audio in {len(gen_text_batches)} batches:")
    for i, batch in enumerate(gen_text_batches):
        show_info(f"  Batch {i + 1}: {batch[:80]}{'...' if len(batch) > 80 else ''}")

    # Call batch process
    return next(
        infer_batch_process(
            (audio, sr),
            ref_text,
            gen_text_batches,
            model_obj,
            vocoder,
            mel_spec_type=mel_spec_type,
            progress=progress,
            target_rms=target_rms,
            cross_fade_duration=cross_fade_duration,
            nfe_step=nfe_step,
            cfg_strength=cfg_strength,
            sway_sampling_coef=sway_sampling_coef,
            speed=speed,
            fix_duration=fix_duration,
            device=device,
        )
    )


def infer_batch_process(
        ref_audio,
        ref_text,
        gen_text_batches,
        model_obj,
        vocoder,
        mel_spec_type="vocos",
        progress=tqdm,
        target_rms=0.1,
        cross_fade_duration=0.15,
        nfe_step=32,
        cfg_strength=2.0,
        sway_sampling_coef=-1,
        speed=1,
        fix_duration=None,
        device=None,
        streaming=False,
        chunk_size=2048,
):
    """FIXED: Better batch processing with proper cross-fade"""
    audio, sr = ref_audio

    # Convert to mono if stereo
    if audio.shape[0] > 1:
        audio = torch.mean(audio, dim=0, keepdim=True)

    # Normalize RMS
    rms = torch.sqrt(torch.mean(torch.square(audio)))
    if rms < target_rms:
        audio = audio * target_rms / rms

    # Resample if needed
    if sr != target_sample_rate:
        resampler = torchaudio.transforms.Resample(sr, target_sample_rate)
        audio = resampler(audio)

    audio = audio.to(device)

    generated_waves = []
    spectrograms = []

    # Ensure ref_text has proper spacing
    if len(ref_text[-1].encode("utf-8")) == 1:
        ref_text = ref_text + " "

    # Process each batch
    for gen_text in (progress.tqdm(gen_text_batches) if progress else gen_text_batches):
        # FIXED: Better speed calculation
        gen_text_len = len(gen_text.encode("utf-8"))
        local_speed = 0.5 if gen_text_len < 20 else speed

        text_list = [ref_text + gen_text]
        final_text_list = convert_char_to_pinyin(text_list)

        ref_audio_len = audio.shape[-1] // hop_length

        if fix_duration is not None:
            duration = int(fix_duration * target_sample_rate / hop_length)
        else:
            ref_text_len = len(ref_text.encode("utf-8"))
            duration = ref_audio_len + int(ref_audio_len / ref_text_len * gen_text_len / local_speed)

        # Inference
        with torch.inference_mode():
            generated, _ = model_obj.sample(
                cond=audio,
                text=final_text_list,
                duration=duration,
                steps=nfe_step,
                cfg_strength=cfg_strength,
                sway_sampling_coef=sway_sampling_coef,
            )

            generated = generated.to(torch.float32)
            generated = generated[:, ref_audio_len:, :]
            generated = generated.permute(0, 2, 1)

            if mel_spec_type == "vocos":
                generated_wave = vocoder.decode(generated)
            elif mel_spec_type == "bigvgan":
                generated_wave = vocoder(generated)

            if rms < target_rms:
                generated_wave = generated_wave * rms / target_rms

            generated_wave = generated_wave.squeeze().cpu().numpy()
            generated_cpu = generated[0].cpu().numpy()

            generated_waves.append(generated_wave)
            spectrograms.append(generated_cpu)

            del generated, _
            torch.cuda.empty_cache()

    # FIXED: Better cross-fade implementation
    if generated_waves:
        if cross_fade_duration <= 0 or len(generated_waves) == 1:
            final_wave = np.concatenate(generated_waves)
        else:
            final_wave = generated_waves[0]

            for i in range(1, len(generated_waves)):
                prev_wave = final_wave
                next_wave = generated_waves[i]

                cross_fade_samples = int(cross_fade_duration * target_sample_rate)
                cross_fade_samples = min(cross_fade_samples, len(prev_wave) // 2, len(next_wave) // 2)

                if cross_fade_samples <= 0:
                    final_wave = np.concatenate([prev_wave, next_wave])
                    continue

                # Extract overlapping regions
                prev_overlap = prev_wave[-cross_fade_samples:]
                next_overlap = next_wave[:cross_fade_samples]

                # Create fade curves
                fade_out = np.linspace(1, 0, cross_fade_samples)
                fade_in = np.linspace(0, 1, cross_fade_samples)

                # Apply cross-fade
                cross_faded_overlap = prev_overlap * fade_out + next_overlap * fade_in

                # Concatenate
                final_wave = np.concatenate([
                    prev_wave[:-cross_fade_samples],
                    cross_faded_overlap,
                    next_wave[cross_fade_samples:]
                ])

        combined_spectrogram = np.concatenate(spectrograms, axis=1)
        yield final_wave, target_sample_rate, combined_spectrogram
    else:
        yield np.array([]), target_sample_rate, None


def remove_silence_for_generated_wav(filename):
    """FIXED: Better silence removal with validation"""
    try:
        aseg = AudioSegment.from_file(filename)
        non_silent_segs = silence.split_on_silence(
            aseg, min_silence_len=1000, silence_thresh=-50, keep_silence=500, seek_step=10
        )

        if not non_silent_segs:
            print("⚠️ No non-silent segments found, keeping original audio")
            return

        non_silent_wave = AudioSegment.silent(duration=0)
        for non_silent_seg in non_silent_segs:
            non_silent_wave += non_silent_seg

        aseg = non_silent_wave
        aseg.export(filename, format="wav")
        print(f"✓ Silence removed from {filename}")
    except Exception as e:
        print(f"⚠️ Error removing silence: {e}")


def save_spectrogram(spectrogram, path):
    """Save spectrogram with error handling"""
    try:
        plt.figure(figsize=(12, 4))
        plt.imshow(spectrogram, origin="lower", aspect="auto")
        plt.colorbar()
        plt.savefig(path)
        plt.close()
    except Exception as e:
        print(f"⚠️ Error saving spectrogram: {e}")