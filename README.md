# SecureDerm AI

A **federated learning platform** for collaborative wound classification across hospitals — without sharing patient images.

## Architecture

```
Hospital Node A ──┐
Hospital Node B ──┼── encrypted gradients ──▶ Aggregation Server ──▶ Edge Deployment
Hospital Node C ──┘
```

## Quick Start

### 1. Create virtual environment

```bash
cd D:\securederm-ai
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Start the aggregation server

```bash
python -m aggregator.server
```

### 3. Run hospital nodes (in separate terminals)

```bash
python -m hospital_node.client --node hospital_A
python -m hospital_node.client --node hospital_B
```

## Project Structure

```
securederm-ai/
├── aggregator/           # Federated aggregation server
│   ├── server.py         # FastAPI endpoints
│   └── fedavg.py         # Federated averaging algorithm
├── hospital_node/        # Hospital training client
│   ├── client.py         # Node client (register, train, upload)
│   ├── train.py          # Local training loop
│   ├── dataset_loader.py # Wound image dataset loader
│   └── privacy_layer.py  # Differential privacy (Opacus)
├── model/                # ML model definitions
│   └── architecture.py   # ResNet18 wound classifier
├── datasets/             # Mock/real datasets
│   ├── hospital_A/
│   └── hospital_B/
├── scripts/              # Utility scripts
│   └── generate_mock_data.py
├── tests/                # Test suite
├── config/               # Configuration files
│   └── settings.py
└── docs/                 # Documentation
    └── TODO.md           # Development roadmap
```

## Technology Stack

- **Language**: Python 3.11+
- **ML Framework**: PyTorch + TorchVision
- **Privacy**: Opacus (differential privacy)
- **API**: FastAPI + Uvicorn
- **Inference**: TensorFlow Lite (edge)
- **Monitoring**: Prometheus + Grafana