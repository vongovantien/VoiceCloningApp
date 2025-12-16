import torch
import os

# ================= CẤU HÌNH =================
# 1. Thêm chữ r ở trước dấu ngoặc kép để sửa lỗi đường dẫn Windows
checkpoint_path = r"D:\VoiceCloningApp\ckpts\your_training_dataset\model_last.pt"

# 2. Mình đổi tên file đầu ra thành "_fixed.pt" để KHÔNG GHI ĐÈ file gốc (An toàn hơn)
output_path = r"D:\VoiceCloningApp\ckpts\your_training_dataset\model_last_fixed.pt"

# Kích thước đích bạn muốn
NEW_SIZE = 2572
# EMBED_DIM sẽ tự động lấy từ file, không cần điền tay

# ================= XỬ LÝ =================
if not os.path.exists(checkpoint_path):
    print(f"LỖI: Không tìm thấy file tại {checkpoint_path}")
    exit()

print(f"Đang load model: {checkpoint_path}...")
checkpoint = torch.load(checkpoint_path, map_location='cpu')

# Xử lý các dạng lưu model khác nhau
if 'state_dict' in checkpoint:
    state_dict = checkpoint['state_dict']
elif 'model' in checkpoint:
    state_dict = checkpoint['model']
else:
    state_dict = checkpoint

target_key = "transformer.text_embed.text_embed.weight"

if target_key in state_dict:
    old_weight = state_dict[target_key]
    old_rows, old_dim = old_weight.shape

    print(f"Kích thước hiện tại trong file: {old_weight.shape}")
    print(f"Kích thước mong muốn: torch.Size([{NEW_SIZE}, {old_dim}])")

    if old_rows == NEW_SIZE:
        print(">>> Model này đã đúng kích thước rồi, không cần sửa nữa!")
    elif old_rows > NEW_SIZE:
        print(">>> Cảnh báo: File gốc lớn hơn code hiện tại. Bạn có đang dùng nhầm file không?")
    else:
        # Tạo khung mới
        new_weight = torch.zeros(NEW_SIZE, old_dim)

        # Copy dữ liệu cũ sang
        new_weight[:old_rows, :] = old_weight

        # Gán lại vào model
        state_dict[target_key] = new_weight
        print(f"Đã resize thành công: {state_dict[target_key].shape}")

        # Cập nhật lại checkpoint
        if 'state_dict' in checkpoint:
            checkpoint['state_dict'] = state_dict
        elif 'model' in checkpoint:
            checkpoint['model'] = state_dict
        else:
            checkpoint = state_dict

        # Lưu file
        torch.save(checkpoint, output_path)
        print("-" * 30)
        print(f"THÀNH CÔNG! File mới đã lưu tại:\n{output_path}")
        print("Hãy đổi đường dẫn trong code chạy của bạn sang file '_fixed.pt' này nhé.")
else:
    print(f"LỖI: Không tìm thấy key '{target_key}' trong model.")
    print("Các key có sẵn gần giống:")
    for k in state_dict.keys():
        if "embed" in k:
            print(f" - {k}")