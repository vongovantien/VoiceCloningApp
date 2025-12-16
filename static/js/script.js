let mediaRecorder, audioChunks = [];
let currentPreviewSrc = null;
let currentHistoryAudio = null;

// ==================== HISTORY FUNCTIONS ====================

function loadHistory() {
    fetch('/api/history?limit=20')
        .then(res => res.json())
        .then(data => {
            if (data.status === 'ok' && data.history) {
                renderHistory(data.history);
            }
        })
        .catch(err => {
            console.error('Failed to load history:', err);
        });
}

function renderHistory(historyList) {
    const container = document.getElementById('historyList');
    const placeholder = document.getElementById('historyPlaceholder');

    if (!historyList || historyList.length === 0) {
        container.innerHTML = `
            <div class="text-center py-5 text-muted" id="historyPlaceholder">
                <i class="fas fa-history fa-3x mb-3 opacity-25"></i>
                <p class="mb-0">Chưa có lịch sử nào</p>
                <small>Các audio đã tạo sẽ hiển thị ở đây</small>
            </div>
        `;
        return;
    }

    let html = '';
    historyList.forEach(item => {
        const date = new Date(item.created_at);
        const timeStr = date.toLocaleString('vi-VN', {
            day: '2-digit',
            month: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });

        const duration = item.duration ? `${item.duration.toFixed(1)}s` : '';
        const textPreview = item.text_input.length > 60
            ? item.text_input.substring(0, 60) + '...'
            : item.text_input;

        html += `
            <div class="history-item" data-id="${item.audio_id}">
                <div class="history-item-header">
                    <span class="history-time">
                        <i class="fas fa-clock me-1"></i>${timeStr}
                    </span>
                    <span class="history-duration">${duration}</span>
                </div>
                <div class="history-text">${textPreview}</div>
                <div class="history-actions">
                    <button class="btn btn-sm btn-history-play" data-audio="${item.audio_path}" title="Phát">
                        <i class="fas fa-play"></i>
                    </button>
                    <button class="btn btn-sm btn-history-stop" title="Dừng">
                        <i class="fas fa-stop"></i>
                    </button>
                    <a href="${item.audio_path}" download class="btn btn-sm btn-history-download" title="Tải xuống">
                        <i class="fas fa-download"></i>
                    </a>
                    <button class="btn btn-sm btn-history-delete" data-id="${item.audio_id}" title="Xóa">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;

    // Attach event listeners
    attachHistoryEventListeners();
}

function attachHistoryEventListeners() {
    const historyAudio = document.getElementById('historyAudio');

    // Play buttons
    document.querySelectorAll('.btn-history-play').forEach(btn => {
        btn.addEventListener('click', function () {
            const audioPath = this.getAttribute('data-audio');
            if (currentHistoryAudio === audioPath && !historyAudio.paused) {
                historyAudio.pause();
            } else {
                currentHistoryAudio = audioPath;
                historyAudio.src = audioPath;
                historyAudio.play();
            }
        });
    });

    // Stop buttons
    document.querySelectorAll('.btn-history-stop').forEach(btn => {
        btn.addEventListener('click', function () {
            historyAudio.pause();
            historyAudio.currentTime = 0;
            currentHistoryAudio = null;
        });
    });

    // Delete buttons
    document.querySelectorAll('.btn-history-delete').forEach(btn => {
        btn.addEventListener('click', function () {
            const audioId = this.getAttribute('data-id');
            if (confirm('Bạn có chắc muốn xóa audio này?')) {
                deleteHistoryItem(audioId);
            }
        });
    });
}

function deleteHistoryItem(audioId) {
    fetch(`/api/history/${audioId}`, { method: 'DELETE' })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'ok') {
                showToast('Đã xóa audio', 'success');
                loadHistory(); // Reload list
            } else {
                showToast('Không thể xóa audio');
            }
        })
        .catch(err => {
            console.error('Delete error:', err);
            showToast('Lỗi khi xóa audio');
        });
}

// ==================== MAIN FUNCTIONS ====================

// Chức năng preview giọng mẫu (play, pause, stop)
window.addEventListener("DOMContentLoaded", function () {
    // Load history on page load
    loadHistory();

    // Refresh history button
    const refreshBtn = document.getElementById('refreshHistory');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', loadHistory);
    }

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

    // ----------------- CÁC CHỨC NĂNG KHÁC -----------------

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

    // Export for use in handleRecording
    window.setPreviewAudio = setPreviewAudio;

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
        const noAudioPlaceholder = document.getElementById("noAudioPlaceholder");
        const audioSource = document.getElementById("audioSource");
        const downloadLink = document.getElementById("downloadLink");
        const generatedAudio = document.getElementById("generatedAudio");

        // Hiển thị loading, ẩn kết quả cũ
        loadingSpinner.style.display = "block";
        audioResult.style.display = "none";
        if (noAudioPlaceholder) noAudioPlaceholder.style.display = "none";

        // Start progress animation
        startProgressAnimation();

        let formData = new FormData(this);

        fetch("/", { method: "POST", body: formData })
            .then(res => {
                if (!res.ok) {
                    throw new Error(`HTTP error! status: ${res.status}`);
                }
                return res.json();
            })
            .then(data => {
                // Complete progress animation
                completeProgressAnimation();

                setTimeout(() => {
                    loadingSpinner.style.display = "none";

                    if (data.audio_url) {
                        audioSource.src = data.audio_url;
                        downloadLink.href = data.audio_url;
                        generatedAudio.load();
                        audioResult.style.display = "block";
                        if (noAudioPlaceholder) noAudioPlaceholder.style.display = "none";

                        // Update stats
                        updateStats(data);

                        // Hiển thị Mel Spectrogram nếu có
                        const spectrogramContainer = document.getElementById("spectrogramContainer");
                        const spectrogramImage = document.getElementById("spectrogramImage");
                        if (data.spectrogram_url && spectrogramContainer && spectrogramImage) {
                            spectrogramImage.src = data.spectrogram_url;
                            spectrogramContainer.style.display = "block";
                        } else if (spectrogramContainer) {
                            spectrogramContainer.style.display = "none";
                        }

                        showToast("Tạo audio thành công!", "success");

                        // Reload history after successful generation
                        loadHistory();
                    } else {
                        if (noAudioPlaceholder) noAudioPlaceholder.style.display = "block";
                        showToast("Không thể tạo audio");
                    }
                }, 300);
            })
            .catch(err => {
                stopProgressAnimation();
                console.error("Error:", err);
                loadingSpinner.style.display = "none";
                if (noAudioPlaceholder) noAudioPlaceholder.style.display = "block";
                showToast("Lỗi: " + err.message);
            });
    });
});

// Phần record
async function handleRecording() {
    const recordBtn = document.getElementById("recordBtn");
    if (mediaRecorder && mediaRecorder.state === "recording") {
        mediaRecorder.stop();
        recordBtn.innerHTML = '<i class="fas fa-microphone me-2"></i>Ghi âm';
        recordBtn.classList.replace("btn-danger", "btn-outline-warning");
        return;
    }

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = e => audioChunks.push(e.data);

        mediaRecorder.onstop = () => {
            const audioBlob = new Blob(audioChunks, { type: "audio/wav" });
            const audioURL = URL.createObjectURL(audioBlob);
            window.setPreviewAudio(audioURL);

            const file = new File([audioBlob], "recorded.wav", { type: "audio/wav" });
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(file);
            document.getElementById("audioInput").files = dataTransfer.files;
        };

        mediaRecorder.start();
        recordBtn.innerHTML = '<i class="fas fa-stop me-2"></i>Dừng ghi';
        recordBtn.classList.replace("btn-outline-warning", "btn-danger");
    } catch (err) {
        alert("Không thể truy cập microphone: " + err);
    }
}

function showToast(message, type = 'error') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <i class="fas ${type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'} me-2"></i>
        ${message}
    `;
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

// ==================== PROGRESS ANIMATION ====================

let progressInterval = null;
let currentProgress = 0;
let progressStartTime = null;

// Total estimated time: ~250 seconds
// Each stage has duration in seconds
const progressStages = [
    { percent: 5, status: "Đang khởi tạo...", detail: "Initializing", duration: 5 },
    { percent: 15, status: "Đang tải model F5-TTS...", detail: "Loading AI model", duration: 30 },
    { percent: 25, status: "Đang tải Vocoder...", detail: "Loading Vocos", duration: 20 },
    { percent: 35, status: "Đang xử lý audio mẫu...", detail: "Preprocessing reference", duration: 15 },
    { percent: 55, status: "Đang sinh giọng nói...", detail: "Generating speech", duration: 80 },
    { percent: 75, status: "Đang tạo waveform...", detail: "Vocoder processing", duration: 40 },
    { percent: 85, status: "Đang lưu audio...", detail: "Saving output file", duration: 10 },
    { percent: 90, status: "Đang tạo spectrogram...", detail: "Creating visualization", duration: 15 },
    //{ percent: 95, status: "Đang đánh giá chất lượng...", detail: "Calculating WER/CER", duration: 30 },
    { percent: 95, status: "Đang hoàn tất...", detail: "Finalizing", duration: 5 }
];

function startProgressAnimation() {
    currentProgress = 0;
    progressStartTime = Date.now();

    updateProgressUI(0, progressStages[0].status, progressStages[0].detail);
    setProgressCircle(0);

    // Mỗi 2.5 giây tăng 1% => 250 giây để đạt 100%
    progressInterval = setInterval(() => {
        if (currentProgress >= 98) {
            return; // Dừng ở 98%, chờ hoàn thành thực sự
        }

        currentProgress += 1;
        setProgressCircle(currentProgress);

        // Tìm stage phù hợp với progress hiện tại
        let currentStage = progressStages[0];
        for (let i = progressStages.length - 1; i >= 0; i--) {
            if (currentProgress >= (i > 0 ? progressStages[i - 1].percent : 0)) {
                currentStage = progressStages[i];
                break;
            }
        }

        // Hiển thị thời gian đã trôi qua
        const totalElapsed = Math.floor((Date.now() - progressStartTime) / 1000);
        const minutes = Math.floor(totalElapsed / 60);
        const seconds = totalElapsed % 60;
        const timeStr = minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;

        updateProgressUI(currentProgress, currentStage.status, `${currentStage.detail} (${timeStr})`);
    }, 2500); // 2.5 giây mỗi lần = 250 giây cho 100%
}

function completeProgressAnimation() {
    if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
    }

    // Animate to 100%
    const animateTo100 = () => {
        if (currentProgress < 100) {
            currentProgress = Math.min(currentProgress + 2, 100);
            setProgressCircle(currentProgress);
            requestAnimationFrame(animateTo100);
        } else {
            const totalTime = progressStartTime ? Math.floor((Date.now() - progressStartTime) / 1000) : 0;
            const minutes = Math.floor(totalTime / 60);
            const seconds = totalTime % 60;
            const timeStr = minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
            updateProgressUI(100, "Hoàn thành!", `Tổng thời gian: ${timeStr}`);
        }
    };
    animateTo100();
}

function stopProgressAnimation() {
    if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
    }
    currentProgress = 0;
    setProgressCircle(0);
}

function setProgressCircle(percent) {
    const circle = document.getElementById('progressCircle');
    const percentText = document.getElementById('progressPercent');

    if (circle && percentText) {
        const circumference = 2 * Math.PI * 45; // r = 45
        const offset = circumference - (percent / 100) * circumference;
        circle.style.strokeDashoffset = offset;
        percentText.textContent = Math.round(percent);
    }
}

function updateProgressUI(percent, status, detail) {
    const statusEl = document.getElementById('loadingStatus');
    const detailEl = document.getElementById('loadingDetail');

    if (statusEl) {
        statusEl.innerHTML = `<i class="fas fa-cog fa-spin me-2"></i>${status}`;
    }
    if (detailEl) {
        detailEl.textContent = detail;
    }
}

// ==================== UPDATE STATS ====================

function updateStats(data) {
    // Duration
    const durationEl = document.getElementById('statDuration');
    if (durationEl && data.duration_display) {
        durationEl.textContent = data.duration_display;
    } else if (durationEl && data.duration) {
        durationEl.textContent = typeof data.duration === 'number'
            ? data.duration.toFixed(2) + 's'
            : data.duration;
    }

    // Generation time
    const genTimeEl = document.getElementById('statGenTime');
    if (genTimeEl && data.generation_time_display) {
        genTimeEl.textContent = data.generation_time_display;
    } else if (genTimeEl && data.generation_time) {
        genTimeEl.textContent = data.generation_time + 's';
    }

    // Character count
    const charsEl = document.getElementById('statChars');
    if (charsEl && data.text_char_count !== undefined) {
        charsEl.textContent = data.text_char_count.toLocaleString();
    }

    // Word count
    const wordsEl = document.getElementById('statWords');
    if (wordsEl && data.text_word_count !== undefined) {
        wordsEl.textContent = data.text_word_count.toLocaleString();
    }

    // // WER
    // const werEl = document.getElementById('statWER');
    // if (werEl) {
    //     werEl.textContent = data.wer_percent || 'N/A';
    // }

    // // CER
    // const cerEl = document.getElementById('statCER');
    // if (cerEl) {
    //     cerEl.textContent = data.cer_percent || 'N/A';
    // }
}

