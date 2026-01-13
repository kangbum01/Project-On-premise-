### 구성
music_project/
└── infra/
    ├── inventory/
    │   ├── hosts.ini            # 기존 hosts.ini 활용
    │   └── group_vars/
    │       ├── all.yml          # [중요] 모든 공통 변수
    │       ├── ai_server.yml    # AI 서버 관련 변수
    │       └── jenkins.yml      # 젠킨스 관련 변수
    ├── roles/
    │   ├── common/              # distribute_key.yaml, sync_time.yaml 로직
    │   ├── ai_server/           # setup_git_client.yaml 로직
    │   ├── jenkins_setup/       # install_Jenkins.yaml, Dockerfile, jenkins.yaml.j2
    │   └── web_deploy/          # deploy.yaml 로직
    └── playbooks/
        └── site.yml             # 모든 Role을 실행하는 마스터 코드
