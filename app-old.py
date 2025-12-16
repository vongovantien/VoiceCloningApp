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
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
# Import F5-TTS inference utilities
from f5_tts.infer.utils_infer import load_model, load_vocoder, infer_process
from f5_tts.model import DiT
from faster_whisper import WhisperModel
from flask import Flask, request, jsonify, render_template, g

app = Flask(__name__, static_url_path="/static", static_folder="static", template_folder="templates")

# Configuration
OUTPUT_DIR = "static/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[INIT] Using device: {DEVICE}")

# Global variables for preloaded models
F5TTS_MODEL = None
VOCODER = None
TARGET_SAMPLE_RATE = 24000
N_MEL_CHANNELS = 100
HOP_LENGTH = 256

# Cấu hình đường dẫn database
DATABASE = os.path.join(app.root_path, 'app.db')


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row  # Cho phép truy cập cột bằng tên
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


# def init_db():
#     with app.app_context():
#         db = get_db()
#         with app.open_resource('schema.sql', mode='r') as f:
#             db.cursor().executescript(f.read())
#         db.commit()


# Khởi tạo database khi chạy lần đầu
if not os.path.exists(DATABASE):
    init_db()

# Voice samples
VOICE_SAMPLES = [
    {"id": "male", "name": "Male Voice", "file_path": "voices/nam-cut.wav"},
    {"id": "female", "name": "Female Voice", "file_path": "voices/nu-cut.wav"},
]


def log_time(start_time, message):
    elapsed = time.time() - start_time
    print(f"[TIME] {message}: {elapsed:.3f}s")
    return time.time()


def preload_models():
    global F5TTS_MODEL, VOCODER

    print("[INIT] Starting model preload...")
    start_total = time.time()

    try:
        vocab_file = "data/Emilia_ZH_EN_pinyin/vocab.txt"
        ckpt_file = "ckpts/your_training_dataset/model_last.pt"

        F5TTS_MODEL = load_model(
            model_cls=DiT,
            model_cfg=dict(
                dim=1024,
                depth=22,
                heads=16,
                ff_mult=2,
                text_dim=512,
                conv_layers=4
            ),
            ckpt_path=ckpt_file,
            vocab_file=vocab_file,
            device=DEVICE
        )
        F5TTS_MODEL.eval()
        log_time(start_total, "Loaded F5-TTS model")

        VOCODER = load_vocoder(vocoder_name="vocos", device=DEVICE)
        log_time(start_total, "Loaded Vocoder")

        print("[INIT] Models preloaded successfully!")

    except Exception as e:
        print(f"[ERROR] Failed to preload models: {e}")
        traceback.print_exc()
        raise


@torch.no_grad()
def generate_audio(gen_text, ref_audio_path=None, ref_text="", speed=1.0):
    start_total = time.time()

    try:
        if ref_audio_path and os.path.exists(ref_audio_path):
            print(f"[INFO] Using reference audio: {ref_audio_path}")
        else:
            ref_audio_path = None
            ref_text = ""
            print("[INFO] No reference audio provided, using default")

        print(f"[INFO] ref_audio {ref_audio_path}")
        print(f"[INFO] ref_text {ref_text}")
        print(f"[INFO] gen_text {gen_text}")

        audio_output, final_sample_rate, spectrogram = infer_process(
            ref_audio=ref_audio_path,
            ref_text=ref_text,
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
        log_time(start_total, "Audio generation (model + vocoder)")
        return audio_output, final_sample_rate

    except Exception as e:
        print(f"[ERROR] Generation failed: {e}")
        traceback.print_exc()
        raise


# Khởi tạo ASR pipeline
whisper_model = None


def init_whisper_model():
    """Khởi tạo Whisper model"""
    global whisper_model
    if whisper_model is None:
        print("[INFO] Loading Whisper model...")
        whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
        # Nếu có GPU: device="cuda", compute_type="float16"
        print("[INFO] Whisper model loaded successfully")


def transcribe_audio(audio_path, max_attempts=3):
    """Chuyển audio thành text với retry logic"""
    global whisper_model

    if whisper_model is None:
        init_whisper_model()

    for attempt in range(1, max_attempts + 1):
        try:
            print(f"[INFO] Transcription attempt {attempt}/{max_attempts}")
            segments, info = whisper_model.transcribe(audio_path, language="vi")
            text = " ".join([segment.text.strip() for segment in segments])

            if text.strip():
                print(f"[SUCCESS] Transcribed text: {text[:100]}...")
                return text
            else:
                print(f"[WARN] Empty transcription result")
                if attempt < max_attempts:
                    time.sleep(1)

        except Exception as e:
            print(f"[ERROR] Transcription attempt {attempt} failed: {e}")
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
    print(f"[REQUEST] New request received at {time.strftime('%H:%M:%S')}")

    try:
        mode = request.form.get("mode", "text_audio")
        gen_text = request.form.get("text", "")
        ref_text = request.form.get("ref_text", "")
        lang = request.form.get("lang", "vi")
        speed = float(request.form.get("speed", "1.0"))
        voice_sample = request.form.get("voice_sample", "male")

        print(f"[INFO] Mode: {mode}, Lang: {lang}, Speed: {speed}, Voice: {voice_sample}")
        print(f"[INFO] Gen Text ({len(gen_text)} chars): {gen_text[:100]}...")
        if ref_text:
            print(f"[INFO] Ref Text ({len(ref_text)} chars): {ref_text[:100]}...")

        if not gen_text.strip():
            return jsonify({"error": "Text cannot be empty"}), 400

        # Xử lý audio path và ref_text
        audio_path = None
        uploaded = ("audio" in request.files and request.files["audio"].filename != "")

        if uploaded:
            # Có upload audio -> transcribe để lấy ref_text
            file = request.files["audio"]
            audio_path = os.path.join(OUTPUT_DIR, f"ref_{uuid.uuid4().hex}.wav")
            file.save(audio_path)

            print(f"[INFO] Transcribing uploaded audio...")
            ref_text = transcribe_audio(audio_path)

            if ref_text is None:
                # Cleanup file nếu transcribe fail
                if os.path.exists(audio_path):
                    os.remove(audio_path)
                return jsonify({"error": "Failed to transcribe audio"}), 500

            print(f"[INFO] Transcribed ref_text ({len(ref_text)} chars): {ref_text[:100]}...")

        else:
            # Không upload -> dùng giọng mẫu
            if voice_sample == "male":
                audio_path = os.path.join("static", "voices", "male.mp3")
            elif voice_sample == "female":
                audio_path = os.path.join("static", "voices", "female.mp3")

            # Đọc ref_text từ file nếu chưa có
            if not ref_text.strip():
                text_ref_path = os.path.join("static", "voices", "text-ref.txt")
                if os.path.exists(text_ref_path):
                    with open(text_ref_path, "r", encoding="utf-8") as f:
                        ref_text = f.read().strip()
                    print(f"[INFO] Loaded ref_text from file: {ref_text[:100]}...")

        audio_data, sample_rate = generate_audio(
            gen_text=gen_text,
            ref_audio_path=audio_path,
            ref_text=ref_text,
            speed=speed
        )

        output_filename = f"out_{uuid.uuid4().hex}.wav"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        sf.write(output_path, audio_data, sample_rate)

        # Cleanup uploaded audio (không xóa giọng mẫu)
        if uploaded and audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception as e:
                print(f"[WARN] Failed to cleanup ref audio: {e}")

        total_time = time.time() - request_start
        print(f"[COMPLETE] Total request time: {total_time:.3f}s")
        print("=" * 60 + "\n")

        # Lưu audio
        output_filename = f"out_{uuid.uuid4().hex}.wav"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        sf.write(output_path, audio_data, sample_rate)

        # Tạo spectrogram
        spec_filename = output_filename.replace(".wav", "_spec.png")
        spec_path = os.path.join(OUTPUT_DIR, spec_filename)
        save_spectrogram_from_audio(output_path, spec_path)

        # Trả về đường dẫn audio và spectrogram
        return jsonify({
            "audio_url": f"/static/output/{output_filename}",
            "spectrogram_url": f"/static/output/{spec_filename}",
            "generation_time": f"{total_time:.2f}s",
            "sample_rate": sample_rate
        })

    except Exception as e:
        print("[EXCEPTION] Error occurred:")
        traceback.print_exc()
        print("=" * 60 + "\n")
        return jsonify({"error": str(e)}), 500


def save_spectrogram_from_audio(audio_path, output_path):
    # Đọc file audio
    y, sr = librosa.load(audio_path, sr=None)
    # Tạo spectrogram
    S = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=100, fmax=8000)
    S_dB = librosa.power_to_db(S, ref=np.max)
    # Vẽ và lưu spectrogram
    plt.figure(figsize=(10, 4))
    librosa.display.specshow(S_dB, sr=sr, x_axis='time', y_axis='mel', fmax=8000)
    plt.colorbar(format='%+2.0f dB')
    plt.title('Mel Spectrogram')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "model_loaded": F5TTS_MODEL is not None,
        "vocoder_loaded": VOCODER is not None,
        "device": DEVICE
    })


@app.route("/cleanup", methods=["POST"])
def cleanup_old_files():
    try:
        import glob
        cutoff_time = time.time() - 3600
        deleted_count = 0
        for pattern in ["out_*.wav", "ref_*.wav"]:
            for filepath in glob.glob(os.path.join(OUTPUT_DIR, pattern)):
                if os.path.getmtime(filepath) < cutoff_time:
                    os.remove(filepath)
                    deleted_count += 1
        return jsonify({"status": "ok", "deleted_files": deleted_count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("F5-TTS Optimized Server Starting...")
    print("=" * 60)
    preload_models()
    print("\n[SERVER] Starting Flask server on http://0.0.0.0:5000")
    print("[SERVER] Health check: http://0.0.0.0:5000/health")
    print("=" * 60 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
