let mediaRecorder, audioChunks = [];
let currentPreviewSrc = null;

// Chức năng preview giọng mẫu (play, pause, stop)
window.addEventListener("DOMContentLoaded", function () {
    // Xử lý nút nghe thử - toggle play/pause
    const previewAudio = document.getElementById('previewAudio');
    document.querySelectorAll('.listen-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            const audioPath = this.getAttribute('data-audio');
            // Cùng file, nếu đang play → pause, ngược lại play/tiếp tục
            if (currentPreviewSrc === audioPath) {
                if (!previewAudio.paused) {
                    previewAudio.pause();
                } else {
                    previewAudio.play();
                }
            } else {
                currentPreviewSrc = audioPath;
                previewAudio.src = audioPath;
                previewAudio.play();
            }
        });
    });

    // Nút tắt: pause và tua về đầu
    document.querySelectorAll('.stop-listen-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            previewAudio.pause();
            previewAudio.currentTime = 0;
            currentPreviewSrc = null;
        });
    });

    // Ẩn audio preview khi tua về cuối
    previewAudio.addEventListener('ended', function () {
        previewAudio.currentTime = 0;
        currentPreviewSrc = null;
    });

    // ----------------- CÁC CHỨC NĂNG KHÁC BẠN ĐANG DÙNG -----------------

    const modeSelect = document.getElementById("modeSelect");
    const audioInput = document.getElementById("audioInput");
    const recordBtn = document.getElementById("recordBtn");

    function toggleModeUI(mode) {
        const audioGroup = document.getElementById("audioInputGroup");
        const preview = document.getElementById("audioPreview");
        if (mode === "text_audio") {
            audioGroup.style.display = "block";
        } else {
            audioGroup.style.display = "none";
            preview.style.display = "none";
        }
    }

    function setPreviewAudio(audioURL) {
        const audioPlayer = document.getElementById("uploadedAudioPlayer");
        audioPlayer.src = audioURL;
        document.getElementById("audioPreview").style.display = "block";
    }

    if (modeSelect) {
        toggleModeUI(modeSelect.value);
        modeSelect.addEventListener("change", () => toggleModeUI(modeSelect.value));
    }

    if (audioInput) {
        audioInput.addEventListener("change", (event) => {
            const file = event.target.files[0];
            if (file) {
                setPreviewAudio(URL.createObjectURL(file));
            } else {
                document.getElementById("audioPreview").style.display = "none";
            }
        });
    }

    if (recordBtn) {
        recordBtn.addEventListener("click", handleRecording);
    }

document.getElementById("synthesisForm").addEventListener("submit", function (e) {
    e.preventDefault();
    const loadingSpinner = document.getElementById("loadingSpinner");
    const audioResult = document.getElementById("audioResult");
    const noAudio = document.getElementById("noAudio");
    const audioSource = document.getElementById("audioSource");
    const downloadLink = document.getElementById("downloadLink");
    const generatedAudio = document.getElementById("generatedAudio");

    // Hiển thị loading, ẩn kết quả cũ
    loadingSpinner.style.display = "block";
    audioResult.style.display = "none";
    noAudio.style.display = "none";

    let formData = new FormData(this);

   fetch("/", { method: "POST", body: formData })
    .then(res => {
        if (!res.ok) {
            throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
    })
    .then(data => {
        loadingSpinner.style.display = "none";
        if (data.audio_url) {
            audioSource.src = data.audio_url;
            downloadLink.href = data.audio_url;
            generatedAudio.load();
            audioResult.style.display = "block";
            showToast("Audio generated successfully!", "success");
        } else {
            noAudio.innerText = "No audio generated";
            noAudio.style.display = "block";
            showToast("No audio generated");
        }
    })
    .catch(err => {
        console.error("Error:", err);
        loadingSpinner.style.display = "none";
        noAudio.innerText = "Error generating audio";
        noAudio.style.display = "block";
        showToast("Error generating audio: " + err.message);
    });
});


});

// Phần record giữ nguyên như cũ
async function handleRecording() {
    const recordBtn = document.getElementById("recordBtn");
    if (mediaRecorder && mediaRecorder.state === "recording") {
        mediaRecorder.stop();
        recordBtn.textContent = "🎤 Start Recording";
        recordBtn.classList.replace("btn-danger", "btn-outline-warning");
        return;
    }

    try {
        const stream = await navigator.mediaDevices.getUserMedia({audio: true});
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = e => audioChunks.push(e.data);

        mediaRecorder.onstop = () => {
            const audioBlob = new Blob(audioChunks, {type: "audio/wav"});
            const audioURL = URL.createObjectURL(audioBlob);
            setPreviewAudio(audioURL);

            const file = new File([audioBlob], "recorded.wav", {type: "audio/wav"});
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(file);
            document.getElementById("audioInput").files = dataTransfer.files;
        };

        mediaRecorder.start();
        recordBtn.textContent = "⏹ Stop Recording";
        recordBtn.classList.replace("btn-outline-warning", "btn-danger");
    } catch (err) {
        alert("Microphone access denied: " + err);
    }
}

function showToast(message, type = 'error') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('show');
    }, 10);

    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            document.body.removeChild(toast);
        }, 300);
    }, 3000);
}
