# SecureDerm AI — Development Roadmap

> Status legend: `[ ]` not started · `[~]` partly done · `[x]` done and covered by the code or tests

---

## Phase A — Core ML

- [x] Build wound classification model (ResNet18, 10-class output)
- [x] Create PyTorch Dataset class for wound images (JPEG/PNG, 224x224)
- [x] Implement training pipeline with CrossEntropyLoss + Adam optimizer
- [x] Add evaluation metrics (accuracy, precision, recall, F1, confusion matrix)
- [x] Add per-class reporting (`python -m scripts.evaluate_global_model`)
- [x] Validate model on a held-out split before federated integration

---

## Phase B — Federated Learning

- [x] Implement hospital client training node (local train → weight extraction)
- [x] Build gradient serialization (state_dict → bytes → base64, with SHA-256 integrity check)
- [ ] Terminate HTTPS in the app itself (today: put a TLS reverse proxy in front)
- [x] Implement Federated Averaging (FedAvg) on aggregator side
- [x] Add weighted averaging based on dataset size per node
- [x] Build model versioning system (increment on each aggregation round)
- [x] Test 2-node simulation end-to-end

---

## Phase C — Privacy Layer

- [x] Integrate Opacus PrivacyEngine into local training loop
- [x] Configure gradient clipping (max_grad_norm)
- [x] Configure Gaussian noise injection (epsilon=3, delta=1e-5), optionally cryptographically secure
- [x] Validate privacy budget tracking across rounds (per-node ledger, lifetime epsilon cap)
- [~] Assert raw images never leave a node (uploads carry weights only; no dedicated payload-inspection test yet)

---

## Phase D — Aggregator Server

- [x] Build `POST /node/register` — node registration + token issuance
- [x] Build `POST /training/update` — receive model updates
- [x] Build `GET /model/latest` — serve latest global model weights
- [x] Implement node management (track registered hospitals + dataset sizes)
- [~] Token authentication for API endpoints (opaque per-node tokens plus an admin token; not JWT)
- [x] Add Prometheus metrics endpoint for monitoring (`GET /metrics`)
- [x] Add model checkpoint saving after each aggregation round

---

## Phase E — Edge Deployment

- [ ] Export trained PyTorch model to ONNX format
- [ ] Convert ONNX → TensorFlow Lite (.tflite)
- [~] Build offline inference pipeline (`scripts/predict_demo.py` and `model/inference.py` run locally; no mobile build)
- [x] Target output: predicted class, confidence, "unknown" flag, top-k and model fingerprint
- [ ] Validate inference on Android 9+ device

---

## Phase F — Infrastructure & DevOps

- [x] Dockerize hospital node (Dockerfile + docker-compose)
- [x] Dockerize aggregation server
- [ ] Set up Prometheus + Grafana monitoring stack (the `/metrics` endpoint is ready to scrape)
- [x] Add CI pipeline (flake8, pytest, type-check, lint)
- [ ] Write deployment playbook for AWS EC2 / GCP Compute Engine

---

## Phase G — Testing

- [x] Unit tests for dataset_loader
- [x] Unit tests for training engine
- [x] Unit tests for aggregation algorithm (FedAvg)
- [x] Unit tests for privacy layer
- [x] Integration test: multi-node federated round
- [~] Security tests: authentication, CSRF, upload sanitisation, log hygiene (a payload-level "no raw data" test is still open)

---

## Phase H — Future Enhancements

- [ ] Secure aggregation protocols
- [ ] Homomorphic encryption for gradient transmission
- [ ] Multi-region federated network support
- [ ] Additional diagnostic models beyond wound classification
- [ ] MobileNetV2 variant for lighter edge inference
