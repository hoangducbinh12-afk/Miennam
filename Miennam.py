import streamlit as st
import pandas as pd
import json
import numpy as np
import easyocr
import re
from PIL import Image
import io
from collections import Counter
import gc # Thư viện dọn rác bộ nhớ

# --- 1. CORE ENGINES (TỐI ƯU HÓA BỘ NHỚ) ---
@st.cache_resource(max_entries=1)
def load_ocr():
    # Tắt GPU nếu chạy trên môi trường share để tránh tràn vRAM gây văng App
    return easyocr.Reader(['en'], gpu=False)

def get_8bit(n):
    val = int(n); d, u = val // 10, val % 10
    t_dv = (d + u) % 10
    so_thuong = [2,3,4,6,8,13,15,17,18,19,20,24,25,26,28,30,31,35,37,39,40,42,46,47,48,51,52,53,57,59,60,62,64,68,69,71,73,74,75,79,80,81,82,84,86,91,93,95,96,97]
    return [1 if d%2!=0 else 0, 1 if u%2!=0 else 0, 1 if (d+u)%2!=0 else 0, 
            1 if d>=5 else 0, 1 if u>=5 else 0, 1 if t_dv>=5 else 0, 
            1 if val in so_thuong else 0, 1 if (d-u+10)%10>=5 else 0]

def get_mapping_82bit(full_str, total_pos=82):
    if not full_str or len(full_str) < total_pos:
        return {str(i * total_pos + j): f"{(i+j)%100:02d}" for i in range(total_pos) for j in range(total_pos)}
    return {str(i * total_pos + j): f"{full_str[i]}{full_str[j]}" for i in range(total_pos) for j in range(total_pos)}

def calculate_tier(losses, threshold_pct):
    if not losses: return 0
    losses_sorted = sorted(losses, reverse=True)
    idx = int(len(losses_sorted) * (threshold_pct / 100)) - 1
    return losses_sorted[max(0, idx)]

def update_matrix_state(db, results_18, mapping):
    if not db:
        for i in range(82*82): db[str(i)] = {"streak_win": 0, "streak_loss": 0, "score": 1000.0, "hit_history": []}
    
    for wire_id, w_data in db.items():
        num = mapping.get(str(wire_id))
        # Giới hạn lịch sử 20 kỳ để file JSON nhẹ
        hist = w_data.get("hit_history", [])[-19:]
        
        if num in results_18:
            w_data["streak_win"] = w_data.get("streak_win", 0) + 1
            w_data["streak_loss"] = 0
            w_data["score"] = round(w_data.get("score", 1000.0) - 1.8, 2)
            hist.append(1)
        else:
            w_data["streak_loss"] = w_data.get("streak_loss", 0) + 1
            w_data["streak_win"] = 0
            w_data["score"] = round(w_data.get("score", 1000.0) + 1.0, 2)
            hist.append(0)
        w_data["hit_history"] = hist

def get_hybrid_6_touches(df_rank):
    if df_rank.empty: return ["?"]*2, ["?"]*4
    top_digits, bot_digits = [], []
    for s in df_rank.sort_values(by=["Rank", "Số"])["Số"]:
        for char in str(s):
            if char not in top_digits: top_digits.append(char)
            if len(top_digits) == 2: break
        if len(top_digits) == 2: break
    for s in df_rank.sort_values(by=["Rank", "Số"], ascending=[False, True])["Số"]:
        for char in str(s):
            if char not in bot_digits and char not in top_digits:
                bot_digits.append(char)
            if len(bot_digits) == 4: break
        if len(bot_digits) == 4: break
    return sorted(top_digits), sorted(bot_digits)

# --- 2. BỘ NÃO LỌC TẦNG SUPREME V14.2.8 ---
def thermal_ai_engines_v14(df_raw, history, db, mapping, cfg):
    if df_raw is None or df_raw.empty: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), df_raw, ([], []), set()
    t2, b4 = get_hybrid_6_touches(df_raw)
    chạm_6 = set(t2 + b4)
    base_88 = {f"{i:02d}" for i in range(100) if any(d in f"{i:02d}" for d in chạm_6) or (f"{i:02d}"[0] == f"{i:02d}"[1])}
    top_79_t1 = set(df_raw.sort_values("Rank")["Số"].head(79))
    top_79_t2 = set()
    if len(history) >= 2:
        t2_wires = sorted(db.items(), key=lambda x: x[1]['score'])[:3000]
        top_79_t2 = {f"{int(mapping.get(w_id)):02d}" for w_id, d in t2_wires if mapping.get(w_id)}

    def apply_final_logic(row):
        s = row['Số']; score = row['Điểm']
        if s in top_79_t1 and s in top_79_t2: score += 1500000
        elif s in top_79_t2: score += 1000000
        if any(d in s for d in chạm_6) or (s[0] == s[1]): score += 500000
        return score

    df_raw['Final_Score'] = df_raw.apply(apply_final_logic, axis=1)
    df_sorted = df_raw.sort_values(by=['Final_Score', 'Số'], ascending=[False, True])
    return df_sorted.head(39), df_sorted.head(59), df_sorted.head(79), df_sorted, (t2, b4), base_88

# --- 3. GIAO DIỆN CHÍNH ---
st.set_page_config(layout="wide", page_title="Matrix Supreme V14.2.8 Fix")
st.title("🛡️ Matrix Supreme V14.2.8 (Anti-Crash)")

if 'cfg' not in st.session_state: st.session_state['cfg'] = {"tier": 58, "win": 12}
if 'db' not in st.session_state: st.session_state['db'] = {}
if 'history' not in st.session_state: st.session_state['history'] = []
if 'last_full_str' not in st.session_state: st.session_state['last_full_str'] = ""
if 'prev_sets' not in st.session_state: st.session_state['prev_sets'] = {}

with st.sidebar:
    if st.button("🚨 RESET ALL", use_container_width=True): st.session_state.clear(); st.rerun()
    st.header("📂 1. DỮ LIỆU")
    up_json = st.file_uploader("Nạp JSON", type=['json'])
    if up_json and st.button("XÁC NHẬN NẠP"):
        data = json.load(up_json)
        st.session_state['db'] = data.get('matrix', data)
        st.session_state['history'] = data.get('history', [])
        st.session_state['last_full_str'] = data.get('last_full_str', "")
        st.rerun()

    st.header("📸 2. QUÉT KQ")
    up_img = st.file_uploader("Ảnh KQ", type=['jpg', 'png', 'jpeg'])
    if up_img and st.button("🚀 QUÉT & GIẢI PHÓNG RAM"):
        try:
            # Chuyển đổi ảnh sang RGB để OCR chuẩn hơn
            img_pil = Image.open(up_img).convert('RGB')
            res_ocr = load_ocr().readtext(np.array(img_pil), detail=0)
            
            # Lọc sạch ký tự, chỉ lấy số
            nums = []
            for text in res_ocr:
                clean_text = re.sub(r'\D', '', text)
                if 2 <= len(clean_text) <= 6:
                    nums.append(clean_text)
            
            if len(nums) >= 18:
                if len(nums[0]) < len(nums[-1]): nums = nums[::-1]
                st.session_state['raw_input'] = " ".join(nums)
                st.session_state['gdb_val'] = nums[0][-2:]
                
                # Giải phóng bộ nhớ ngay lập tức
                del img_pil
                gc.collect()
                st.success("RAM sạch! Quét OK.")
                st.rerun()
            else:
                st.error("Không nhận diện đủ 18 hạng giải.")
        except Exception as e:
            st.error(f"Lỗi ảnh: {e}")

    st.divider()
    if st.button("🔥 PHÂN TÍCH & LƯU", type="primary", use_container_width=True):
        raw_val, gdb_val = st.session_state.get('raw_input', ""), st.session_state.get('gdb_val', "")
        raw_list = [x.strip() for x in raw_val.split() if x]
        if len(raw_list) >= 18 and gdb_val:
            mapping = get_mapping_82bit(st.session_state['last_full_str'])
            gdb_num = f"{int(re.sub(r'\D', '', gdb_val)[-2:]):02d}"
            p = st.session_state.get('prev_sets', {})
            check = lambda d: "A" if gdb_num in (d or []) else "T"
            
            st.session_state['history'].insert(0, {
                "STT": len(st.session_state['history']) + 1, "GĐB": gdb_val,
                "Cối39": check(p.get('d39')), "Kết59": check(p.get('d59')), 
                "Safe79": check(p.get('d79')), "88-Base": "A" if gdb_num in (p.get('b88') or []) else "T"
            })
            update_matrix_state(st.session_state['db'], [n[-2:] for n in raw_list], mapping)
            st.session_state['last_full_str'] = "".join(raw_list)[:82]
            st.rerun()

    st.header("📝 3. INPUT")
    st.session_state['raw_input'] = st.text_area("Loto:", value=st.session_state.get('raw_input', ""), height=80)
    st.session_state['gdb_val'] = st.text_input("GĐB:", value=st.session_state.get('gdb_val', ""))
    st.header("⚙️ 4. BỘ LỌC")
    st.session_state['cfg']['tier'] = st.slider("Tầng Sạch (%):", 40, 80, 58)
    st.session_state['cfg']['win'] = st.slider("Kỳ xét:", 5, 20, 12)

# --- 4. HIỂN THỊ KẾT QUẢ ---
if st.session_state['last_full_str'] or st.session_state['db']:
    def get_matrix_df():
        db, mapping = st.session_state['db'], get_mapping_82bit(st.session_state['last_full_str'])
        stats = {f"{i:02d}": {"total_score": 0.0, "hits": 0, "losses": []} for i in range(100)}
        for wire_id, w_d in db.items():
            num = mapping.get(str(wire_id))
            if num:
                s = stats[num]; sw, sl = int(w_d.get("streak_win", 0)), int(w_d.get("streak_loss", 0))
                s["losses"].append(sl if sw == 0 else 0)
                s["hits"] += sum(w_d.get("hit_history", [])[-st.session_state['cfg']['win']:])
                if sw == 0: s["total_score"] += float(w_d.get("score", 1000.0))
        res = []
        for num, s in stats.items():
            dc = max(1, len([x for x in s["losses"] if x > 0]))
            hard = round((s["hits"] / (st.session_state['cfg']['win'] * (6724/100))) * 100, 2)
            score = round((s["total_score"] / dc) * (1 + hard/100), 2)
            res.append({"Số": num, "Điểm": score, "Tang": calculate_tier(s["losses"], st.session_state['cfg']['tier']), "Cứng": hard})
        df = pd.DataFrame(res).sort_values(by=["Điểm", "Số"], ascending=[False, True]).reset_index(drop=True)
        df["Rank"] = df.index + 1; return df

    df_base = get_matrix_df()
    dk, da, ds, df_f, (t2, b4), b88_set = thermal_ai_engines_v14(df_base, st.session_state['history'], st.session_state['db'], get_mapping_82bit(st.session_state['last_full_str']), st.session_state['cfg'])
    st.session_state['prev_sets'] = {'d39': dk["Số"].tolist(), 'd59': da["Số"].tolist(), 'd79': ds["Số"].tolist(), 'b88': list(b88_set)}

    st.markdown("---")
    m1, m2, m3 = st.columns(3)
    m1.metric("🔝 2 CHẠM MẠNH", ",".join(t2))
    m2.metric("📉 4 CHẠM ĐÁY", ",".join(b4))
    m3.info(f"V14.2.8 | RAM Clear")

    c1, c2, c3 = st.columns(3)
    c1.success("🎯 Cối Elite 39"); c1.code(", ".join(dk["Số"].tolist()))
    c2.info("🔥 Kết Hybrid 59"); c2.code(", ".join(da["Số"].tolist()))
    c3.warning("🛡️ Safe 79 (Overlapped)"); c3.code(", ".join(ds["Số"].tolist()))

    t_hist, t_rank = st.tabs(["📜 LỊCH SỬ", "📊 CHI TIẾT RANK"])
    with t_hist:
        if st.session_state['history']:
            st.dataframe(pd.DataFrame(st.session_state['history']), use_container_width=True, hide_index=True)
    with t_rank:
        st.dataframe(df_f.sort_values("Final_Score", ascending=False), use_container_width=True)

    st.download_button("💾 XUẤT MASTER JSON", data=json.dumps({"matrix": st.session_state['db'], "history": st.session_state['history'], "last_full_str": st.session_state['last_full_str']}, ensure_ascii=False), file_name="matrix_master.json", use_container_width=True)
