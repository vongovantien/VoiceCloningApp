f5-tts_infer-cli \
--model "F5TTS_Base" \
--ref_audio ref.wav \
--ref_text "cả hai bên hãy cố gắng hiểu cho nhau" \
--gen_text "Ngày xửa ngày xưa, trong một ngôi làng nhỏ, có hai anh em sống nương tựa vào nhau từ khi cha mẹ mất sớm. Cha mẹ để lại cho họ một ít tài sản, đủ để hai anh em sống yên ổn qua ngày" \
--speed 1.0 \
--vocoder_name vocos \
--vocab_file data/Emilia_ZH_EN_pinyin/vocab.txt \
--ckpt_file ckpts/your_training_dtaset/model_last.pt \