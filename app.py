# ============================================================
# app.py - Windows/Linux 호환 버전
# ============================================================
import os
import io
import json
import math
import base64
import random
import secrets
import logging
import platform
import pytz
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.font_manager as fm
from datetime import datetime
from flask import (
    Flask, render_template, request,
    session, send_file, make_response, jsonify
)
from flask_session import Session
# ============================================================
# 0. OS 감지 및 조건부 import
# ============================================================
IS_WINDOWS = platform.system() == 'Windows'
if not IS_WINDOWS:
    import fcntl
# ============================================================
# 1. 로거 설정
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
)
logger = logging.getLogger(__name__)
# ============================================================
# 2. Flask 앱 초기화
# ============================================================
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
if not os.environ.get('SECRET_KEY'):
    logger.warning(
        "⚠️  SECRET_KEY가 설정되지 않았습니다. "
        "운영 환경에서는 반드시 환경변수에 SECRET_KEY를 설정하세요."
    )
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"]      = "filesystem"
Session(app)
ALLOWED_STUDENT_EXTENSIONS  = {'csv', 'xlsx', 'xls'}
ALLOWED_LIST_EXTENSIONS     = {'txt', 'xlsx', 'xls'}
ALLOWED_RESTRICT_EXTENSIONS = {'txt'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
# ============================================================
# 3. 색상 기본값 및 파일 경로
# ============================================================
COLORS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'colors.json')
DEFAULT_COLORS = {
    'color_default':     '#E3F2FD',
    'color_front':       '#FFCDD2',
    'color_empty':       '#F5F5F5',
    'color_seat_border': '#000000',
    'color_grid_bg':     '#FFFFFF',
    'color_podium':      '#F5C0F5',
}
def load_colors() -> dict:
    """저장된 색상 불러오기 (없으면 기본값)"""
    try:
        if os.path.exists(COLORS_FILE):
            with open(COLORS_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            return {**DEFAULT_COLORS, **saved}
    except Exception as e:
        logger.error(f"색상 파일 로드 실패: {e}")
    return dict(DEFAULT_COLORS)
def save_colors_to_file(colors: dict) -> bool:
    """색상을 파일에 저장"""
    try:
        allowed  = set(DEFAULT_COLORS.keys())
        filtered = {k: v for k, v in colors.items() if k in allowed}
        with open(COLORS_FILE, 'w', encoding='utf-8') as f:
            json.dump(filtered, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"색상 파일 저장 실패: {e}")
        return False
# ============================================================
# 4. 파일 검증 유틸리티
# ============================================================
def allowed_file(filename: str, allowed_ext: set) -> bool:
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in allowed_ext
def validate_upload(file_obj, allowed_ext: set) -> tuple:
    if not file_obj or not file_obj.filename:
        return False, "파일이 선택되지 않았습니다."
    if not allowed_file(file_obj.filename, allowed_ext):
        return False, (
            f"허용되지 않는 파일 형식입니다. "
            f"허용 형식: {', '.join(allowed_ext)}"
        )
    file_obj.seek(0, 2)
    file_size = file_obj.tell()
    file_obj.seek(0)
    if file_size > MAX_FILE_SIZE:
        size_mb = file_size / (1024 * 1024)
        return False, (
            f"파일 크기({size_mb:.1f}MB)가 너무 큽니다. "
            f"최대 {MAX_FILE_SIZE // (1024 * 1024)}MB까지 허용됩니다."
        )
    if file_size == 0:
        return False, "빈 파일은 업로드할 수 없습니다."
    return True, "OK"
# ============================================================
# 5. 폰트 설정
# ============================================================
def set_korean_font():
    BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
    font_path = os.path.join(BASE_DIR, "NanumGothic.ttf")
    if os.path.exists(font_path):
        fm.fontManager.addfont(font_path)
        plt.rc('font', family='NanumGothic')
    else:
        fallback = 'Malgun Gothic' if IS_WINDOWS else 'NanumGothic'
        plt.rc('font', family=fallback)
    plt.rcParams['axes.unicode_minus'] = False
set_korean_font()
# ============================================================
# 6. 방문자 카운터
# ============================================================
def get_and_update_counts(is_new_visitor: bool) -> tuple:
    data_file = 'visitors.json'
    today_str = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d')
    data      = {}
    try:
        if IS_WINDOWS:
            try:
                with open(data_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    data = json.loads(content) if content else {}
            except (FileNotFoundError, json.JSONDecodeError):
                data = {}
            if data.get('date') != today_str:
                data = {
                    'date':        today_str,
                    'today_count': 0,
                    'total_count': data.get('total_count', 0)
                }
            if is_new_visitor:
                data['today_count'] += 1
                data['total_count'] += 1
                with open(data_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False)
        else:
            with open(data_file, 'a+', encoding='utf-8') as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    f.seek(0)
                    content = f.read().strip()
                    data = json.loads(content) if content else {}
                except json.JSONDecodeError:
                    logger.warning("visitors.json 파싱 실패 - 초기화합니다.")
                    data = {}
                if data.get('date') != today_str:
                    data = {
                        'date':        today_str,
                        'today_count': 0,
                        'total_count': data.get('total_count', 0)
                    }
                if is_new_visitor:
                    data['today_count'] += 1
                    data['total_count'] += 1
                    f.seek(0)
                    f.truncate()
                    json.dump(data, f, ensure_ascii=False)
                fcntl.flock(f, fcntl.LOCK_UN)
    except OSError as e:
        logger.error(f"방문자 파일 처리 오류: {e}")
        return 0, 0
    return data.get('today_count', 0), data.get('total_count', 0)
# ============================================================
# 7. 이름 검색 유틸리티
# ============================================================
def find_full_id_by_name(target_name: str, full_student_list: list):
    target_name = str(target_name).strip()
    for student in full_student_list:
        try:
            _, name = student.split('.', 1)
            if name.strip() == target_name:
                return student
        except ValueError:
            continue
        except Exception as e:
            logger.warning(f"find_full_id_by_name 예상치 못한 오류: {e}")
            continue
    for student in full_student_list:
        if target_name in student:
            return student
    return None
# ============================================================
# 8. 파일 파싱
# ============================================================
def parse_files(f_student, f_front, f_restrict, current_students=None):
    students_list             = current_students if current_students else []
    front_list                = []
    restrict_list_for_session = []
    if f_student:
        ok, msg = validate_upload(f_student, ALLOWED_STUDENT_EXTENSIONS)
        if not ok:
            logger.warning(f"학생 파일 검증 실패: {msg}")
        else:
            students_list = []
            try:
                if f_student.filename.endswith('.csv'):
                    try:
                        df = pd.read_csv(
                            f_student, encoding='cp949', dtype=str, header=None
                        )
                    except UnicodeDecodeError:
                        f_student.seek(0)
                        df = pd.read_csv(
                            f_student, encoding='utf-8', dtype=str, header=None
                        )
                else:
                    df = pd.read_excel(f_student, dtype=str, header=None)
                for _, row in df.iterrows():
                    items = [
                        str(x).strip()
                        for x in row
                        if pd.notna(x) and str(x).strip() != ''
                    ]
                    if len(items) >= 2:
                        num  = items[0].replace('.0', '')
                        name = items[1]
                        if num.isdigit():
                            students_list.append(f"{num}. {name}")
            except Exception as e:
                logger.error(f"학생 명단 읽기 오류: {e}")
    if f_front and students_list:
        ok, msg = validate_upload(f_front, ALLOWED_LIST_EXTENSIONS)
        if not ok:
            logger.warning(f"앞자리 파일 검증 실패: {msg}")
        else:
            try:
                if f_front.filename.endswith(('.xlsx', '.xls')):
                    temp = (
                        pd.read_excel(f_front, header=None)
                        .iloc[:, 0]
                        .astype(str)
                        .tolist()
                    )
                else:
                    raw_data = f_front.read()
                    try:
                        content = raw_data.decode("utf-8")
                    except UnicodeDecodeError:
                        content = raw_data.decode("cp949")
                    temp = [l.strip() for l in content.splitlines() if l.strip()]
                front_list = [
                    fid for n in temp
                    if (fid := find_full_id_by_name(n, students_list))
                ]
                front_list.sort(
                    key=lambda x: int(x.split('.')[0])
                    if '.' in x and x.split('.')[0].isdigit()
                    else 99999
                )
            except Exception as e:
                logger.error(f"앞자리 파일 오류: {e}")
    if f_restrict and students_list:
        ok, msg = validate_upload(f_restrict, ALLOWED_RESTRICT_EXTENSIONS)
        if not ok:
            logger.warning(f"제한 파일 검증 실패: {msg}")
        else:
            try:
                raw_data = f_restrict.read()
                try:
                    content = raw_data.decode("utf-8").splitlines()
                except UnicodeDecodeError:
                    content = raw_data.decode("cp949").splitlines()
                for line in content:
                    if "," in line:
                        parts = line.strip().split(",", 1)
                        if len(parts) == 2:
                            id1 = find_full_id_by_name(parts[0], students_list)
                            id2 = find_full_id_by_name(parts[1], students_list)
                            if id1 and id2:
                                restrict_list_for_session.append([id1, id2])
            except Exception as e:
                logger.error(f"제한 파일 오류: {e}")
    return students_list, front_list, restrict_list_for_session
# ============================================================
# 9. 배치 알고리즘 - 랜덤 (기존 그대로)
# ============================================================
def is_valid_arrangement(rows: list, restriction_set: set) -> bool:
    for row in rows:
        for i, student in enumerate(row):
            if not student:
                continue
            if i + 1 < len(row):
                neighbor = row[i + 1]
                if not neighbor:
                    continue
                if frozenset([student, neighbor]) in restriction_set:
                    return False
    return True
def arrange_seats_logic(
    students: list,
    restriction_set: set,
    max_per_row: int,
    front_set: set,
    fixed_dict: dict
):
    """백트래킹 기반 랜덤 자리 배치 (개선버전)"""
    # ── 기본 수치 계산 ──────────────────────────────────────
    num_blocked  = list(fixed_dict.values()).count("🚫 비움")
    total_slots  = len(students) + num_blocked
    fixed_indices = {
        int(r) * max_per_row + int(c): s_id
        for (r, c), s_id in fixed_dict.items()
    }
    fixed_student_ids = set(fixed_dict.values())
    movable_students  = [s for s in students if s not in fixed_student_ids]
    # ── 슬롯 점수: 앞/중앙일수록 낮음 ──────────────────────
    def get_seat_score(idx: int) -> float:
        r      = idx // max_per_row
        c      = idx % max_per_row
        center = (max_per_row - 1) / 2
        return (r * 100) + abs(c - center)
    all_indices       = list(range(total_slots))
    available_indices = [idx for idx in all_indices if idx not in fixed_indices]
    available_indices.sort(key=get_seat_score)
    # ── 빈자리 슬롯을 prime에서 제외 ────────────────────────
    movable_front_students = [s for s in movable_students if s in front_set]
    num_movable_front      = len(movable_front_students)
    blocked_slot_indices = {
        idx for idx, val in fixed_indices.items()
        if val == "🚫 비움"
    }
    available_prime_candidates = [
        idx for idx in available_indices
        if idx not in blocked_slot_indices
    ]
    dynamic_prime_indices = set(
        available_prime_candidates[:num_movable_front]
    )
    # ── 조건 수에 따라 한계값 동적 조정 ─────────────────────
    n       = len(movable_students)
    penalty = len(restriction_set) + len(front_set) + num_blocked
    max_steps   = max(10000, n * 150 + penalty * 500)
    max_retries = max(30,    min(100, n // 3 + penalty * 3))
    steps       = 0
    # ── 사전 검증: 고정석 간 짝 제한 충돌 체크 ─────────────
    def check_fixed_conflicts() -> bool:
        fixed_positions = sorted(fixed_indices.keys())
        for pos in fixed_positions:
            student = fixed_indices[pos]
            if student == "🚫 비움":
                continue
            right_pos = pos + 1
            if (
                right_pos in fixed_indices
                and pos % max_per_row != max_per_row - 1
            ):
                right_student = fixed_indices[right_pos]
                if right_student == "🚫 비움":
                    continue
                if frozenset([student, right_student]) in restriction_set:
                    logger.warning(
                        f"⚠️ 해결 불가 충돌: 고정석 [{pos}]{student} ↔ "
                        f"[{right_pos}]{right_student} 짝 제한 위반"
                    )
                    return False
        return True
    if not check_fixed_conflicts():
        logger.warning("고정석 간 짝 제한 충돌로 배치 불가능")
        return None
    logger.info(
        f"배치 시작: 학생={n}, 제한={len(restriction_set)}쌍, "
        f"앞자리={len(front_set)}명, 빈자리={num_blocked}개 | "
        f"max_steps={max_steps}, max_retries={max_retries}"
    )
    # ── 백트래킹 ─────────────────────────────────────────────
    def backtrack(current_pos, arrangement, used_movable_mask):
        nonlocal steps
        steps += 1
        if steps > max_steps:
            return None
        if current_pos == total_slots:
            rows = [
                arrangement[i:i + max_per_row]
                for i in range(0, len(arrangement), max_per_row)
            ]
            return rows
        if current_pos in fixed_indices:
            fixed_student = fixed_indices[current_pos]
            if fixed_student != "🚫 비움":
                if (
                    current_pos % max_per_row != 0
                    and arrangement
                ):
                    prev_student = arrangement[-1]
                    if (
                        prev_student
                        and prev_student != "🚫 비움"
                        and frozenset([fixed_student, prev_student]) in restriction_set
                    ):
                        return None
            arrangement.append(fixed_student)
            res = backtrack(current_pos + 1, arrangement, used_movable_mask)
            if res:
                return res
            arrangement.pop()
            return None
        is_dynamic_prime = current_pos in dynamic_prime_indices
        remaining_front_indices = [
            i for i, s in enumerate(movable_students)
            if not used_movable_mask[i] and s in front_set
        ]
        for i in range(len(movable_students)):
            if used_movable_mask[i]:
                continue
            student  = movable_students[i]
            is_front = student in front_set
            if is_dynamic_prime and remaining_front_indices and not is_front:
                continue
            if not is_dynamic_prime and is_front:
                future_primes = [p for p in dynamic_prime_indices if p > current_pos]
                if len(future_primes) >= len(remaining_front_indices):
                    continue
            if (
                current_pos % max_per_row != 0
                and arrangement
            ):
                prev_student = arrangement[-1]
                if (
                    prev_student
                    and prev_student != "🚫 비움"
                    and frozenset([student, prev_student]) in restriction_set
                ):
                    continue
            arrangement.append(student)
            used_movable_mask[i] = True
            result = backtrack(current_pos + 1, arrangement, used_movable_mask)
            if result:
                return result
            arrangement.pop()
            used_movable_mask[i] = False
        return None
    # ── 재시도 루프 ──────────────────────────────────────────
    for attempt in range(max_retries):
        random.shuffle(movable_students)
        steps = 0
        res   = backtrack(0, [], [False] * len(movable_students))
        if res:
            logger.info(
                f"배치 성공: 시도 {attempt + 1}회 / {max_retries}회, "
                f"{steps}스텝"
            )
            return res
    logger.warning(
        f"배치 실패: {max_retries}회 모두 실패 "
        f"(마지막 시도 {steps}스텝)"
    )
    return None
# ============================================================
# 9-2. 배치 알고리즘 - 번호순 (신규 추가)
# ============================================================
# 방향 코드 정의
# A: 왼→오, 앞→뒤  (기본 가로순)
# B: 세로(열)순,   왼→오  (왼쪽 열부터 위→아래)
# C: 오→왼, 앞→뒤  (교사 시점 오른쪽에서 1,2 시작)
# D: 왼→오, 뒤→앞  (뒤에서 1,2 시작)
# E: 오→왼, 뒤→앞  (교사 시점 + 뒤에서 시작)
# F: 세로(열)순,   오→왼  (오른쪽 열부터 위→아래, 교사 기준)
ORDER_DIRECTION_LABELS = {
    'A': '➡️ 왼→오, 앞→뒤  (1행 1열부터)',
    'B': '⬇️ 세로순, 왼→오  (1열 위→아래)',
    'C': '⬅️ 오→왼, 앞→뒤  (교사 기준 오른쪽에서 시작)',
    'D': '➡️ 왼→오, 뒤→앞  (마지막 행부터)',
    'E': '⬅️ 오→왼, 뒤→앞  (교사 기준 뒤 오른쪽에서 시작)',
    'F': '⬇️ 세로순, 오→왼  (오른쪽 열부터 위→아래)',
}
def get_slot_order(direction: str, num_rows: int, max_per_row: int) -> list:
    """방향별 슬롯 인덱스 순서 반환"""
    slots = []
    if direction == 'A':
        for r in range(num_rows):
            for c in range(max_per_row):
                slots.append(r * max_per_row + c)
    elif direction == 'B':
        for c in range(max_per_row):
            for r in range(num_rows):
                slots.append(r * max_per_row + c)
    elif direction == 'C':
        for r in range(num_rows):
            for c in reversed(range(max_per_row)):
                slots.append(r * max_per_row + c)
    elif direction == 'D':
        for r in reversed(range(num_rows)):
            for c in range(max_per_row):
                slots.append(r * max_per_row + c)
    elif direction == 'E':
        for r in reversed(range(num_rows)):
            for c in reversed(range(max_per_row)):
                slots.append(r * max_per_row + c)
    elif direction == 'F':
        for c in reversed(range(max_per_row)):
            for r in range(num_rows):
                slots.append(r * max_per_row + c)
    return slots
def arrange_by_order(
    students: list,
    max_per_row: int,
    direction: str,
    fixed_dict: dict
) -> list:
    """번호순 자리 배치 - 고정석/제외석 반영"""
    fixed_student_ids = set(fixed_dict.values()) - {"🚫 비움"}
    movable_students = sorted(
        [s for s in students if s not in fixed_student_ids],
        key=lambda x: int(x.split('.')[0])
        if '.' in x and x.split('.')[0].isdigit() else 9999
    )
    num_blocked = list(fixed_dict.values()).count("🚫 비움")
    total_slots = len(students) + num_blocked
    num_rows    = math.ceil(total_slots / max_per_row)
    fixed_indices = {
        int(r) * max_per_row + int(c): s_id
        for (r, c), s_id in fixed_dict.items()
    }
    arrangement = [''] * total_slots
    for idx, val in fixed_indices.items():
        if idx < total_slots:
            arrangement[idx] = val
    slot_order = get_slot_order(direction, num_rows, max_per_row)
    student_idx = 0
    for slot_idx in slot_order:
        if slot_idx >= total_slots:
            continue
        if arrangement[slot_idx] != '':
            continue
        if student_idx < len(movable_students):
            arrangement[slot_idx] = movable_students[student_idx]
            student_idx += 1
    rows = [
        arrangement[i:i + max_per_row]
        for i in range(0, total_slots, max_per_row)
    ]
    logger.info(
        f"번호순 배치 완료: 방향={direction}, "
        f"학생={len(movable_students)}명, 행={num_rows}"
    )
    return rows
# ============================================================
# 10. 이미지 생성
# ============================================================
def draw_seat_chart(
    rows: list,
    col_num: int,
    view_type: str,
    seat_mode: str,
    front_list: list,
    fixed_dict: dict,
    all_students: list = None,
    with_list: bool = False,
    title_text: str = "",
    colors: dict = None
) -> io.BytesIO:
    """자리 배치도 이미지 생성"""
    if colors is None:
        colors = load_colors()
    c_default = colors.get('color_default',     DEFAULT_COLORS['color_default'])
    c_front   = colors.get('color_front',       DEFAULT_COLORS['color_front'])
    c_border  = colors.get('color_seat_border', DEFAULT_COLORS['color_seat_border'])
    c_grid_bg = colors.get('color_grid_bg',     DEFAULT_COLORS['color_grid_bg'])
    c_podium  = colors.get('color_podium',      DEFAULT_COLORS['color_podium'])
    A4_WIDTH  = 12
    A4_HEIGHT = 8.27
    FONT_SIZE_NAME = 15
    seat_w, seat_h = 1.0, 0.4
    row_gap        = 0.12
    gap_inside     = 0.0  if seat_mode == 'pair' else 0.12
    gap_group      = 0.25 if seat_mode == 'pair' else 0.12
    def get_base_x(c_idx: int) -> float:
        if seat_mode == 'single':
            return c_idx * (seat_w + gap_inside)
        else:
            pair_idx    = c_idx // 2
            pos_in_pair = c_idx % 2
            return (
                pair_idx * (seat_w * 2 + gap_inside + gap_group)
                + pos_in_pair * (seat_w + gap_inside)
            )
    num_rows   = len(rows)
    total_w    = get_base_x(col_num - 1) + seat_w
    total_h    = num_rows * (seat_h + row_gap) + 1.0
    top_margin = 0.92 if title_text else 0.98
    if with_list and all_students:
        fig, (ax_seat, ax_list) = plt.subplots(
            1, 2,
            figsize=(A4_WIDTH, A4_HEIGHT),
            gridspec_kw={'width_ratios': [3.8, 1], 'wspace': 0}
        )
        plt.subplots_adjust(left=0.01, right=0.99, top=top_margin, bottom=0.05)
    else:
        fig, ax_seat = plt.subplots(figsize=(A4_WIDTH, A4_HEIGHT))
        ax_list = None
        plt.subplots_adjust(left=0.01, right=0.99, top=top_margin, bottom=0.01)
    ax = ax_seat
    fig.patch.set_facecolor(c_grid_bg)
    ax.set_facecolor(c_grid_bg)
    if title_text:
        title_x = total_w * 0.65 if with_list else total_w / 2
        ax.text(
            title_x, total_h + 0.2, title_text,
            ha='center', va='bottom',
            fontsize=37, fontweight='bold'
        )
        current_ylim_top = total_h + 0.5
    else:
        current_ylim_top = total_h
    if view_type == 'student':
        podium_y    = total_h - 0.5
        first_row_y = podium_y - 0.5 - seat_h
        y_direction = -1
        def transform(x, y):
            return x, y
    else:
        podium_y    = 0.5
        first_row_y = podium_y + 0.5
        y_direction = 1
        def transform(x, y):
            return total_w - x - seat_w, y
    # 교탁
    center_x = total_w / 2
    ax.add_patch(patches.Rectangle(
        (center_x - 1.1, podium_y - 0.2), 2.2, 0.4,
        facecolor=c_podium, edgecolor="black", linewidth=1.5
    ))
    ax.text(
        center_x, podium_y, "교  탁",
        ha='center', va='center', fontweight='bold', fontsize=16
    )
    # 좌석 그리기
    front_set_draw = set(front_list)
    for r_idx, row_data in enumerate(rows):
        base_y = first_row_y + (r_idx * y_direction * (seat_h + row_gap))
        for c_idx, name in enumerate(row_data):
            if not name or name == "🚫 비움":
                continue
            base_x           = get_base_x(c_idx)
            final_x, final_y = transform(base_x, base_y)
            if name in front_set_draw:
                bg = c_front
            else:
                bg = c_default
            ax.add_patch(patches.Rectangle(
                (final_x, final_y), seat_w, seat_h,
                facecolor=bg, edgecolor=c_border, linewidth=1.2
            ))
            if '.' in name:
                num, sname = name.split('.', 1)
                disp_name  = f"{num}.\n{sname.strip()}"
            else:
                disp_name = name
            ax.text(
                final_x + seat_w / 2, final_y + seat_h / 2,
                disp_name,
                ha='center', va='center',
                fontsize=FONT_SIZE_NAME, fontweight='bold',
                linespacing=1.1
            )
    ax.set_xlim(-0.2, total_w + 0.2)
    ax.set_ylim(0, current_ylim_top)
    ax.axis('off')
    # 명단 표
    if with_list and ax_list and all_students:
        ax_list.set_facecolor(c_grid_bg)
        ax_list.axis('off')
        try:
            sorted_students = sorted(
                all_students,
                key=lambda x: int(x.split('.')[0])
                if '.' in x and x.split('.')[0].isdigit()
                else 9999
            )
        except Exception:
            sorted_students = sorted(all_students)
        count = len(sorted_students)
        mid   = math.ceil(count / 2)
        table_data = []
        for i in range(mid):
            row = [sorted_students[i]]
            row.append(sorted_students[i + mid] if i + mid < count else "")
            table_data.append(row)
        table = ax_list.table(
            cellText=table_data,
            loc='center', cellLoc='center',
            colWidths=[0.38, 0.38]
        )
        table.auto_set_font_size(False)
        table.set_fontsize(11)
        table.scale(1, 2.3)
        for (row, col), cell in table.get_celld().items():
            cell.set_edgecolor('#444444')
            cell.set_linewidth(1)
            if row % 2 == 0:
                cell.set_facecolor('#F9F9F9')
    img = io.BytesIO()
    fig.savefig(img, format='png', pad_inches=0.2, dpi=120,
                facecolor=fig.get_facecolor())
    img.seek(0)
    plt.close(fig)
    return img
# ============================================================
# 11. index() 헬퍼 함수들
# ============================================================
def load_session_data() -> dict:
    return {
        'students_list': session.get('students_list', []),
        'front_list':    session.get('front_list',    []),
        'restrict_list': session.get('restrict_list', []),
        'final_rows':    session.get('last_rows',     []) or [],
    }
def handle_clear_action(action: str) -> None:
    if action == 'clear_student':
        session.update({
            'students_list': [],
            'last_rows':     [],
            'front_list':    [],
            'restrict_list': [],
        })
        logger.info("학생 명단 전체 초기화")
    elif action == 'clear_front':
        session['front_list'] = []
        logger.info("앞자리 명단 초기화")
    elif action == 'clear_restrict':
        session['restrict_list'] = []
        logger.info("짝 제한 명단 초기화")
def parse_fixed_seats(fixed_seats_state: dict, col_num: int) -> dict:
    fixed_dict = {}
    for key, val in fixed_seats_state.items():
        if val in ('.', '', None):
            continue
        parts = key.split('_')
        if len(parts) == 3:
            try:
                r, c = int(parts[1]), int(parts[2])
                if c < col_num:
                    fixed_dict[(r, c)] = val
            except ValueError:
                logger.warning(f"고정석 키 파싱 실패: {key}")
    return fixed_dict
def generate_image_b64(
    final_rows, col_num, view_type, seat_mode,
    front_list, fixed_dict, students_list, title_text,
    colors: dict = None
):
    try:
        img_io = draw_seat_chart(
            final_rows, col_num, view_type, seat_mode,
            front_list, fixed_dict,
            all_students=students_list,
            with_list=False,
            title_text=title_text,
            colors=colors
        )
        b64 = base64.b64encode(img_io.getvalue()).decode()
        return f"data:image/png;base64,{b64}"
    except Exception as e:
        logger.error(f"이미지 생성 오류: {e}")
        return None
def prepare_template_data(
    students_list, front_list, restrict_list,
    final_rows, col_num, fixed_seats_state,
    image_url, error_msg, view_type, seat_mode,
    today_cnt, total_cnt, today_str_short,
    arrange_type='random', order_dir='A'     # ← 신규 추가
) -> dict:
    safe_student_table = []
    for s in students_list:
        if '.' in s:
            parts = s.split('.', 1)
            safe_student_table.append({
                'num':  parts[0].strip(),
                'name': parts[1].strip()
            })
        else:
            safe_student_table.append({'num': '-', 'name': s.strip()})
    base_rows = math.ceil(len(students_list) / col_num) if students_list else 0
    max_fixed_row = 0
    for key, val in fixed_seats_state.items():
        if val not in ('.', ''):
            try:
                max_fixed_row = max(max_fixed_row, int(key.split('_')[1]))
            except (ValueError, IndexError):
                pass
    grid_rows = max(base_rows, max_fixed_row + 1)
    if grid_rows == 0 and students_list:
        grid_rows = 1
    if final_rows:
        grid_rows = len(final_rows)
    file_colors   = load_colors()
    saved_colors  = session.get('custom_colors', {})
    custom_colors = {**file_colors, **saved_colors}
    return dict(
        students              = students_list,
        student_table         = safe_student_table,
        front_list            = front_list,
        restrict_list         = restrict_list,
        col_num               = col_num,
        grid_rows             = grid_rows,
        image_url             = image_url,
        error                 = error_msg,
        view_type             = view_type,
        seat_mode             = seat_mode,
        fixed_seats_state     = fixed_seats_state,
        has_students          = len(students_list) > 0,
        has_front             = len(front_list) > 0,
        has_restrict          = len(restrict_list) > 0,
        today_cnt             = today_cnt,
        total_cnt             = total_cnt,
        save_date             = today_str_short,
        seat_data             = final_rows if final_rows else [],
        custom_colors         = custom_colors,
        arrange_type          = arrange_type,                   # ← 신규
        order_dir             = order_dir,                      # ← 신규
        order_direction_labels= ORDER_DIRECTION_LABELS,         # ← 신규
    )
# ============================================================
# 12. 메인 라우트
# ============================================================
@app.route('/', methods=['GET', 'POST'])
def index():
    logger.info("index() 호출")
    data          = load_session_data()
    students_list = data['students_list']
    front_list    = data['front_list']
    restrict_list = data['restrict_list']
    final_rows    = data['final_rows']
    try:
        col_num = int(request.form.get('col_num', 8))
        col_num = max(1, min(col_num, 20))
    except (ValueError, TypeError):
        col_num = 8
    view_type    = request.form.get('view_type',    'student')
    seat_mode    = request.form.get('seat_mode',    'pair')
    action       = request.form.get('action',       '')
    arrange_type = request.form.get('arrange_type', 'random')   # ← 신규
    order_dir    = request.form.get('order_dir',    'A')        # ← 신규
    logger.info(
        f"action: '{action}', "
        f"arrange_type: '{arrange_type}', "
        f"order_dir: '{order_dir}'"
    )
    grade       = request.form.get('grade', '')
    grade_class = request.form.get('grade_class', '')
    title_text  = (
        f"{grade}학년 {grade_class}반 자리배치표"
        if (grade or grade_class) else ""
    )
    fixed_seats_state = {}
    if request.method == 'POST':
        for key, val in request.form.items():
            if key.startswith('fixed_'):
                fixed_seats_state[key] = val
    kst             = pytz.timezone('Asia/Seoul')
    today_str       = datetime.now(kst).strftime('%Y-%m-%d')
    today_str_short = datetime.now(kst).strftime('%y%m%d')
    user_cookie     = request.cookies.get('visit_date')
    is_new = (request.method == 'GET') and (user_cookie != today_str)
    today_cnt, total_cnt = get_and_update_counts(is_new)
    image_url = None
    error_msg = None
    handle_clear_action(action)
    if action.startswith('clear_'):
        data          = load_session_data()
        students_list = data['students_list']
        front_list    = data['front_list']
        restrict_list = data['restrict_list']
        final_rows    = data['final_rows']
    if request.method == 'POST':
        f_student  = request.files.get('student_file')
        f_front    = request.files.get('front_file')
        f_restrict = request.files.get('restrict_file')
        has_file = (
            (f_student  and f_student.filename)  or
            (f_front    and f_front.filename)    or
            (f_restrict and f_restrict.filename)
        )
        if has_file:
            s, f, r = parse_files(
                f_student, f_front, f_restrict, students_list
            )
            if s:
                students_list            = s
                session['students_list'] = s
                session['last_rows']     = []
                final_rows               = []
            if f:
                front_list            = f
                session['front_list'] = f
            if r:
                restrict_list            = r
                session['restrict_list'] = r
        elif action in ('run', 'arrange', 'redraw'):
            if not students_list:
                error_msg = "⚠️ 학생 명단이 없습니다. 파일을 먼저 업로드해주세요."
            else:
                fixed_dict      = parse_fixed_seats(fixed_seats_state, col_num)
                restriction_set = {frozenset(p) for p in restrict_list}
                if action in ('run', 'arrange'):
                    # ── 배치 방식 분기 (신규) ─────────────────
                    if arrange_type == 'ordered':
                        new_rows = arrange_by_order(
                            students_list, col_num, order_dir, fixed_dict
                        )
                        if new_rows:
                            session['last_rows'] = new_rows
                            final_rows           = new_rows
                            logger.info(f"번호순 배치 성공: {len(new_rows)}줄")
                        else:
                            error_msg = "❌ 번호순 배치에 실패했습니다."
                    else:
                        new_rows = arrange_seats_logic(
                            students_list, restriction_set,
                            col_num, set(front_list), fixed_dict
                        )
                        if new_rows:
                            session['last_rows'] = new_rows
                            final_rows           = new_rows
                            logger.info(f"랜덤 배치 성공: {len(new_rows)}줄")
                        else:
                            error_msg = "❌ 조건을 만족하는 배치를 찾지 못했습니다."
                else:
                    final_rows = session.get('last_rows', []) or []
    if final_rows:
        fixed_dict_for_draw = parse_fixed_seats(fixed_seats_state, col_num)
        file_colors    = load_colors()
        saved_colors   = session.get('custom_colors', {})
        current_colors = {**file_colors, **saved_colors}
        image_url = generate_image_b64(
            final_rows, col_num, view_type, seat_mode,
            front_list, fixed_dict_for_draw,
            students_list, title_text,
            colors=current_colors
        )
    template_data = prepare_template_data(
        students_list, front_list, restrict_list,
        final_rows, col_num, fixed_seats_state,
        image_url, error_msg, view_type, seat_mode,
        today_cnt, total_cnt, today_str_short,
        arrange_type=arrange_type,   # ← 신규
        order_dir=order_dir,         # ← 신규
    )
    response = make_response(render_template('index.html', **template_data))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"]        = "no-cache"
    response.headers["Expires"]       = "0"
    if is_new:
        response.set_cookie('visit_date', today_str, max_age=60 * 60 * 24)
    return response
# ============================================================
# 13. 이미지 다운로드
# ============================================================
@app.route('/download_image/<mode>')
def download_image(mode: str):
    last_rows     = session.get('last_rows')
    students_list = session.get('students_list', [])
    front_list    = session.get('front_list',    [])
    try:
        col_num = int(request.args.get('col_num', 8))
        col_num = max(1, min(col_num, 20))
    except (ValueError, TypeError):
        col_num = 8
    view_type   = request.args.get('view_type',   'student')
    seat_mode   = request.args.get('seat_mode',   'pair')
    grade       = request.args.get('grade',       '')
    grade_class = request.args.get('grade_class', '')
    title_text  = (
        f"{grade}학년 {grade_class}반 자리배치표"
        if (grade or grade_class) else ""
    )
    seats_str = request.args.get('seats')
    if seats_str:
        flat_seats = seats_str.split(',')
        if view_type == 'teacher':
            flat_seats.reverse()
        last_rows = [
            flat_seats[i:i + col_num]
            for i in range(0, len(flat_seats), col_num)
        ]
    if not last_rows:
        return (
            "<script>"
            "alert('저장할 배치 데이터가 없습니다.');"
            "history.back();"
            "</script>"
        )
    file_colors    = load_colors()
    saved_colors   = session.get('custom_colors', {})
    current_colors = {**file_colors, **saved_colors}
    try:
        img_io = draw_seat_chart(
            last_rows, col_num, view_type, seat_mode,
            front_list, {},
            all_students=students_list,
            with_list=(mode == 'full'),
            title_text=title_text,
            colors=current_colors
        )
        prefix   = f"{grade}학년_{grade_class}반_" if grade else ""
        today_aa = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d')
        filename = f"{prefix}자리배치_{today_aa}.png"
        return send_file(
            img_io,
            as_attachment=True,
            download_name=filename,
            mimetype='image/png'
        )
    except Exception as e:
        logger.error(f"이미지 다운로드 오류: {e}")
        return f"이미지 생성 중 오류 발생: {e}", 500
# ============================================================
# 14. 예시 파일 다운로드
# ============================================================
@app.route('/download_sample/<file_type>')
def download_sample(file_type: str):
    if file_type == 'student':
        data = [
            ['1','윤동희'],  ['2','전민재'],  ['3','한태양'],  ['4','황성빈'],  ['5','손호영'],
            ['6','전준우'],  ['7','김도영'],  ['8','구자욱'],  ['9','최정'],   ['10','양의지'],
            ['11','류현진'], ['12','강백호'], ['13','김혜성'], ['14','박민우'], ['15','오지환'],
            ['16','양현종'], ['17','김광현'], ['18','원태인'], ['19','노시환'], ['20','문동주'],
            ['21','홍창기'], ['22','정수빈'], ['23','박동원'], ['24','최형우'], ['25','나성범'],
            ['26','강민호'], ['27','박세웅'], ['28','김원중'], ['29','고영표'], ['30','박영현'],
            ['31','송성문'], ['32','채은성'], ['33','정해영'], ['34','곽빈'],   ['35','김영웅'],
        ]
        df     = pd.DataFrame(data, columns=['번호', '이름'])
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, header=False)
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name='예시_학생명단.xlsx',
            mimetype=(
                'application/vnd.openxmlformats-'
                'officedocument.spreadsheetml.sheet'
            )
        )
    elif file_type == 'front':
        content = "윤동희\n원태인\n최정\n송성문"
        output  = io.BytesIO(content.encode('utf-8'))
        return send_file(
            output,
            as_attachment=True,
            download_name='예시_앞자리.txt',
            mimetype='text/plain'
        )
    elif file_type == 'restrict':
        content = "윤동희,한태양\n윤동희,황성빈\n곽빈,황성빈\n노시환,김원중"
        output  = io.BytesIO(content.encode('utf-8'))
        return send_file(
            output,
            as_attachment=True,
            download_name='예시_짝_제한.txt',
            mimetype='text/plain'
        )
    logger.warning(f"알 수 없는 sample 타입 요청: {file_type}")
    return "파일을 찾을 수 없습니다.", 404
# ============================================================
# 15. 명단 수동 수정 라우트
# ============================================================
@app.route('/update_list/<list_type>', methods=['POST'])
def update_individual_list(list_type: str):
    if list_type not in ('student', 'front', 'restrict'):
        return jsonify({'status': 'error', 'message': '잘못된 요청입니다.'}), 400
    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': '요청 데이터가 없습니다.'}), 400
    raw_text = data.get('text', '').strip()
    lines    = [line.strip() for line in raw_text.splitlines() if line.strip()]
    full_students = session.get('students_list', [])
    name_map = {}
    for s in full_students:
        if '.' in s:
            parts = s.split('.', 1)
            name_map[parts[1].strip()] = s
    def auto_match_name(input_txt: str) -> str:
        txt = input_txt.strip()
        if '.' in txt:
            return txt
        return name_map.get(txt, txt)
    if list_type == 'student':
        session['students_list'] = lines
        session['last_rows']     = None
    elif list_type == 'front':
        temp_front = [auto_match_name(line) for line in lines if line]
        temp_front.sort(
            key=lambda x: int(x.split('.')[0])
            if '.' in x and x.split('.')[0].isdigit()
            else 99999
        )
        session['front_list'] = temp_front
    elif list_type == 'restrict':
        parsed_restrict = []
        for line in lines:
            parts = line.split(',')
            if len(parts) >= 2:
                p1 = auto_match_name(parts[0])
                p2 = auto_match_name(parts[1])
                parsed_restrict.append([p1, p2])
        session['restrict_list'] = parsed_restrict
    session.modified = True
    return jsonify({'status': 'success'})
# ============================================================
# 16. 커스텀 다운로드
# ============================================================
@app.route('/api/download_custom', methods=['POST'])
def download_custom():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': '요청 데이터가 없습니다.'}), 400
        seats = data.get('seats', [])
        if not seats:
            return jsonify({'status': 'error', 'message': '배치 데이터가 없습니다.'}), 400
        mode        = data.get('mode',        'basic')
        grade       = data.get('grade',       '')
        grade_class = data.get('grade_class', '')
        view_type   = data.get('view_type',   'student')
        title_text  = (
            f"{grade}학년 {grade_class}반 자리배치표"
            if (grade or grade_class) else ""
        )
        col_num       = len(seats[0]) if seats else 8
        students_list = session.get('students_list', [])
        front_list    = session.get('front_list',    [])
        file_colors    = load_colors()
        saved_colors   = session.get('custom_colors', {})
        current_colors = {**file_colors, **saved_colors}
        img_buf = draw_seat_chart(
            seats, col_num, view_type, 'pair',
            front_list, {},
            all_students=students_list,
            with_list=(mode == 'full'),
            title_text=title_text,
            colors=current_colors
        )
        response = make_response(img_buf.getvalue())
        response.headers['Content-Type'] = 'image/png'
        filename = f"수정된_자리배치_{grade}학년{grade_class}반.png"
        try:
            filename = filename.encode('utf-8').decode('latin-1')
        except (UnicodeDecodeError, UnicodeEncodeError):
            filename = "seat_arrangement.png"
        response.headers['Content-Disposition'] = (
            f'attachment; filename={filename}'
        )
        return response
    except Exception as e:
        logger.error(f"download_custom 오류: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
# ============================================================
# 17. 드래그 앤 드롭 세션 동기화
# ============================================================
@app.route('/api/update_seats', methods=['POST'])
def update_seats():
    try:
        data       = request.get_json()
        flat_seats = data.get('seats', [])
        view_type  = data.get('view_type', 'student')
        if flat_seats:
            if view_type == 'teacher':
                flat_seats.reverse()
            last_rows = session.get('last_rows', [])
            col_num   = len(last_rows[0]) if last_rows else 8
            new_rows = [
                flat_seats[i:i + col_num]
                for i in range(0, len(flat_seats), col_num)
            ]
            session['last_rows'] = new_rows
            session.modified     = True
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"update_seats 오류: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
# ============================================================
# 18. 색상 저장/조회 라우트
# ============================================================
@app.route('/api/save_colors', methods=['POST'])
def save_colors():
    """사용자 색상 설정 저장 (세션 + 파일)"""
    try:
        import re
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': '데이터 없음'}), 400
        filtered = {}
        for key, val in data.items():
            if key not in DEFAULT_COLORS:
                continue
            if not re.match(r'^#[0-9A-Fa-f]{3,8}$', str(val)):
                return jsonify({
                    'status':  'error',
                    'message': f'잘못된 색상값: {val}'
                }), 400
            filtered[key] = val
        session['custom_colors'] = filtered
        session.modified = True
        save_colors_to_file(filtered)
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"save_colors 오류: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
@app.route('/api/get_colors', methods=['GET'])
def get_colors():
    """현재 적용된 색상 반환"""
    file_colors  = load_colors()
    saved_colors = session.get('custom_colors', {})
    merged       = {**file_colors, **saved_colors}
    return jsonify(merged)
@app.route('/privacy')
def privacy():
    return render_template('privacy.html')
# ============================================================
# 19. 앱 실행
# ============================================================
if __name__ == '__main__':
    debug_mode = IS_WINDOWS
    app.run(debug=debug_mode)