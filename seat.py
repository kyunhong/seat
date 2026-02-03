import streamlit as st
import pandas as pd
import random
import math
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import platform
import io

# ---------------------------------------------------------
# 1. 폰트 및 기본 설정
# ---------------------------------------------------------
def set_korean_font():
    system_name = platform.system()
    if system_name == "Windows":
        plt.rc('font', family='Malgun Gothic')
    elif system_name == "Darwin":
        plt.rc('font', family='AppleGothic')
    else:
        plt.rc('font', family='NanumGothic')
    plt.rcParams['axes.unicode_minus'] = False

set_korean_font()

# ---------------------------------------------------------
# 2. 알고리즘 로직
# ---------------------------------------------------------
def find_full_id_by_name(target_name, full_student_list):
    target_name = str(target_name).strip()
    for student in full_student_list:
        try:
            _, name = student.split('.', 1)
            if name.strip() == target_name:
                return student
        except:
            continue
    for student in full_student_list:
        if target_name in student:
            return student
    return None

def is_valid_arrangement(rows, restriction_set):
    for row in rows:
        for i, student in enumerate(row):
            if not student: continue
            if i + 1 < len(row):
                neighbor = row[i+1]
                if not neighbor: continue
                pair = frozenset([student, neighbor])
                if pair in restriction_set: return False
    return True

def arrange_seats_logic(students, restriction_set, max_per_row, n_front, front_set, fixed_dict):
# 총 배치해야 할 슬롯(Slot) 개수 = 학생 수 + 비움 좌석 수
    num_blocked = list(fixed_dict.values()).count("🚫 비움")
    total_slots = len(students) + num_blocked
    
    fixed_indices = { (r * max_per_row + c): s_id for (r, c), s_id in fixed_dict.items() }
    fixed_student_ids = set(fixed_dict.values())
    
    # movable_students에는 '비움'이 포함되지 않으므로 그대로 둠
    movable_students = [s for s in students if s not in fixed_student_ids]
    
    # 탐색 범위(all_indices)를 total_slots 만큼 늘림
    all_indices = list(range(total_slots))
    
    def get_seat_score(idx):
        r = idx // max_per_row
        c = idx % max_per_row
        center = (max_per_row - 1) / 2
        return (r * 100) + abs(c - center)

    available_indices = [idx for idx in all_indices if idx not in fixed_indices]
    available_indices.sort(key=get_seat_score)
    
    movable_front_students = [s for s in movable_students if s in front_set]
    num_movable_front = len(movable_front_students)
    dynamic_prime_indices = set(available_indices[:num_movable_front])
    
    max_steps = 5000
    steps = 0

    def backtrack(current_pos, arrangement, used_movable_mask):
        nonlocal steps
        steps += 1
        if steps > max_steps: return None
        
        # 종료 조건: 현재 위치가 'total_slots'에 도달했을 때로 변경
        if current_pos == total_slots:
            rows = [arrangement[i:i+max_per_row] for i in range(0, len(arrangement), max_per_row)]
            return rows if is_valid_arrangement(rows, restriction_set) else None

        if current_pos in fixed_indices:
            arrangement.append(fixed_indices[current_pos])
            res = backtrack(current_pos + 1, arrangement, used_movable_mask)
            if res: return res
            arrangement.pop()
            return None

        is_dynamic_prime = current_pos in dynamic_prime_indices
        remaining_front_indices = [i for i, s in enumerate(movable_students) 
                                   if not used_movable_mask[i] and s in front_set]

        for i in range(len(movable_students)):
            if used_movable_mask[i]: continue
            student = movable_students[i]
            is_front = student in front_set
            
            if is_dynamic_prime and len(remaining_front_indices) > 0 and not is_front: continue
            if not is_dynamic_prime and is_front:
                future_primes = [p for p in dynamic_prime_indices if p > current_pos]
                if len(future_primes) >= len(remaining_front_indices): continue

            arrangement.append(student)
            used_movable_mask[i] = True
            
            if len(arrangement) % max_per_row == 0:
                if not is_valid_arrangement([arrangement[-max_per_row:]], restriction_set):
                    arrangement.pop()
                    used_movable_mask[i] = False
                    continue

            result = backtrack(current_pos + 1, arrangement, used_movable_mask)
            if result: return result
            
            arrangement.pop()
            used_movable_mask[i] = False
        return None

    for _ in range(20):
        random.shuffle(movable_students)
        steps = 0
        res = backtrack(0, [], [False] * len(movable_students))
        if res: return res
    return None

# ---------------------------------------------------------
# 3. Streamlit UI
# ---------------------------------------------------------
st.set_page_config(page_title="자리 배치 프로그램", page_icon="🏫", layout="wide")


if 'result_rows' not in st.session_state: st.session_state.result_rows = None
if 'fixed_seats' not in st.session_state: st.session_state.fixed_seats = {}

# --- [사이드바] 파일 업로드 ---
with st.sidebar:
    st.header("📂 명단 파일 업로드")
    student_file = st.file_uploader("1. 학생 명단 (Excel/CSV)", type=['xlsx', 'xls', 'csv'])
    front_file = st.file_uploader("2. 앞자리 희망 (선택)", type=['xlsx', 'txt'])
    restrict_file = st.file_uploader("3. 짝 제한 (선택)", type=['txt'])

    students_list = []
    front_list = []
    restrictions = set()
    
    # 1. 학생 명단 로드
    if student_file:
        try:
            if student_file.name.endswith('.csv'):
                try: df = pd.read_csv(student_file, encoding='cp949', dtype=str)
                except: df = pd.read_csv(student_file, encoding='utf-8', dtype=str)
            else: df = pd.read_excel(student_file, dtype=str)
            
            for _, row in df.iterrows():
                if len(row) >= 2 and pd.notna(row.iloc[0]):
                    num = str(row.iloc[0]).replace('.0', '').strip()
                    name = str(row.iloc[1]).strip()
                    students_list.append(f"{num}. {name}")
        except: st.error("파일 읽기 실패")

    # 2. 앞자리 명단 로드
    if front_file and students_list:
        try:
            temp = pd.read_excel(front_file).iloc[:, 0].astype(str).tolist() if front_file.name.endswith(('xlsx', 'xls')) else [l.strip() for l in front_file.getvalue().decode("utf-8").splitlines() if l.strip()]
            front_list = [fid for n in temp if (fid := find_full_id_by_name(n, students_list))]
        except: pass
        
    # 3. 제한 명단 로드
    if restrict_file and students_list:
        try:
            for l in restrict_file.getvalue().decode("utf-8").splitlines():
                if "," in l:
                    n1, n2 = l.strip().split(",")
                    id1, id2 = find_full_id_by_name(n1, students_list), find_full_id_by_name(n2, students_list)
                    if id1 and id2: restrictions.add(frozenset([id1, id2]))
        except: pass

    if students_list:
        st.markdown("---")
        st.markdown("### 📊 입력 현황")
        m1, m2 = st.columns(2)
        m1.metric("총원", f"{len(students_list)}명")
        m2.metric("앞자리", f"{len(front_list)}명")
       # st.metric("짝꿍 제한", f"{len(restrictions)}쌍")

# --- [메인] 타이틀 ---
#st.title("🏫 자리 배치 프로그램")
st.markdown("# 🏫 자리 배치 프로그램 <small style='color:grey; font-size:15px'>Developed by 박홍균</small>", unsafe_allow_html=True)

if not students_list:
    st.info("👈 왼쪽 사이드바에서 학생 명단 파일을 먼저 업로드해주세요.")
    st.stop()

# =========================================================
# [레이아웃 위치 잡기]
# 시각적으로 Expander(고정석)가 위에, Control(버튼)이 아래에 오도록 
# 빈 컨테이너를 먼저 순서대로 선언
# =========================================================
slot_expander = st.container() # 1. 위쪽 영역 (고정석 등)
#st.markdown("###")             # 여백
slot_control = st.container()  # 2. 아래쪽 영역 (실행 버튼 등)

# =========================================================
# [A. 하단 컨트롤 타워 로직]
# 변수(col_num 등) 생성을 위해 코드상으로는 먼저 실행
# 하지만 화면에는 'slot_control' 컨테이너(아래쪽)에 그려짐
# =========================================================
with slot_control:
    c_mode, c_col, c_view, c_run, c_save = st.columns([2, 1, 2, 1, 1], gap="small")

    with c_mode:
        # 1. 배치 모드
        seat_mode = st.radio("모드", ["👫 짝꿍/분단", "📝 시험대형"], horizontal=True, label_visibility="collapsed")

    with c_col:
        # 2. 분단(열) 수
        # c_col 칸 내부를 다시 [텍스트(0.5) : 입력창(1)] 비율로 쪼갬
        sub_text, sub_input = st.columns([0.5, 1])
        
        with sub_text:
            # 입력창 높이에 맞춰 텍스트를 내리기 위해 padding-top 구현
            st.markdown("<div style='padding-top: 10px; text-align: right; font-weight: bold;'>열 개수:</div>", unsafe_allow_html=True)
        
        with sub_input:
            # 라벨을 숨기고 숫자만 표시
            col_num = st.number_input("열", 1, 12, 8, label_visibility="collapsed", help="분단(열) 수")

    with c_view:
        # 3. 시점 선택
        view_type = st.radio("시점", ["학생 시점", "교사 시점"], horizontal=True, label_visibility="collapsed")

    with c_run:
        # 4. 실행 버튼
        run_clicked = st.button("🚀 배치 실행", type="primary", use_container_width=True)

    with c_save:
        # 5. 저장 버튼 (자리를 미리 잡아둠)
        save_placeholder = st.empty()

# =========================================================
# [B. 상단 고정석/명단 로직]
# 이제 col_num 변수가 있으므로, 'slot_expander' 컨테이너(위쪽)에 
# 내용을 채워 넣음
# =========================================================
with slot_expander:
    with st.expander("📌 명단 확인 및 고정석/제외석 지정 ", expanded=False):
        # 명단 확인 탭
        t_list, t_fixed = st.tabs(["📋 명단 확인", "🔒 고정석/제외석 지정"])
        
        with t_list:
            col_list_1, col_list_2 = st.columns(2)
            with col_list_1:
                st.caption("전체 명단")
                try:
                    data_preview = [{"번호": s.split('. ', 1)[0], "이름": s.split('. ', 1)[1]} if '. ' in s else {"번호": "-", "이름": s} for s in students_list]
                    st.dataframe(pd.DataFrame(data_preview), height=200, use_container_width=True, hide_index=True)
                except: st.write(students_list)
            with col_list_2:
                st.caption("앞자리 희망")
                try:
                    data_preview = [{"번호": s.split('. ', 1)[0], "이름": s.split('. ', 1)[1]} if '. ' in s else {"번호": "-", "이름": s} for s in front_list]
                    st.dataframe(pd.DataFrame(data_preview), height=200, use_container_width=True, hide_index=True)                
                except: st.write(front_list)

    with t_fixed:
            # 초기화 카운터 설정 (이게 바뀌면 모든 위젯이 강제로 새로고침됨)
            if 'reset_count' not in st.session_state: 
                st.session_state.reset_count = 0

            # 상단 안내 및 초기화 버튼
            tf_col1, tf_col2 = st.columns([4, 1])
            
            with tf_col1:
                st.info(f"현재 설정된 {col_num}열 기준으로 고정석/제외석을 배치합니다. 제외석 배치를 위해 행은 +1로 표시됩니다.")
            
            with tf_col2:
                if st.button("🔄 초기화", use_container_width=True, help="모든 설정을 지웁니다."):
                    st.session_state.fixed_seats = {}      # 데이터 비우기
                    st.session_state.reset_count += 1      # 키 변경을 위한 카운트 증가
                    st.rerun()                             # 재실행

            # 열 개수가 바뀌면 고정석 정보 리셋
            if 'last_col_num' not in st.session_state: st.session_state.last_col_num = col_num
            if st.session_state.last_col_num != col_num:
                st.session_state.fixed_seats = {}
                st.session_state.last_col_num = col_num
                st.session_state.reset_count += 1 # 열 바뀔 때도 강제 리셋

            # +2줄 여유 있게 생성
            num_needed_rows = math.ceil(len(students_list) / col_num) + 2
            new_fixed = {}
            
            for r in range(num_needed_rows):
                cols = st.columns(col_num)
                for c in range(col_num):
                    seat_idx = r * col_num + c
                    
                    # 너무 많이 그리지 않도록 제한
                    if seat_idx >= len(students_list) + 10: 
                        break

                    # 현재 저장된 값 불러오기
                    current_val = st.session_state.fixed_seats.get((r, c), "미지정")
                    
                    option_list = ["."] + ["🚫 비움"] + students_list
                    
                    # 기본 선택값 로직
                    default_index = 0
                    if current_val == "🚫 비움":
                        default_index = 1
                    elif current_val in students_list:
                        default_index = students_list.index(current_val) + 2

                    # key 뒤에 reset_count를 붙임 -> 초기화 버튼 누르면 키가 바뀜 -> 새 위젯 생성
                    unique_key = f"grid_{col_num}_{r}_{c}_{st.session_state.reset_count}"

                    sel = cols[c].selectbox(
                        "s", 
                        option_list, 
                        key=unique_key,
                        index=default_index,
                        label_visibility="collapsed"
                    )
                    
                    if sel != ".": 
                        new_fixed[(r, c)] = sel
            
            # 중복 검사
            real_students_fixed = [v for v in new_fixed.values() if v != "🚫 비움"]
            if len(real_students_fixed) != len(set(real_students_fixed)):
                st.error("⚠️ 중복된 학생이 있습니다!")
                st.session_state.fixed_valid = False
            else:
                st.session_state.fixed_seats = new_fixed
                st.session_state.fixed_valid = True

# --- [로직] 실행 및 결과 처리 ---
if run_clicked:
    if not st.session_state.get('fixed_valid', True):
        st.error("고정석 설정에 오류가 있습니다 (중복).")
    else:
        with st.spinner("..."):
            rows = arrange_seats_logic(students_list, restrictions, col_num, len(front_list), set(front_list), st.session_state.fixed_seats)
            if rows:
                st.session_state.result_rows = rows
                st.session_state.seat_mode = seat_mode
                st.session_state.col_max = col_num
            else:
                st.error("조건 만족 실패. 다시 시도해주세요.")

# --- [메인] 결과 화면 ---
if st.session_state.result_rows:
    #st.markdown("---")
    
    rows = st.session_state.result_rows
    max_cols = st.session_state.col_max
    mode = st.session_state.seat_mode # 저장된 모드 사용
    
    seat_w, seat_h, row_gap = 1.0, 0.7, 0.2
    gap_inside = 0.0 if "짝꿍" in mode else 0.2
    gap_group = 0.3 if "짝꿍" in mode else 0.2

    def get_x_pos(c_idx):
        pair_idx = c_idx // 2
        pos_in_pair = c_idx % 2
        return (pair_idx * (seat_w * 2 + gap_inside + gap_group)) + (pos_in_pair * (seat_w + gap_inside))

    num_rows = len(rows)
    total_h = num_rows * (seat_h + row_gap) + 1.2
    
    # 그래프 그리기
    # 전체 배치의 실제 '가로 폭'을 정확히 계산 (마지막 열의 시작좌표 + 책상폭)
    real_total_width = get_x_pos(max_cols - 1) + seat_w
    
    # figsize를 실제 비율(가로:세로)에 맞춰서 자동 설정 (찌그러짐 방지)
    # 가로를 10으로 고정했을 때 세로 길이 계산
    fig, ax = plt.subplots(figsize=(10, 10 * (total_h / real_total_width)))
    
    # 여백 제거 설정
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
    
    podium_y = total_h - 0.8 if "학생" in view_type else 0
    row_start_y = podium_y - 0.3 - seat_h if "학생" in view_type else 1.2
    row_dir = -1 if "학생" in view_type else 1

    # 교탁 위치: 정확한 정중앙 (0번 열과 마지막 열의 중간)
    center_x = (get_x_pos(0) + real_total_width) / 2
    podium_w = 2.0
    
    # 교탁 그리기
    ax.add_patch(plt.Rectangle(
            (center_x - (podium_w/2), podium_y), 
            podium_w, 
            0.6, 
            facecolor="#F5C0F5",  # 교탁 배경색 (분홍)
            edgecolor="black",    # 테두리 색상 (검정)
            linewidth=1.5         # 테두리 두께 (학생 책상과 동일)
        ))
    ax.text(center_x, podium_y+0.3, "교 탁", color="black", ha='center', va='center', fontweight='bold', fontsize=15)

    # 좌석 그리기 루프
    for r_idx, row_data in enumerate(rows):
        y = row_start_y + (row_dir * r_idx * (seat_h + row_gap))
        for c_idx, name in enumerate(row_data):
            # 1. 이름이 없거나, '비움'으로 설정된 경우 아예 그리지 않고 건너뜀
            if not name or name == "🚫 비움": 
                continue 
            
            # 2. 좌표 계산 (비움 자리를 건너뛰어도 좌표는 그 자리 기준으로 계산됨)
            x = get_x_pos(c_idx)
            
            # 3. 색상 설정 (일반 학생들만 처리하면 됨)
            bg = "#E3F2FD" 
            if name in front_list: bg = "#FFCDD2"
            if (r_idx, c_idx) in st.session_state.fixed_seats: bg = "#FFF176"
            
            # 4. 그리기
            ax.add_patch(plt.Rectangle((x, y), seat_w, seat_h, facecolor=bg, edgecolor='black', linewidth=1.5))
            
            disp_name = name.replace(". ", ".\n") if ". " in name else name
            ax.text(x+seat_w/2, y+seat_h/2, disp_name, ha='center', va='center', fontsize=12, fontweight='bold')

    # X축 범위를 실제 폭에 맞춰 딱 자르기 (좌우 여백 0.5씩 대칭 부여)
    ax.set_xlim(-0.5, real_total_width + 0.5)
    ax.set_ylim(-0.2, total_h + 0.2)
    ax.axis('off')
    
    st.pyplot(fig)
    
    # 상단 저장 버튼 업데이트 (결과가 나온 뒤에 채워넣음)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches='tight', pad_inches=0.1, dpi=150)
    save_placeholder.download_button("💾 저장", buf.getvalue(), "seat.png", "image/png", use_container_width=True)
    
    # 하단 텍스트 명단
    with st.expander("텍스트 명단 보기"):
        df_res = pd.DataFrame(rows)
        df_res.columns = [f"{i+1}열" for i in range(max_cols)]
        df_res.index = [f"{i+1}행" for i in range(len(rows))]
        st.dataframe(df_res, use_container_width=True)  