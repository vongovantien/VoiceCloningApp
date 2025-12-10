# from flask import Flask, render_template, request, send_file, jsonify
# import os
# from werkzeug.utils import secure_filename
# import torch
# import tempfile
# import uuid
#
# app = Flask(__name__)
#
# # Cấu hình
# UPLOAD_FOLDER = 'uploads'
# OUTPUT_FOLDER = 'outputs'
# ALLOWED_EXTENSIONS = {'wav', 'mp3', 'ogg', 'flac'}
#
# os.makedirs(UPLOAD_FOLDER, exist_ok=True)
# os.makedirs(OUTPUT_FOLDER, exist_ok=True)
#
# app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
# app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
#
# # Khởi tạo TTS model (XTTS-v2 hỗ trợ voice cloning)
# device = "cuda" if torch.cuda.is_available() else "cpu"
# tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
#
#
# def allowed_file(filename):
#     return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
#
#
# @app.route('/')
# def index():
#     return render_template('index.html')
#
#
# @app.route('/clone', methods=['POST'])
# def clone_voice():
#     try:
#         # Kiểm tra input
#         if 'voice_file' not in request.files:
#             return jsonify({'error': 'Không tìm thấy file giọng nói'}), 400
#
#         if 'text' not in request.form or not request.form['text'].strip():
#             return jsonify({'error': 'Vui lòng nhập văn bản'}), 400
#
#         voice_file = request.files['voice_file']
#         text = request.form['text'].strip()
#         language = request.form.get('language', 'vi')  # Mặc định tiếng Việt
#
#         if voice_file.filename == '':
#             return jsonify({'error': 'Chưa chọn file'}), 400
#
#         if not allowed_file(voice_file.filename):
#             return jsonify({'error': 'Định dạng file không hỗ trợ'}), 400
#
#         # Lưu file giọng nói tham chiếu
#         filename = secure_filename(voice_file.filename)
#         unique_id = str(uuid.uuid4())
#         voice_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{unique_id}_{filename}")
#         voice_file.save(voice_path)
#
#         # Tạo file output
#         output_filename = f"{unique_id}_output.wav"
#         output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
#
#         # Clone giọng nói và tạo audio
#         tts.tts_to_file(
#             text=text,
#             speaker_wav=voice_path,
#             language=language,
#             file_path=output_path
#         )
#
#         # Xóa file tạm
#         os.remove(voice_path)
#
#         return jsonify({
#             'success': True,
#             'output_file': output_filename,
#             'message': 'Tạo giọng nói thành công!'
#         })
#
#     except Exception as e:
#         return jsonify({'error': f'Lỗi: {str(e)}'}), 500
#
#
# @app.route('/download/<filename>')
# def download_file(filename):
#     try:
#         filepath = os.path.join(app.config['OUTPUT_FOLDER'], filename)
#         if os.path.exists(filepath):
#             return send_file(filepath, as_attachment=True)
#         return jsonify({'error': 'File không tồn tại'}), 404
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500
#
#
# @app.route('/play/<filename>')
# def play_file(filename):
#     try:
#         filepath = os.path.join(app.config['OUTPUT_FOLDER'], filename)
#         if os.path.exists(filepath):
#             return send_file(filepath, mimetype='audio/wav')
#         return jsonify({'error': 'File không tồn tại'}), 404
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500
#
#
# if __name__ == '__main__':
#     app.run(debug=True, host='0.0.0.0', port=5000)