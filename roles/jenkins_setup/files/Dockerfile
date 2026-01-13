FROM jenkins/jenkins:lts
USER root

# 컨테이너 내부에 ansible 설치
RUN apt-get update && apt-get install -y \
    ansible \
    python3-pip \
    python3-docker \
    && apt-get clean


# 플러그인 자동 설치 (JCasC, Git, Pipeline, Ansible 등)
RUN jenkins-plugin-cli --plugins \
    configuration-as-code \
    git \
    workflow-aggregator \
    ansible \
    job-dsl

USER jenkins
# JCasC 환경 변수 설정
ENV CASC_JENKINS_CONFIG=/var/jenkins_home/casc_configs/jenkins.yaml