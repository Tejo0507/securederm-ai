# SecureDerm AI — Development Roadmap

> Status legend: `[ ]` not started · `[~]` in progress · `[x]` done

---

## Phase A — Core ML

- [ ] Build wound classification model (ResNet18, 4-class output)
- [ ] Create PyTorch Dataset class for wound images (JPEG/PNG, 224x224)
- [ ] Implement training pipeline with CrossEntropyLoss + Adam optimizer
- [ ] Add evaluation metrics (accuracy, precision, recall, F1, confusion matrix)
- [ ] Add per-class accuracy reporting for infection severity levels
- [ ] Validate model on held-out test split before federated integration

---

## Phase B — Federated Learning

- [ ] Implement hospital client training node (local train → weight extraction)
- [ ] Build gradient serialization (state_dict → bytes → base64)
- [ ] Set up secure HTTPS transmission channel for gradient uploads
- [ ] Implement Federated Averaging (FedAvg) on aggregator side
- [ ] Add weighted averaging based on dataset size per node
- [ ] Build model versioning system (increment on each aggregation round)
- [ ] Test 2-node simulation end-to-end

---

## Phase C — Privacy Layer

- [ ] Integrate Opacus PrivacyEngine into local training loop
- [ ] Configure gradient clipping (max_grad_norm)
- [ ] Configure Gaussian noise injection (epsilon=3, delta=1e-5)
- [ ] Validate privacy budget tracking across rounds
- [ ] Add assertion: raw images never leave node (network payload check)

---

## Phase D — Aggregator Server

- [ ] Build `POST /node/register` — node registration + token issuance
- [ ] Build `POST /training/update` — receive encrypted gradients
- [ ] Build `GET /model/latest` — serve latest global model weights
- [ ] Implement node management (track registered hospitals + dataset sizes)
- [ ] Add JWT-based authentication for API endpoints
- [ ] Add Prometheus metrics endpoint for monitoring
- [ ] Add model checkpoint saving after each aggregation round

---

## Phase E — Edge Deployment

- [ ] Export trained PyTorch model to ONNX format
- [ ] Convert ONNX → TensorFlow Lite (.tflite)
- [ ] Build offline inference pipeline (load image → preprocess → predict)
- [ ] Target output: `{ "severity": "Moderate Infection", "confidence": 0.83 }`
- [ ] Validate inference on Android 9+ device

---

## Phase F — Infrastructure & DevOps

- [ ] Dockerize hospital node (Dockerfile + docker-compose)
- [ ] Dockerize aggregation server
- [ ] Set up Prometheus + Grafana monitoring stack
- [ ] Add CI pipeline (lint, test, type-check)
- [ ] Write deployment playbook for AWS EC2 / GCP Compute Engine

---

## Phase G — Testing

- [ ] Unit tests for dataset_loader
- [ ] Unit tests for training engine
- [ ] Unit tests for aggregation algorithm (FedAvg)
- [ ] Unit tests for privacy layer
- [ ] Integration test: multi-node federated round
- [ ] Security test: verify no raw data in network payloads

---

## Phase H — Future Enhancements

- [ ] Secure aggregation protocols
- [ ] Homomorphic encryption for gradient transmission
- [ ] Multi-region federated network support
- [ ] Additional diagnostic models beyond wound classification
- [ ] MobileNetV2 variant for lighter edge inference
