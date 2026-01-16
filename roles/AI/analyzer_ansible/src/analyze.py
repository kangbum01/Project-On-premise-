import librosa
import numpy as np
import json
import os
import sys
import subprocess
import warnings
import tarfile
from datetime import datetime


# [0. 환경 설정] 
warnings.filterwarnings('ignore')

# ★ Ansible 환경 변수 수신 (환경 변수가 없으면 기존 경로를 기본값으로 사용)
GIT_REPO_PATH = os.getenv("ANALYZER_GIT_PATH", "/home/ansible-admin/project")
NAS_DIR = os.getenv("ANALYZER_NAS_PATH", "/mnt/NAS/result/")
LB_HOST_IP = os.getenv("ANALYZER_LB_IP", "10.4.2.10")
REMOTE_WEB_PATH = os.getenv("ANALYZER_WEB_ROOT", "/usr/share/nginx/html/music-project")

# 파생 경로 설정
GIT_WEB_DIR = os.path.join(GIT_REPO_PATH, "web")
# [0. 환경 설정] 경고 무시 및 인프라 경로 정의
warnings.filterwarnings('ignore')

GIT_REPO_PATH = "/home/ansible-admin/project"
GIT_WEB_DIR = os.path.join(GIT_REPO_PATH, "web")
NAS_DIR = "/mnt/NAS/result/"


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
AUDIO_DIR = os.path.join(ROOT_DIR, "audio")
INPUT_AUDIO = os.path.join(AUDIO_DIR, "input.mp3")
TEMP_WAV = os.path.join(AUDIO_DIR, "temp.wav")

OUTPUT_JSON = os.path.join(GIT_WEB_DIR, "theme.json")
PROJECT_JS = os.path.join(GIT_WEB_DIR, "theme.generated.js")
PROJECT_CSS = os.path.join(GIT_WEB_DIR, "theme.generated.css")

# 디렉토리 생성 보장
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(GIT_WEB_DIR, exist_ok=True)

# [1. 감정 매핑 데이터] - 생략 (기존과 동일)
MOOD_TARGETS = { ... } 

# [2. 감정 랭킹 / 3. 물리 지표 함수] - 생략 (기존과 동일)
def get_emotion_ranking(f): ...
def analyze_physics(y, sr): ...

# 디렉토리 사전에 생성
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(GIT_WEB_DIR, exist_ok=True)

# [1. 정밀 감정 매핑 데이터]
MOOD_TARGETS = {
    "Manic / Frenetic": (165, 0.95, 3200), "Aggressive / Wild": (150, 0.9, 2100),
    "Joyful / Radiant": (128, 0.85, 2700), "Powerful / Heroic": (115, 0.8, 1900),
    "Tense / Urgent": (140, 0.75, 2400), "Excited / Upbeat": (135, 0.7, 2300),
    "Cheerful / Sunny": (122, 0.65, 2500), "Mysterious / Driving": (105, 0.6, 1400),
    "Focused / Rhythmic": (124, 0.55, 1800), "Calm / Balanced": (92, 0.45, 1700),
    "Whimsical / Curious": (108, 0.4, 2600), "Anxious / Fast-paced": (145, 0.35, 2800),
    "Relaxed / Chill": (85, 0.3, 1900), "Melancholic / Dreamy": (75, 0.25, 1200),
    "Sad / Lonely": (68, 0.2, 900), "Depressing / Gloomy": (62, 0.15, 750),
    "Atmospheric / Ethereal": (82, 0.35, 3600), "Neutral / Ambient": (100, 0.5, 2000),
    "Dark / Heavy": (95, 0.85, 850), "Soft / Tender": (80, 0.25, 1500),
    "Stressed / Chaotic": (160, 0.8, 2900), "Brave / Epic": (110, 0.9, 1800),
    "Lonely / Quiet": (65, 0.1, 1100), "Vibrant / Sharp": (130, 0.75, 3300),
    "Deep / Soulful": (88, 0.55, 1300)
}

# [2. 감정 랭킹 계산 엔진]
def get_emotion_ranking(f):
    t, i, b = f['tempo'], f['intensity'], f['brightness']
    rankings = []
    for mood, target in MOOD_TARGETS.items():
        dist = np.sqrt(((t - target[0])/60)**2 + ((i - target[1])/0.5)**2 + ((b - target[2])/1500)**2)
        score = np.exp(-3.0 * dist)
        rankings.append({"mood": mood, "score": float(score)})
    rankings = sorted(rankings, key=lambda x: x['score'], reverse=True)[:5]
    scores = np.array([r['score'] for r in rankings])
    exp_scores = np.exp(scores * 6.5)
    probs = exp_scores / exp_scores.sum()
    return [{"mood": r['mood'], "confidence": f"{round(p * 100, 2)}%"} for r, p in zip(rankings, probs)]

# [3. 물리 지표 분석 함수]
def analyze_physics(y, sr):
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, _ = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)
    tempo = float(tempo[0]) if isinstance(tempo, np.ndarray) else float(tempo)
    rms = librosa.feature.rms(y=y)[0]
    intensity = min(1.0, np.mean(rms) * 5.0 + np.var(rms) * 18)
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    brightness = np.percentile(centroid, 85)
    key_idx = int(np.argmax(np.mean(librosa.feature.chroma_stft(y=y, sr=sr), axis=1)))
    return {"tempo": round(tempo, 1), "intensity": round(float(intensity), 3), 
            "brightness": round(float(brightness), 2), "key_index": key_idx}


# [4. 메인 실행 프로세스]
def analyze():
    if not os.path.exists(INPUT_AUDIO):
        print("[ERROR] 입력 파일(input.mp3)이 없습니다."); return

    try:

        # --- 0. LB 서버 기존 파일 삭제 (Ansible에서 주입받은 IP/경로 사용) ---
        print(f">>> [0/5] LB 서버({LB_HOST_IP}) 기존 파일 청소 중...")
        lb_user_host = f"ansible-admin@{LB_HOST_IP}"
        targets = f"{REMOTE_WEB_PATH}/theme.json {REMOTE_WEB_PATH}/theme.generated.js {REMOTE_WEB_PATH}/theme.generated.css"
        clean_cmd = f"ssh -o StrictHostKeyChecking=no {lb_user_host} 'rm -f {targets}'"
        subprocess.run(clean_cmd, shell=True, check=False)

        # --- A. 분석 및 리소스 생성 ---
        print(">>> [1/5] 오디오 전처리...")

        # =========================================================================
        # ★ [추가됨] 0. LB 서버 기존 파일 삭제 (Frontend Cache 방지)
        # =========================================================================
        print(">>> [0/5] LB 서버(10.4.2.10) 기존 파일 청소 중...")
        lb_host = "ansible-admin@10.4.2.10"
        remote_path = "/usr/share/nginx/html/music-project"
        
        # 삭제할 파일 목록 (공백으로 구분)
        targets = f"{remote_path}/theme.json {remote_path}/theme.generated.js {remote_path}/theme.generated.css"
        
        # SSH 명령 실행 (rm -f로 파일이 없어도 에러 무시)
        clean_cmd = f"ssh -o StrictHostKeyChecking=no {lb_host} 'rm -f {targets}'"
        
        # 에러가 나도 분석은 계속되어야 하므로 try-except 없이 check=False로 실행
        subprocess.run(clean_cmd, shell=True, check=False)
        print("    [Clean] LB 서버 파일 삭제 명령 전송 완료")
        # =========================================================================

        # --- A. 분석 및 리소스 생성 ---
        print(">>> [1/5] 오디오 전처리 (0초~10초)...")

        subprocess.run(["ffmpeg", "-y", "-i", INPUT_AUDIO, "-ar", "16000", "-ss", "0", "-t", "10", TEMP_WAV], check=True, capture_output=True)
        y, sr = librosa.load(TEMP_WAV, sr=16000)

        print(">>> [2/5] 음악 물리 지표 정밀 분석...")
        features = analyze_physics(y, sr)

        print(">>> [3/5] 감정 랭킹 추출 및 테마 계산...")
        emotion_rankings = get_emotion_ranking(features)
        primary_mood = emotion_rankings[0]['mood']
        

        # 테마 계산 로직 (기존과 동일)
        hue = (features['key_index'] * 30 + (features['brightness'] / 100)) % 360
        sat = 80 if features['intensity'] > 0.6 else 50
        palette = {"main": f"hsl({hue:.1f}, {sat}%, 45%)", "bg": f"hsl({hue:.1f}, 20%, 8%)", "accent": f"hsl({(hue+150)%360:.1f}, 90%, 50%)"}

        hue = (features['key_index'] * 30 + (features['brightness'] / 100)) % 360
        sat = 80 if features['intensity'] > 0.6 else 50
        palette = {"main": f"hsl({hue:.1f}, {sat}%, 45%)", "bg": f"hsl({hue:.1f}, 20%, 8%)", "accent": f"hsl({(hue+150)%360:.1f}, 90%, 50%)"}


        theme_data = {"analysis": features, "emotion_rankings": emotion_rankings, "palette": palette, "updated": datetime.now().isoformat()}
        
        # 파일 저장
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f: json.dump(theme_data, f, indent=4, ensure_ascii=False)
        with open(PROJECT_JS, "w", encoding="utf-8") as f: f.write(f"window.MRDW_DATA = {json.dumps(theme_data, ensure_ascii=False)};")
        
        beat_dur = round(60 / features['tempo'], 3)
        css = f":root {{ --mrdw-main: {palette['main']}; --mrdw-accent: {palette['accent']}; --mrdw-beat: {beat_dur}s; --mrdw-glow: {int(features['intensity']*60)}px; }}"
        with open(PROJECT_CSS, "w", encoding="utf-8") as f: f.write(css)


        # --- B. NAS 아카이빙 ---
        print(f">>> [4/5] NAS 아카이빙 시도 ({NAS_DIR})...")
        # --- B. NAS 아카이빙 (독립된 예외 처리) ---
        print(">>> [4/5] NAS 아카이빙 시도...")

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        nas_file_name = f"음악분석파일_{ts}.tar.gz"
        local_zip = os.path.join("/tmp", nas_file_name)
        
        try:
            with tarfile.open(local_zip, "w:gz") as tar:
                for f_path in [OUTPUT_JSON, PROJECT_JS, PROJECT_CSS]:
                    tar.add(f_path, arcname=os.path.basename(f_path))
            subprocess.run(["cp", local_zip, os.path.join(NAS_DIR, nas_file_name)], check=True, timeout=5)

            print(f"    [NAS SUCCESS] 아카이브 완료")
        except Exception as nas_err:
            print(f"    [NAS ERROR] 과정 무시 후 진행: {nas_err}")

        # --- C. Git Push ---
        print(f">>> [5/5] Git Push 진행 ({GIT_REPO_PATH})...")

            print(f"    [NAS SUCCESS] 아카이브 완료: {nas_file_name}")
        except Exception as nas_err:
            print(f"    [NAS ERROR] 복사 실패 (과정 무시 후 배포 진행): {nas_err}")

        # --- C. Git Push 및 배포 트리거 ---
        print(">>> [5/5] Git Push 및 Ansible 자동 배포 트리거...")

        try:
            subprocess.run(["git", "add", "."], cwd=GIT_REPO_PATH, check=True)
            subprocess.run(["git", "commit", "-m", f"Vibe Shift: {primary_mood}"], cwd=GIT_REPO_PATH, check=True)
            subprocess.run(["git", "push", "origin", "main"], cwd=GIT_REPO_PATH, check=True, timeout=20)

            print(f"\n[분석 완료] 배포 성공! 무드: {primary_mood}")
        except Exception as git_err:
            print(f"    [GIT ERROR] 실패: {git_err}")
            print(f"\n[분석 완료] 배포 성공! 현재 무드: {primary_mood}")
        except Exception as git_err:
            print(f"    [GIT ERROR] Git 작업 실패: {git_err}")


    except Exception as e:
        print(f"\n[FATAL ERROR] 분석 파이프라인 중단: {e}")
    finally:

        for f_path in [TEMP_WAV, INPUT_AUDIO]:
            if os.path.exists(f_path): os.remove(f_path)
        print(">>> [System] 임시 파일 정리 완료.")
        # 다음 파일 처리를 위한 자원 정리
        for f_path in [TEMP_WAV, INPUT_AUDIO]:
            if os.path.exists(f_path):
                os.remove(f_path)
        print(">>> [System] 임시 파일 정리 완료. 다음 요청 대기 중.")

if __name__ == "__main__":
    analyze()
