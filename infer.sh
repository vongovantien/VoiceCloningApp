f5-tts_infer-cli \
--model "F5TTS_Base" \
--ref_audio ref.wav \
--ref_text "cả hai bên hãy cố gắng hiểu cho nhau" \
--gen_text "mình muốn ra nước ngoài để tiếp xúc nhiều công ty lớn, sau đó mang những gì học được về việt nam giúp xây dựng các công trình tốt hơn" \
--speed 1.0 \
--vocoder_name vocos \
--vocab_file data/Emilia_ZH_EN_pinyin/vocab.txt \
--ckpt_file ckpts/your_training_datase
t/model_last.pt \