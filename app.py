import sys
import os
import sqlite3
import time
import traceback
import uuid
import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf
import torch
from omegaconf import OmegaConf
from importlib.resources import files

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

# Import F5-TTS inference utilities
from f5_tts.infer.utils_infer import (
    load_model,
    load_vocoder,
    infer_process,
    preprocess_ref_audio_text
)
from f5_tts.model import DiT, UNetT
from faster_whisper import WhisperModel
from flask import Flask, request, jsonify, render_template, g

app = Flask(__name__, static_url_path="/static", static_folder="static", template_folder="templates")

# Configuration
OUTPUT_DIR = "static/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[INIT] Using device: {DEVICE}")

# Global variables
F5TTS_MODEL = None
VOCODER = None
WHISPER_MODEL = None
TARGET_SAMPLE_RATE = 24000

# ========================================
# CRITICAL FIX: Load model config from YAML exactly like CLI!
# ========================================
MODEL_NAME = "F5TTS_Base"  # Hoặc model bạn đang dùng
VOCAB_FILE = "data/Emilia_ZH_EN_pinyin/vocab.txt"
CKPT_FILE = "ckpts/your_training_dataset/model_last.pt"

# Database config
DATABASE = os.path.join(app.root_path, 'app.db')


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def init_db():
    """Initialize database with schema"""
    with app.app_context():
        db = get_db()
        # Create generated_audios table for history
        db.execute('''
            CREATE TABLE IF NOT EXISTS generated_audios (
                audio_id INTEGER PRIMARY KEY AUTOINCREMENT,
                text_input TEXT NOT NULL,
                voice_sample TEXT,
                audio_path TEXT NOT NULL,
                spectrogram_path TEXT,
                duration REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db.commit()
        print("[DB] Database initialized successfully")


def save_audio_history(text_input, voice_sample, audio_path, spectrogram_path=None, duration=None):
    """Save generated audio to history"""
    try:
        db = get_db()
        db.execute('''
            INSERT INTO generated_audios (text_input, voice_sample, audio_path, spectrogram_path, duration)
            VALUES (?, ?, ?, ?, ?)
        ''', (text_input, voice_sample, audio_path, spectrogram_path, duration))
        db.commit()
        print(f"[DB] Saved audio history: {audio_path}")
        return True
    except Exception as e:
        print(f"[DB ERROR] Failed to save history: {e}")
        return False


def get_audio_history(limit=20):
    """Get audio history list"""
    try:
        db = get_db()
        cursor = db.execute('''
            SELECT audio_id, text_input, voice_sample, audio_path, spectrogram_path, duration, created_at
            FROM generated_audios
            ORDER BY created_at DESC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"[DB ERROR] Failed to get history: {e}")
        return []


def delete_audio_history(audio_id):
    """Delete audio from history"""
    try:
        db = get_db()
        # Get file paths first
        cursor = db.execute('SELECT audio_path, spectrogram_path FROM generated_audios WHERE audio_id = ?', (audio_id,))
        row = cursor.fetchone()
        if row:
            # Delete files - handle path correctly
            for path_key in ['audio_path', 'spectrogram_path']:
                if row[path_key]:
                    # Remove leading slash and convert to proper path
                    file_path = row[path_key].lstrip('/')
                    # On Windows, also handle forward slashes
                    file_path = file_path.replace('/', os.sep)
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                            print(f"[DB] Deleted file: {file_path}")
                        except Exception as e:
                            print(f"[WARN] Could not delete file {file_path}: {e}")
            
            # Delete from DB
            db.execute('DELETE FROM generated_audios WHERE audio_id = ?', (audio_id,))
            db.commit()
            print(f"[DB] Deleted audio history: {audio_id}")
            return True
    except Exception as e:
        print(f"[DB ERROR] Failed to delete history: {e}")
    return False


# Voice samples
VOICE_SAMPLES = [
    {"id": "male", "name": "Giọng đọc tin tức (Nữ)", "file_path": "voices/male.mp3", "icon": "news"},
    {"id": "female", "name": "Giọng kể chuyện (Nam)", "file_path": "voices/female.mp3", "icon": "story"},
]


def log_time(start_time, message):
    elapsed = time.time() - start_time
    print(f"[TIME] {message}: {elapsed:.3f}s")
    return time.time()


def calculate_wer(reference, hypothesis):
    """
    Calculate Word Error Rate (WER)
    WER = (S + D + I) / N
    where S = substitutions, D = deletions, I = insertions, N = words in reference
    """
    ref_words = reference.lower().split()
    hyp_words = hypothesis.lower().split()
    
    # Dynamic programming for edit distance
    d = [[0] * (len(hyp_words) + 1) for _ in range(len(ref_words) + 1)]
    
    for i in range(len(ref_words) + 1):
        d[i][0] = i
    for j in range(len(hyp_words) + 1):
        d[0][j] = j
    
    for i in range(1, len(ref_words) + 1):
        for j in range(1, len(hyp_words) + 1):
            if ref_words[i-1] == hyp_words[j-1]:
                d[i][j] = d[i-1][j-1]
            else:
                d[i][j] = min(
                    d[i-1][j] + 1,      # deletion
                    d[i][j-1] + 1,      # insertion
                    d[i-1][j-1] + 1     # substitution
                )
    
    if len(ref_words) == 0:
        return 0.0 if len(hyp_words) == 0 else 1.0
    
    return d[len(ref_words)][len(hyp_words)] / len(ref_words)


def calculate_cer(reference, hypothesis):
    """
    Calculate Character Error Rate (CER)
    CER = (S + D + I) / N
    where S = substitutions, D = deletions, I = insertions, N = characters in reference
    """
    ref_chars = list(reference.lower().replace(" ", ""))
    hyp_chars = list(hypothesis.lower().replace(" ", ""))
    
    # Dynamic programming for edit distance
    d = [[0] * (len(hyp_chars) + 1) for _ in range(len(ref_chars) + 1)]
    
    for i in range(len(ref_chars) + 1):
        d[i][0] = i
    for j in range(len(hyp_chars) + 1):
        d[0][j] = j
    
    for i in range(1, len(ref_chars) + 1):
        for j in range(1, len(hyp_chars) + 1):
            if ref_chars[i-1] == hyp_chars[j-1]:
                d[i][j] = d[i-1][j-1]
            else:
                d[i][j] = min(
                    d[i-1][j] + 1,
                    d[i][j-1] + 1,
                    d[i-1][j-1] + 1
                )
    
    if len(ref_chars) == 0:
        return 0.0 if len(hyp_chars) == 0 else 1.0
    
    return d[len(ref_chars)][len(hyp_chars)] / len(ref_chars)


def evaluate_audio_quality(audio_path, original_text, lang="vi"):
    """
    Transcribe generated audio and calculate WER/CER against original text
    """
    try:
        load_whisper_model()
        
        print(f"[EVAL] Transcribing generated audio for quality evaluation...")
        segments, info = WHISPER_MODEL.transcribe(audio_path, language=lang)
        transcribed_text = " ".join([segment.text.strip() for segment in segments])
        
        # Safe print with length check
        orig_preview = original_text[:100] if len(original_text) > 0 else "(empty)"
        trans_preview = transcribed_text[:100] if len(transcribed_text) > 0 else "(empty)"
        print(f"[EVAL] Original: {orig_preview}...")
        print(f"[EVAL] Transcribed: {trans_preview}...")
        
        # Handle empty texts
        if not original_text.strip() or not transcribed_text.strip():
            print("[EVAL] Warning: Empty text detected, skipping WER/CER calculation")
            return {
                "transcribed_text": transcribed_text,
                "wer": None,
                "cer": None,
                "wer_percent": "N/A",
                "cer_percent": "N/A"
            }
        
        wer = calculate_wer(original_text, transcribed_text)
        cer = calculate_cer(original_text, transcribed_text)
        
        print(f"[EVAL] WER: {wer:.2%}, CER: {cer:.2%}")
        
        return {
            "transcribed_text": transcribed_text,
            "wer": wer,
            "cer": cer,
            "wer_percent": f"{wer:.1%}",
            "cer_percent": f"{cer:.1%}"
        }
    except Exception as e:
        print(f"[EVAL ERROR] Failed to evaluate: {e}")
        traceback.print_exc()
        return {
            "transcribed_text": "",
            "wer": None,
            "cer": None,
            "wer_percent": "N/A",
            "cer_percent": "N/A"
        }


def load_f5tts_model():
    """
    FIXED: Load model EXACTLY like CLI - using YAML config!
    This is the critical fix!
    """
    global F5TTS_MODEL, VOCODER

    if F5TTS_MODEL is not None and VOCODER is not None:
        print("[INFO] Models already loaded, skipping...")
        return

    print("[LOADING] Loading F5-TTS model and vocoder...")
    start_time = time.time()

    try:
        # Validate files exist
        if not os.path.exists(VOCAB_FILE):
            raise FileNotFoundError(f"Vocab file not found: {VOCAB_FILE}")
        if not os.path.exists(CKPT_FILE):
            raise FileNotFoundError(f"Checkpoint file not found: {CKPT_FILE}")

        print(f"[INFO] Model: {MODEL_NAME}")
        print(f"[INFO] Checkpoint: {CKPT_FILE}")
        print(f"[INFO] Vocab: {VOCAB_FILE}")

        # ========================================
        # CRITICAL: Load model config from YAML exactly like CLI!
        # ========================================
        yaml_config_path = str(files("f5_tts").joinpath(f"configs/{MODEL_NAME}.yaml"))

        if not os.path.exists(yaml_config_path):
            print(f"[WARN] YAML config not found at {yaml_config_path}")
            print(f"[WARN] Trying alternative path...")
            # Try relative path
            alt_path = f"configs/{MODEL_NAME}.yaml"
            if os.path.exists(alt_path):
                yaml_config_path = alt_path
            else:
                raise FileNotFoundError(f"Cannot find {MODEL_NAME}.yaml config file")

        print(f"[INFO] Loading config from: {yaml_config_path}")

        # Load config using OmegaConf exactly like CLI
        model_cfg_full = OmegaConf.load(yaml_config_path)
        model_cfg = model_cfg_full.model

        print(f"[INFO] Model config loaded:")
        print(f"  - backbone: {model_cfg.backbone}")
        print(f"  - arch: {model_cfg.arch}")

        # Get model class from config
        model_cls = globals()[model_cfg.backbone]  # DiT or UNetT
        print(f"[INFO] Using model class: {model_cls.__name__}")

        # Load model exactly like CLI
        F5TTS_MODEL = load_model(
            model_cls=model_cls,
            model_cfg=model_cfg.arch,  # Use arch from YAML!
            ckpt_path=CKPT_FILE,
            vocab_file=VOCAB_FILE,
            mel_spec_type="vocos",
            device=DEVICE
        )

        F5TTS_MODEL.eval()
        log_time(start_time, "Loaded F5-TTS model")

        # Load vocoder
        VOCODER = load_vocoder(vocoder_name="vocos", device=DEVICE)
        log_time(start_time, "Loaded Vocoder")

        print("[SUCCESS] F5-TTS models loaded successfully!")

        # Print model info
        total_params = sum(p.numel() for p in F5TTS_MODEL.parameters())
        print(f"[INFO] Total parameters: {total_params:,}")

    except Exception as e:
        print(f"[ERROR] Failed to load F5-TTS models: {e}")
        traceback.print_exc()
        raise


def load_whisper_model():
    """Load Whisper model"""
    global WHISPER_MODEL

    if WHISPER_MODEL is not None:
        print("[INFO] Whisper model already loaded, skipping...")
        return

    print("[LOADING] Loading Whisper model...")
    start_time = time.time()

    try:
        WHISPER_MODEL = WhisperModel("base", device="cpu", compute_type="int8")
        log_time(start_time, "Loaded Whisper model")
        print("[SUCCESS] Whisper model loaded successfully!")
    except Exception as e:
        print(f"[ERROR] Failed to load Whisper model: {e}")
        traceback.print_exc()
        raise


def unload_models():
    """Unload models to free VRAM"""
    global F5TTS_MODEL, VOCODER, WHISPER_MODEL

    print("[CLEANUP] Unloading models to free VRAM...")

    if F5TTS_MODEL is not None:
        del F5TTS_MODEL
        F5TTS_MODEL = None
        print("[INFO] F5-TTS model unloaded")

    if VOCODER is not None:
        del VOCODER
        VOCODER = None
        print("[INFO] Vocoder unloaded")

    if WHISPER_MODEL is not None:
        del WHISPER_MODEL
        WHISPER_MODEL = None
        print("[INFO] Whisper model unloaded")

    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        print("[INFO] CUDA cache cleared")

    print("[SUCCESS] Models unloaded and VRAM freed")


@torch.no_grad()
def generate_audio(gen_text, ref_audio_path, ref_text, speed=1.0):
    """
    Generate audio exactly like CLI
    """
    start_total = time.time()

    try:
        # Load models if needed
        load_f5tts_model()

        print(f"[INFO] Generation parameters:")
        print(f"  - ref_audio: {ref_audio_path}")
        print(f"  - ref_text ({len(ref_text)} chars): {ref_text[:100]}...")
        print(f"  - gen_text ({len(gen_text)} chars): {gen_text[:100]}...")
        print(f"  - speed: {speed}")
        print(f"  - device: {DEVICE}")

        # Preprocess audio and text exactly like CLI
        print("[PREPROCESSING] Processing reference audio and text...")
        processed_ref_audio, processed_ref_text = preprocess_ref_audio_text(
            ref_audio_path,
            ref_text,
            clip_short=True,
            show_info=print,
            device=DEVICE
        )

        print(f"[INFO] Preprocessed:")
        print(f"  - ref_audio: {processed_ref_audio}")
        print(f"  - ref_text: {processed_ref_text[:100]}...")

        # Generate with exact CLI parameters
        audio_output, final_sample_rate, spectrogram = infer_process(
            ref_audio=processed_ref_audio,
            ref_text=processed_ref_text,
            gen_text=gen_text,
            model_obj=F5TTS_MODEL,
            vocoder=VOCODER,
            mel_spec_type="vocos",
            speed=speed,
            target_rms=0.1,
            cross_fade_duration=0.15,
            nfe_step=32,
            cfg_strength=2.0,
            sway_sampling_coef=-1.0,
            device=DEVICE
        )

        log_time(start_total, "Total generation time")

        print(f"[INFO] Generated audio:")
        print(f"  - Shape: {audio_output.shape if hasattr(audio_output, 'shape') else len(audio_output)}")
        print(f"  - Sample rate: {final_sample_rate}")
        print(f"  - Duration: {len(audio_output) / final_sample_rate:.2f}s")

        return audio_output, final_sample_rate

    except Exception as e:
        print(f"[ERROR] Generation failed: {e}")
        traceback.print_exc()
        raise


def transcribe_audio(audio_path, max_attempts=3):
    """Transcribe audio with retry"""
    load_whisper_model()

    for attempt in range(1, max_attempts + 1):
        try:
            print(f"[INFO] Transcription attempt {attempt}/{max_attempts}")
            segments, info = WHISPER_MODEL.transcribe(audio_path, language="vi")
            text = " ".join([segment.text.strip() for segment in segments])

            if text.strip():
                print(f"[SUCCESS] Transcribed: {text[:100]}...")
                return text
            else:
                print(f"[WARN] Empty transcription")
                if attempt < max_attempts:
                    time.sleep(1)

        except Exception as e:
            print(f"[ERROR] Attempt {attempt} failed: {e}")
            if attempt < max_attempts:
                time.sleep(1)

    print("[ERROR] All transcription attempts failed")
    return None


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        print("\n" + "=" * 60)
        return render_template("index.html", voice_samples=VOICE_SAMPLES)

    request_start = time.time()
    print("\n" + "=" * 60)
    print(f"[REQUEST] New request at {time.strftime('%H:%M:%S')}")

    try:
        mode = request.form.get("mode", "text_audio")
        gen_text = request.form.get("text", "")
        ref_text = request.form.get("ref_text", "")
        lang = request.form.get("lang", "vi")
        speed = float(request.form.get("speed", "1.0"))
        voice_sample = request.form.get("voice_sample", "male")

        print(f"[INFO] Parameters: mode={mode}, lang={lang}, speed={speed}, voice={voice_sample}")
        print(f"[INFO] Gen text: {gen_text[:100]}...")

        if not gen_text.strip():
            return jsonify({"error": "Text cannot be empty"}), 400

        # Handle audio path and ref_text
        audio_path = None
        uploaded = ("audio" in request.files and request.files["audio"].filename != "")

        if uploaded:
            # Upload audio -> transcribe
            file = request.files["audio"]
            audio_path = os.path.join(OUTPUT_DIR, f"ref_{uuid.uuid4().hex}.wav")
            file.save(audio_path)

            print(f"[INFO] Transcribing uploaded audio...")
            ref_text = transcribe_audio(audio_path)

            if ref_text is None:
                if os.path.exists(audio_path):
                    os.remove(audio_path)
                return jsonify({"error": "Failed to transcribe audio"}), 500

        else:
            # Use voice sample
            if voice_sample == "male":
                audio_path = os.path.join("static", "voices", "male.mp3")
            elif voice_sample == "female":
                audio_path = os.path.join("static", "voices", "female.mp3")

            if not os.path.exists(audio_path):
                audio_path_wav = audio_path.replace(".mp3", ".wav")
                if os.path.exists(audio_path_wav):
                    audio_path = audio_path_wav
                else:
                    return jsonify({"error": f"Voice sample not found: {voice_sample}"}), 404

            # Load ref_text
            if not ref_text.strip():
                text_ref_path = os.path.join("static", "voices", "text-ref.txt")
                if os.path.exists(text_ref_path):
                    with open(text_ref_path, "r", encoding="utf-8") as f:
                        ref_text = f.read().strip()
                else:
                    ref_text = transcribe_audio(audio_path)

        # Validate inputs
        if not audio_path or not os.path.exists(audio_path):
            return jsonify({"error": "Reference audio not found"}), 400

        if not ref_text or not ref_text.strip():
            return jsonify({"error": "Reference text is empty"}), 400

        # Generate audio
        audio_data, sample_rate = generate_audio(
            gen_text=gen_text,
            ref_audio_path=audio_path,
            ref_text=ref_text,
            speed=speed
        )

        # Save output
        output_filename = f"out_{uuid.uuid4().hex}.wav"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        sf.write(output_path, audio_data, sample_rate)

        # Cleanup
        if uploaded and audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception as e:
                print(f"[WARN] Cleanup failed: {e}")

        # Create spectrogram
        spec_filename = output_filename.replace(".wav", "_spec.png")
        spec_path = os.path.join(OUTPUT_DIR, spec_filename)
        save_spectrogram_from_audio(output_path, spec_path)

        # Calculate duration
        duration = len(audio_data) / sample_rate

        # Calculate text statistics
        text_char_count = len(gen_text)
        text_word_count = len(gen_text.split())

        # Evaluate audio quality (WER/CER)
        # eval_result = evaluate_audio_quality(output_path, gen_text, lang)

        # Save to history
        save_audio_history(
            text_input=gen_text,
            voice_sample=voice_sample,
            audio_path=f"/static/output/{output_filename}",
            spectrogram_path=f"/static/output/{spec_filename}",
            duration=duration
        )

        total_time = time.time() - request_start
        print(f"[COMPLETE] Total time: {total_time:.3f}s")
        print("=" * 60 + "\n")

        return jsonify({
            "audio_url": f"/static/output/{output_filename}",
            "spectrogram_url": f"/static/output/{spec_filename}",
            "generation_time": f"{total_time:.2f}",
            "generation_time_display": f"{total_time:.2f}s",
            "sample_rate": sample_rate,
            "duration": duration,
            "duration_display": f"{duration:.2f}s",
            # Text statistics
            "text_char_count": text_char_count,
            "text_word_count": text_word_count,
            # Quality metrics (commented out)
            # "wer": eval_result.get("wer"),
            # "cer": eval_result.get("cer"),
            # "wer_percent": eval_result.get("wer_percent", "N/A"),
            # "cer_percent": eval_result.get("cer_percent", "N/A"),
            # "transcribed_text": eval_result.get("transcribed_text", "")
        })

    except Exception as e:
        print("[EXCEPTION] Error:")
        traceback.print_exc()
        print("=" * 60 + "\n")
        return jsonify({"error": str(e)}), 500


def save_spectrogram_from_audio(audio_path, output_path):
    """Create and save spectrogram"""
    try:
        y, sr = librosa.load(audio_path, sr=None)
        S = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=100, fmax=8000)
        S_dB = librosa.power_to_db(S, ref=np.max)
        plt.figure(figsize=(10, 4))
        librosa.display.specshow(S_dB, sr=sr, x_axis='time', y_axis='mel', fmax=8000)
        plt.colorbar(format='%+2.0f dB')
        plt.title('Mel Spectrogram')
        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close()
    except Exception as e:
        print(f"[ERROR] Spectrogram failed: {e}")


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "model_loaded": F5TTS_MODEL is not None,
        "vocoder_loaded": VOCODER is not None,
        "whisper_loaded": WHISPER_MODEL is not None,
        "device": DEVICE,
        "cuda_available": torch.cuda.is_available(),
        "cuda_memory_allocated": f"{torch.cuda.memory_allocated() / 1024 ** 3:.2f} GB" if torch.cuda.is_available() else "N/A",
        "cuda_memory_reserved": f"{torch.cuda.memory_reserved() / 1024 ** 3:.2f} GB" if torch.cuda.is_available() else "N/A"
    })


@app.route("/models/status")
def models_status():
    return jsonify({
        "f5tts_loaded": F5TTS_MODEL is not None,
        "vocoder_loaded": VOCODER is not None,
        "whisper_loaded": WHISPER_MODEL is not None,
        "device": DEVICE,
        "model_name": MODEL_NAME,
        "vocab_file": VOCAB_FILE,
        "ckpt_file": CKPT_FILE
    })


@app.route("/models/unload", methods=["POST"])
def unload_models_endpoint():
    try:
        unload_models()
        return jsonify({"status": "ok", "message": "Models unloaded"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/debug/test_generation", methods=["POST"])
def debug_test_generation():
    try:
        data = request.get_json()
        gen_text = data.get("gen_text", "Test generation.")
        ref_audio = data.get("ref_audio", "static/voices/male.mp3")
        ref_text = data.get("ref_text", "")
        speed = float(data.get("speed", 1.0))

        print("\n" + "=" * 60)
        print("[DEBUG TEST]")
        print(f"  ref_audio: {ref_audio}")
        print(f"  gen_text: {gen_text[:80]}...")
        print("=" * 60)

        load_f5tts_model()

        audio_data, sample_rate = generate_audio(
            gen_text=gen_text,
            ref_audio_path=ref_audio if os.path.exists(ref_audio) else None,
            ref_text=ref_text,
            speed=speed
        )

        output_filename = f"debug_{uuid.uuid4().hex}.wav"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        sf.write(output_path, audio_data, sample_rate)

        return jsonify({
            "status": "ok",
            "audio_url": f"/static/output/{output_filename}",
            "sample_rate": sample_rate
        })

    except Exception as e:
        print(f"[ERROR] Debug failed: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/cleanup", methods=["POST"])
def cleanup_old_files():
    try:
        import glob
        cutoff_time = time.time() - 3600
        deleted_count = 0
        for pattern in ["out_*.wav", "ref_*.wav", "out_*_spec.png", "debug_*.wav"]:
            for filepath in glob.glob(os.path.join(OUTPUT_DIR, pattern)):
                if os.path.getmtime(filepath) < cutoff_time:
                    os.remove(filepath)
                    deleted_count += 1
        return jsonify({"status": "ok", "deleted_files": deleted_count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/history")
def api_get_history():
    """Get audio generation history"""
    try:
        limit = request.args.get('limit', 20, type=int)
        history = get_audio_history(limit)
        return jsonify({"status": "ok", "history": history})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/history/<int:audio_id>", methods=["DELETE"])
def api_delete_history(audio_id):
    """Delete audio from history"""
    try:
        success = delete_audio_history(audio_id)
        if success:
            return jsonify({"status": "ok", "message": f"Deleted audio {audio_id}"})
        else:
            return jsonify({"error": "Failed to delete"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("F5-TTS Flask Server")
    print("=" * 60)
    print(f"[CONFIG] Model: {MODEL_NAME}")
    print(f"[CONFIG] Vocab: {VOCAB_FILE}")
    print(f"[CONFIG] Checkpoint: {CKPT_FILE}")
    
    # Initialize database
    init_db()
    
    print("[INFO] Models will load on first request")
    print("\n[SERVER] http://0.0.0.0:5000")
    print("=" * 60 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)

