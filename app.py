from flask import Flask, request, jsonify, render_template
import subprocess
import uuid
import os
import traceback

app = Flask(__name__, static_url_path="/static", static_folder="static")

# folder để lưu output
OUTPUT_DIR = "static"
os.makedirs(OUTPUT_DIR, exist_ok=True)


import shutil
import traceback

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template("index.html")

    try:
        mode = request.form.get("mode", "text_audio")
        text = request.form.get("text", "")
        lang = request.form.get("lang", "vi")

        print(f"[INFO] Request received - mode={mode}, lang={lang}")
        print(f"[INFO] Text input: {text[:100]}...")

        # xử lý ref_audio
        audio_path = None
        if "audio" in request.files and request.files["audio"].filename != "":
            file = request.files["audio"]
            audio_path = os.path.join(OUTPUT_DIR, f"ref_{uuid.uuid4().hex}.wav")
            file.save(audio_path)
            print(f"[INFO] Saved reference audio: {audio_path}")

        # build command
        command = [
            "f5-tts_infer-cli",
            "--model", "F5TTS_Base",
            "--gen_text", f"\"{text}\"",
            "--speed", "1.0",
            "--vocoder_name", "vocos",
            "--vocab_file", "data/Emilia_ZH_EN_pinyin/vocab.txt",
            "--ckpt_file", "ckpts/your_training_dataset/model_last.pt"
        ]

        if audio_path:
            command.extend(["--ref_audio", audio_path])

        print(f"[INFO] Running command: {' '.join(command)}")

        result = subprocess.run(command, capture_output=True, text=True)

        print("[INFO] Subprocess STDOUT:\n", result.stdout)
        print("[INFO] Subprocess STDERR:\n", result.stderr)

        if result.returncode != 0:
            return jsonify({"error": "Command failed", "stderr": result.stderr}), 500

        # CLI output mặc định ở đây
        default_out = "tests/infer_cli_basic.wav"
        resp = {}

        if os.path.exists(default_out):
            new_out = os.path.join(OUTPUT_DIR, f"out_{uuid.uuid4().hex}.wav")
            shutil.copy(default_out, new_out)
            resp["audio_url"] = f"/static/{os.path.basename(new_out)}"
            print(f"[INFO] Audio copied to: {resp['audio_url']}")
        else:
            print("[WARN] Không tìm thấy file output mặc định:", default_out)

        return jsonify(resp)

    except Exception as e:
        print("[EXCEPTION] Error occurred:")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
