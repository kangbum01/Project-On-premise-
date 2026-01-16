#!/bin/bash

# 1. 초기 경로 설정
PROJECT_ROOT=$(pwd)
ANSIBLE_DIR="$PROJECT_ROOT/ansible"
SRC_DIR="$PROJECT_ROOT/src"

echo ">>> [1/3] 프로젝트 구조 및 Ansible 최적화 설정 시작..."
mkdir -p $ANSIBLE_DIR/templates
mkdir -p $PROJECT_ROOT/audio

# 2. 원격 배포용 최적화 Playbook 생성 (deploy.yml)
# 핵심: 'copy' 모듈을 사용하여 관리 PC의 소스코드를 대상 서버로 전송함
cat <<EOF > $ANSIBLE_DIR/deploy.yml
---
- name: Remote Deploy Music Analyzer API (CentOS 9)
  hosts: analysis_node
  become: yes
  vars:
    # 대상 서버에서 프로젝트가 설치될 절대 경로
    remote_project_path: "/home/{{ ansible_user_id }}/music_analyzer"

  tasks:
    - name: 1. 시스템 필수 저장소 및 패키지 설치
      dnf:
        name:
          - epel-release
          - https://mirrors.rpmfusion.org/free/el/rpmfusion-free-release-9.noarch.rpm
          - https://mirrors.rpmfusion.org/nonfree/el/rpmfusion-nonfree-release-9.noarch.rpm
          - python3-pip
          - python3-devel
          - ffmpeg
          - libsndfile
          - atlas-devel
          - gcc-c++
        state: present
        disable_gpg_check: yes

    - name: 2. CRB 저장소 활성화
      shell: dnf config-manager --set-enabled crb
      changed_when: false

    - name: 3. Python 패키지 설치 (CPU 전용 최적화)
      pip:
        name: [torch, torchaudio, python-multipart, fastapi, uvicorn, librosa, transformers, soundfile, "numpy<2.0"]
        extra_args: "--extra-index-url https://download.pytorch.org/whl/cpu"

    - name: 4. 프로젝트 디렉토리 생성
      file:
        path: "{{ item }}"
        state: directory
        owner: "{{ ansible_user_id }}"
        mode: '0755'
      loop:
        - "{{ remote_project_path }}"
        - "{{ remote_project_path }}/src"
        - "{{ remote_project_path }}/audio"
        - "/home/{{ ansible_user_id }}/project/web"

    - name: 5. 소스 코드 전송 (Local -> Remote)
      copy:
        src: "{{ item }}"
        dest: "{{ remote_project_path }}/src/"
        owner: "{{ ansible_user_id }}"
        mode: '0644'
      loop:
        - "{{ playbook_dir }}/../src/api.py"
        - "{{ playbook_dir }}/../src/analyze.py"

    - name: 6. Systemd 서비스 파일 배포
      template:
        src: templates/music_analyzer.service.j2
        dest: /etc/systemd/system/music_analyzer.service

    - name: 7. 서비스 상시 가동 및 자동 실행 상태 보장 (Final)
      systemd:
        name: music_analyzer
        state: started
        enabled: yes
        daemon_reload: yes

    - name: 8. 방화벽 8000포트 오픈
      firewalld:
        port: 8000/tcp
        permanent: yes
        state: enabled
      ignore_errors: yes

  handlers:
    - name: Restart Service
      systemd:
        name: music_analyzer
        state: restarted
EOF

# 3. Systemd 템플릿 (원격 경로 변수 반영)
cat <<EOF > $ANSIBLE_DIR/templates/music_analyzer.service.j2
[Unit]
Description=MRDW Music Analyzer API Service
After=network.target

[Service]
User={{ ansible_user_id }}
WorkingDirectory={{ remote_project_path }}/src
ExecStart=/usr/bin/python3 -u {{ remote_project_path }}/src/api.py
Restart=always
TimeoutStartSec=300
Environment=PYTHONPATH={{ remote_project_path }}/src
Environment=PYTHONUNBUFFERED=1
Environment=HOME=/home/{{ ansible_user_id }}

[Install]
WantedBy=multi-user.target
EOF

# 4. ProxyJump 설정이 포함된 예시 인벤토리 생성 (hosts.ini)
cat <<EOF > $ANSIBLE_DIR/hosts.ini
[analysis_node]
# 여기에 대상 서버 정보를 입력하세요
analysis_vm ansible_host=10.4.1.11 ansible_user=ansible-admin

[analysis_node:vars]
# 중계 서버(Bastion) 설정 예시
ansible_ssh_common_args='-o ProxyCommand="ssh -W %h:%p -q ansible-admin@172.16.6.81"'
ansible_python_interpreter=/usr/bin/python3
EOF

echo ">>> [2/3] .gitignore 생성..."
cat <<EOF > $PROJECT_ROOT/.gitignore
__pycache__/
*.pyc
audio/*.mp3
audio/*.wav
ansible/*.retry
EOF

echo ">>> [3/3] 완료! 이제 전체 폴더를 Git Repo에 Push 하세요."
echo "상대방은 'ansible-playbook -i hosts.ini deploy.yml --ask-become-pass'만 치면 됩니다."
