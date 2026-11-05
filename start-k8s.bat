@echo off
REM Step 1: Build the FastAPI Backend Docker image with the tag Kubernetes expects
echo [1/4] Building FastAPI Backend image for Kubernetes...
docker build -t ecommerce-backend:latest ./backend

REM Step 2: Build the Express.js Frontend Docker image with the tag Kubernetes expects
echo [2/4] Building Express.js Frontend image for Kubernetes...
docker build -t ecommerce-frontend-web:latest ./frontend-web

REM Step 3: Deploy all Pods, Services, Autoscaler (HPA), and NetworkPolicy to Kubernetes
echo [3/4] Deploying to Kubernetes cluster...
kubectl apply -f k8s/k8s-manifests.yaml
kubectl rollout restart deployment ecommerce-backend ecommerce-frontend

REM Step 4: Wait 4 seconds for Kubernetes Pods to become Ready and open browser on NodePort 30300
echo [4/4] Waiting for Kubernetes Pods to start...
timeout /t 4 /nobreak >nul
kubectl get pods
start http://localhost:30300