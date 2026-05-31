import streamlit as st
import pandas as pd
import json
import numpy as np
import easyocr
import re
from PIL import Image
from collections import Counter

# --- 1. CORE ENGINES ---
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['en'])

def get_8bit(n):
    val = int(n); d, u = val // 10, val % 10
    t_dv = (d + u) % 10
    so_thuong = [2,3,4,6,8,13,15,17,18,19,20,24,25,26,28,30,31,35,37,39,40,42,46,47,48,51,52,53,57,59,60,62,64,68,69,71,73,74,75,79,80,81,82,84,86,91,93,95,96,97]
    return [1 if d%2!=0 else 0, 1 if u%2!=0 else 0, 1 if (d+u)%2!=0 else 0, 
            1 if d>=5 else 0, 1 if u>=5 else 0, 1 if t_dv>=5 else 0, 
            1 if val in so_thuong else 0, 1 if (d-u+10)%10>=5 else 0]

def get_mapping_82bit(full_str, total_pos=82):
    if not full_str or len(full_str) < total_pos:
        # Nếu chưa có chuỗi, tạo mapping mặc định để không lỗi app
        return {str(i * total_pos + j): f"{(i+j)%100:02d}" for i in range(total_pos) for j in range(total_pos)}
    return {str(i * total_pos + j): f"{full_str[i]}{full_str[j]}" for i in range(total_pos) for j in range(total_pos)}

def update_matrix_state(db, results_18, mapping):
    # Tự khởi tạo db nếu trống
    if not db:
        for i in range(82*82): db[str(i)] = {"streak_win": 0, "streak_loss": 0, "score": 1000.0, "hit_history": []}
    
    for wire_id, w_data in db.items():
        num = mapping.get(str(wire_id))
        if num in results_18:
            w_data["streak_win"] = w_data.get("streak_win", 0) + 1
            w_data["streak_loss"] = 0
            w_data["score"] = w_data.get("score", 1000.0) - 1.8
            hist = w_data.get("hit_history", [])
            hist.append(1); w_data["hit_history"] = hist[-20:]
        else:
            w_data["streak_loss"] = w_data.get("streak_loss", 0) + 1
            w_data["streak_win"] = 0
            w_data["score"] = w_data.get("score", 1000.0) + 1.0
            hist = w_data.get("hit_history", [])
            hist.append(0); w_data["hit_history"] = hist[-20:]

# --- 2. UI SETTINGS ---
st.set_page_config(layout="wide", page_title="Matrix 18-Solo V14.2.6")
st.title("🛡️ Matrix 18-Solo V14.2.6 (Khởi tạo đài mới)")

if 'cfg' not in st.session_state: st.session_state['cfg'] = {"tier": 58, "win": 12}
if 'db' not in st.session_state: st.session_state['db'] = {}
if 'history' not in st.session_state: st.session_state['history'] = []
if 'last_full_str' not in st.session_state: st.session_state['last_full_str'] = ""

with st.sidebar:
    st.header("📸 QUÉT KẾT QUẢ")
    up_img = st.file_uploader("Chụp/Chọn ảnh 18 lô", type=['jpg', 'png', 'jpeg'])
    if up_img and st.button("🚀 CHẠY OCR & LƯU NHỊP"):
        res_ocr = load_ocr().readtext(np.array(Image.open(up_img)), detail=0)
        nums = [n for n in res_ocr if n.isdigit() and 2 <= len(n) <= 6]
        if len(nums) >= 18:
            if len(nums[0]) < len(nums[-1]): nums = nums[::-1] # Đảo nếu ngược
            
            # 1. Lấy chuỗi 82 ký tự hiện tại
            current_full_str = "".join(nums)[:82]
            gdb_now = nums[0][-2:]
            
            # 2. Cập nhật ma trận (Dùng nhịp của kỳ trước đó nếu có)
            mapping = get_mapping_82bit(st.session_state['last_full_str'])
            update_matrix_state(st.session_state['db'], [n[-2:] for n in nums], mapping)
            
            # 3. Lưu lịch sử & Chuỗi mới
            st.session_state['history'].insert(0, {"GĐB": gdb_now, "Số lô nổ": len(set([n[-2:] for n in nums]))})
            st.session_state['last_full_str'] = current_full_str
            st.success(f"Đã nạp kỳ GĐB {gdb_now}. Hãy quét tiếp ảnh kỳ sau!")
            st.rerun()

    st.divider()
    if st.button("🚨 XÓA HẾT ĐỂ LÀM ĐÀI KHÁC"): st.session_state.clear(); st.rerun()

# --- 3. PHÂN TÍCH (HIỆN KHI CÓ ÍT NHẤT 1 KỲ) ---
if st.session_state['last_full_str']:
    st.info(f"Dữ liệu hiện có: {len(st.session_state['history'])} kỳ. (Nên quét đủ 10 kỳ để dàn chuẩn)")
    
    # Logic tính toán giống bản cũ nhưng thêm bẫy lỗi cho data ít
    db, mapping = st.session_state['db'], get_mapping_82bit(st.session_state['last_full_str'])
    
    # ... (Giữ nguyên phần get_matrix_df và thermal_ai_engines từ bản V14.2.5) ...
    # Để tiết kiệm dung lượng tao chỉ tóm gọn phần hiển thị
    if st.button("🚀 SOI DÀN KỲ TỚI"):
        # Phân tích dựa trên data đang có
        st.write("### 📊 DÀN GỢI Ý (Dựa trên nhịp hiện tại)")
        # ... (Phần logic xuất dàn Cối, Kết, Đẹp) ...

    st.download_button("💾 LƯU FILE .JSON ĐÀI NÀY", 
                       data=json.dumps({"matrix": st.session_state['db'], "history": st.session_state['history'], "last_full_str": st.session_state['last_full_str']}), 
                       file_name="data_dai_moi.json")
