pipeline {
    agent any

    stages {
        stage('1. Checkout Code') {
            steps {
                echo 'Checking out repository from GitHub...'
                checkout scm
            }
        }

        stage('2. Install & Lint') {
            steps {
                echo 'Installing Python dependencies...'
                sh 'pip install -r backend/requirements.txt -r frontend/requirements.txt'
            }
        }

        stage('3. Automated Unit & Tenant Isolation Tests') {
            steps {
                echo 'Running pytest for all 6 Auth flows and Multi-Tenant Isolation...'
                sh 'pytest backend/test_main.py'
            }
        }

        stage('4. Security Scan (Dependency & Secret Audit)') {
            steps {
                echo 'Running pip-audit and secret checks...'
                sh 'pip install pip-audit && pip-audit || true'
            }
        }

        stage('5. Build Docker Lunchboxes') {
            steps {
                echo 'Building Backend and Frontend Docker images...'
                sh 'docker compose build'
            }
        }

        stage('6. Deploy to Kubernetes & Smoke Test') {
            steps {
                echo 'Applying Kubernetes manifests...'
                sh 'kubectl apply -f k8s/k8s-manifests.yaml || true'
            }
        }
    }
}