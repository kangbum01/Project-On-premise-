from fastapi import FastAPI, UploadFile, File, HTTPException
import shutil
import os
import uvicorn
import sys
import traceback

# -----------------------------
# 1. 모듈 경로 및 환경 변수 설정
# -----------------------------
# Ansible이 주입한 프로젝트 루트 경로를 가져옵니다.
PROJECT_ROOT = os.getenv("ANALYZER_PROJECT_PATH", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")

# 모듈 로드를 위해 src 디렉토리를 path에 추가
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

analyze = None
try:
    import analyze 
    print(f"[API] analyze.py 모듈 로드 성공 (Path: {SRC_DIR})")
except Exception as e:
    print(f"[ERROR] analyze.py 로드 실패! 원인: {e}")

app = FastAPI(title="MRDW Music Analyzer API")

# -----------------------------
# 2. 공유 경로 설정 (Ansible 변수 기반)
# -----------------------------
# 분석 엔진과 공유할 오디오 저장 경로
AUDIO_DIR = os.path.join(PROJECT_ROOT, "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

@app.post("/upload")
async def upload_music(file: UploadFile = File(...)):
    # analyze.py가 기다리고 있는 파일명으로 저장
    input_path = os.path.join(AUDIO_DIR, "input.mp3")

    try:
        with open(input_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        print(f"\n[API] 파일 수신 및 저장 완료: {input_path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 저장 실패: {str(e)}")

    # [분석 실행] analyze.py의 analyze() 함수 호출
    if analyze and hasattr(analyze, 'analyze'):
        try:
            print("[API] 분석 엔진(analyze.py) 가동...")
            analyze.analyze() 
            print("[API] 모든 파이프라인 프로세스 완료")
        except Exception as e:
            print(f"[API] 분석 실행 중 에러: {str(e)}")
            return {"status": "warning", "message": f"분석 중 오류 발생: {str(e)}"}
    else:
        msg = "analyze 모듈을 찾을 수 없습니다. src 디렉토리 구성을 확인하세요."
        print(f"[API] 경고: {msg}")
        return {"status": "error", "message": msg}

    return {
        "status": "success", 
        "message": "분석 및 배포 완료", 
        "file_name": file.filename,
        "storage_path": input_path
    }

if __name__ == "__main__":
    # 포트 번호도 필요하다면 환경 변수로 관리 가능합니다.
    api_port = int(os.getenv("ANALYZER_API_PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=api_port)
