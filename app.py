from flask import Flask, request, jsonify, render_template
import torch
import uuid
import os
import time
import traceback
from pathlib import Path
import soundfile as sf

# Import F5-TTS inference utilities
from f5_tts.infer.utils_infer import load_model, load_vocoder, infer_process
from f5_tts.model import DiT
from f5_tts.model.utils import convert_char_to_pinyin

app = Flask(__name__, static_url_path="/static", static_folder="static")

# Configuration
OUTPUT_DIR = "static"
os.makedirs(OUTPUT_DIR, exist_ok=True)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[INIT] Using device: {DEVICE}")

# Global variables for preloaded models
F5TTS_MODEL = None
VOCODER = None
TARGET_SAMPLE_RATE = 24000
N_MEL_CHANNELS = 100
HOP_LENGTH = 256


def log_time(start_time, message):
    """Helper function to log execution time"""
    elapsed = time.time() - start_time
    print(f"[TIME] {message}: {elapsed:.3f}s")
    return time.time()


def preload_models():
    """Preload models at startup using F5-TTS utilities"""
    global F5TTS_MODEL, VOCODER

    print("[INIT] Starting model preload...")
    start_total = time.time()

    try:
        # Load F5-TTS model using built-in loader
        start = time.time()
        vocab_file = "data/Emilia_ZH_EN_pinyin/vocab.txt"
        ckpt_file = "ckpts/your_training_dataset/model_last.pt"

        F5TTS_MODEL = load_model(
            model_cls=DiT,  # Pass the class, not string
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
        log_time(start, "Loaded F5-TTS model")

        # Load vocoder
        start = time.time()
        VOCODER = load_vocoder(vocoder_name="vocos", device=DEVICE)
        log_time(start, "Loaded Vocoder")

        log_time(start_total, "Total model loading")
        print("[INIT] Models preloaded successfully!")

    except Exception as e:
        print(f"[ERROR] Failed to preload models: {e}")
        traceback.print_exc()
        raise


@torch.no_grad()
def generate_audio(gen_text, ref_audio_path=None, ref_text="", speed=1.0):
    """Generate audio using preloaded models with F5-TTS inference"""
    start_total = time.time()

    try:
        # Prepare reference audio path (infer_process expects file path, not array)
        start = time.time()
        if ref_audio_path and os.path.exists(ref_audio_path):
            print(f"[INFO] Using reference audio: {ref_audio_path}")
            log_time(start, "Reference audio validation")
        else:
            # No reference audio provided
            ref_audio_path = None
            ref_text = ""
            print("[INFO] No reference audio provided, using default")

        # Kiểm tra và xử lý ref_text trước khi truyền vào infer_process
        if not ref_text:  # Kiểm tra nếu ref_text là chuỗi rỗng hoặc None
            print("[WARNING] ref_text is empty or None.")
            ref_text = ""  # Hoặc bạn có thể gán giá trị mặc định nào đó

        print(f"[WARNING] ref_text: {ref_text}")
        print(f"[WARNING] ref_audio_path: {ref_audio_path}")

        # Use F5-TTS inference function
        start = time.time()
        audio_output, final_sample_rate, spectrogram = infer_process(
            ref_audio=ref_audio_path,  # Pass file path directly, not loaded array
            ref_text="cả hai bên hãy cố gắng hiểu cho nhau",
            gen_text=gen_text,
            model_obj=F5TTS_MODEL,
            vocoder=VOCODER,
            mel_spec_type="vocos",
            speed=speed,
            target_rms=0.1,
            cross_fade_duration=0.15,
            nfe_step=32,  # Reduce for faster inference (default: 32)
            cfg_strength=2.0,
            sway_sampling_coef=-1.0,
            device=DEVICE
        )
        log_time(start, "Audio generation (model + vocoder)")

        log_time(start_total, "Total generation")
        return audio_output, final_sample_rate

    except Exception as e:
        print(f"[ERROR] Generation failed: {e}")
        traceback.print_exc()
        raise


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template("index.html")

    request_start = time.time()
    print("\n" + "=" * 60)
    print(f"[REQUEST] New request received at {time.strftime('%H:%M:%S')}")

    try:
        # Parse request
        start = time.time()
        mode = request.form.get("mode", "text_audio")
        gen_text = request.form.get("text", "")
        ref_text = request.form.get("ref_text", "")
        lang = request.form.get("lang", "vi")
        speed = float(request.form.get("speed", "1.0"))

        print(f"[INFO] Mode: {mode}, Lang: {lang}, Speed: {speed}")
        print(f"[INFO] Gen Text ({len(gen_text)} chars): {gen_text[:100]}...")
        if ref_text:
            print(f"[INFO] Ref Text ({len(ref_text)} chars): {ref_text[:100]}...")
        log_time(start, "Request parsing")

        # Validate input
        if not gen_text.strip():
            return jsonify({"error": "Text cannot be empty"}), 400

        # Handle reference audio
        start = time.time()
        audio_path = None
        if "audio" in request.files and request.files["audio"].filename != "":
            file = request.files["audio"]
            audio_path = os.path.join(OUTPUT_DIR, f"ref_{uuid.uuid4().hex}.wav")
            file.save(audio_path)

            # Validate the saved file
            try:
                import wave
                with wave.open(audio_path, 'rb') as wf:
                    duration = wf.getnframes() / wf.getframerate()
                    print(f"[INFO] Reference audio saved: {audio_path} ({duration:.2f}s)")
            except Exception as e:
                print(f"[WARN] Could not validate audio file: {e}")
                print(f"[INFO] Reference audio saved: {audio_path}")
        log_time(start, "Audio file handling")

        # Generate audio
        start = time.time()
        audio_data, sample_rate = generate_audio(
            gen_text=gen_text,
            ref_audio_path=audio_path,
            ref_text=ref_text,
            speed=speed
        )
        log_time(start, "Audio generation")

        # Save output
        start = time.time()
        output_filename = f"out_{uuid.uuid4().hex}.wav"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        sf.write(output_path, audio_data, sample_rate)
        log_time(start, "Saving output")

        # Cleanup reference audio
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                print(f"[INFO] Cleaned up reference audio")
            except Exception as e:
                print(f"[WARN] Failed to cleanup ref audio: {e}")

        total_time = time.time() - request_start
        print(f"[COMPLETE] Total request time: {total_time:.3f}s")
        print("=" * 60 + "\n")

        return jsonify({
            "audio_url": f"/static/{output_filename}",
            "generation_time": f"{total_time:.2f}s",
            "sample_rate": sample_rate
        })

    except Exception as e:
        print("[EXCEPTION] Error occurred:")
        traceback.print_exc()
        print("=" * 60 + "\n")
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "model_loaded": F5TTS_MODEL is not None,
        "vocoder_loaded": VOCODER is not None,
        "device": DEVICE
    })


@app.route("/cleanup", methods=["POST"])
def cleanup_old_files():
    """Cleanup old generated files to save disk space"""
    try:
        import glob
        from datetime import datetime, timedelta

        # Delete files older than 1 hour
        cutoff_time = time.time() - 3600
        deleted_count = 0

        for pattern in ["out_*.wav", "ref_*.wav"]:
            for filepath in glob.glob(os.path.join(OUTPUT_DIR, pattern)):
                if os.path.getmtime(filepath) < cutoff_time:
                    os.remove(filepath)
                    deleted_count += 1

        return jsonify({
            "status": "ok",
            "deleted_files": deleted_count
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("F5-TTS Optimized Server Starting...")
    print("=" * 60)

    # Preload models before starting server
    preload_models()

    print("\n[SERVER] Starting Flask server on http://0.0.0.0:5000")
    print("[SERVER] Health check: http://0.0.0.0:5000/health")
    print("=" * 60 + "\n")

    # Use threaded=True for better performance with multiple requests
    # Set debug=False in production for better performance
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)