"""
Standalone federated training demo for presentations.

What this script shows:
1) Client-level local training
2) Explicit assignment of aggregation weights
3) Weighted FedAvg parameter aggregation
4) Round-wise global loss/accuracy tracking

This file is intentionally self-contained and does not modify any existing project files.

Run:
    d:\\securederm-ai\\venv\\Scripts\\python.exe scripts\\presentation_federated_training_demo.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


SEED = 42
INPUT_DIM = 8
NUM_CLASSES = 3
NUM_CLIENTS = 3
LOCAL_EPOCHS = 2
ROUNDS = 5
BATCH_SIZE = 32
LR = 0.05


torch.manual_seed(SEED)


class TinyClassifier(nn.Module):
    def __init__(self, input_dim: int, num_classes: int) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 16),
            nn.ReLU(),
            nn.Linear(16, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


@dataclass
class ClientData:
    name: str
    train_loader: DataLoader
    val_loader: DataLoader
    num_train_samples: int


def make_synthetic_split(n: int, shift: float) -> Tuple[torch.Tensor, torch.Tensor]:
    x = torch.randn(n, INPUT_DIM) + shift
    logits = torch.stack(
        [
            0.6 * x[:, 0] - 0.2 * x[:, 1] + 0.1 * shift,
            -0.3 * x[:, 2] + 0.7 * x[:, 3] - 0.05 * shift,
            0.4 * x[:, 4] + 0.4 * x[:, 5] + 0.2 * shift,
        ],
        dim=1,
    )
    y = logits.argmax(dim=1)
    return x, y


def build_clients() -> List[ClientData]:
    specs = [
        ("Hospital_A", 320, -0.4),
        ("Hospital_B", 220, 0.2),
        ("Hospital_C", 160, 0.7),
    ]
    clients: List[ClientData] = []

    for name, n_samples, shift in specs:
        x, y = make_synthetic_split(n_samples, shift)
        split = int(0.8 * n_samples)
        x_train, y_train = x[:split], y[:split]
        x_val, y_val = x[split:], y[split:]

        train_loader = DataLoader(
            TensorDataset(x_train, y_train), batch_size=BATCH_SIZE, shuffle=True
        )
        val_loader = DataLoader(
            TensorDataset(x_val, y_val), batch_size=BATCH_SIZE, shuffle=False
        )

        clients.append(
            ClientData(
                name=name,
                train_loader=train_loader,
                val_loader=val_loader,
                num_train_samples=len(x_train),
            )
        )

    return clients


def evaluate(model: nn.Module, loaders: List[DataLoader]) -> Tuple[float, float]:
    criterion = nn.CrossEntropyLoss()
    model.eval()

    total_loss = 0.0
    total_correct = 0
    total_count = 0

    with torch.no_grad():
        for loader in loaders:
            for xb, yb in loader:
                logits = model(xb)
                loss = criterion(logits, yb)
                total_loss += loss.item() * xb.size(0)
                preds = logits.argmax(dim=1)
                total_correct += (preds == yb).sum().item()
                total_count += xb.size(0)

    return total_loss / total_count, total_correct / total_count


def local_train(
    global_state: Dict[str, torch.Tensor],
    client: ClientData,
    epochs: int,
) -> Tuple[Dict[str, torch.Tensor], float]:
    model = TinyClassifier(INPUT_DIM, NUM_CLASSES)
    model.load_state_dict(global_state)
    model.train()

    optimizer = torch.optim.SGD(model.parameters(), lr=LR)
    criterion = nn.CrossEntropyLoss()

    running_loss = 0.0
    seen = 0

    for _ in range(epochs):
        for xb, yb in client.train_loader:
            optimizer.zero_grad()
            logits = model(xb)
            loss = criterion(logits, yb)
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * xb.size(0)
            seen += xb.size(0)

    avg_loss = running_loss / max(seen, 1)
    return model.state_dict(), avg_loss


def fedavg(
    local_states: List[Dict[str, torch.Tensor]],
    weights: List[float],
) -> Dict[str, torch.Tensor]:
    agg_state: Dict[str, torch.Tensor] = {}
    keys = local_states[0].keys()

    for k in keys:
        weighted = [state[k] * w for state, w in zip(local_states, weights)]
        agg_state[k] = torch.stack(weighted, dim=0).sum(dim=0)

    return agg_state


def main() -> None:
    clients = build_clients()

    total_samples = sum(c.num_train_samples for c in clients)
    agg_weights = [c.num_train_samples / total_samples for c in clients]

    global_model = TinyClassifier(INPUT_DIM, NUM_CLASSES)
    global_state = global_model.state_dict()

    print("=" * 78)
    print("SecureDerm AI - Federated Training Presentation Demo")
    print("=" * 78)
    print("Client sample distribution and aggregation weights:")
    for c, w in zip(clients, agg_weights):
        print(f"  - {c.name}: {c.num_train_samples} samples, FedAvg weight={w:.4f}")
    print("-" * 78)

    val_loaders = [c.val_loader for c in clients]

    for rnd in range(1, ROUNDS + 1):
        local_states: List[Dict[str, torch.Tensor]] = []
        local_losses: List[float] = []

        for c in clients:
            state, loss = local_train(global_state, c, epochs=LOCAL_EPOCHS)
            local_states.append(state)
            local_losses.append(loss)

        global_state = fedavg(local_states, agg_weights)
        global_model.load_state_dict(global_state)

        global_val_loss, global_val_acc = evaluate(global_model, val_loaders)

        print(f"Round {rnd}/{ROUNDS}")
        for c, l in zip(clients, local_losses):
            print(f"  Local train loss - {c.name}: {l:.4f}")
        print(f"  Global val loss: {global_val_loss:.4f}")
        print(f"  Global val accuracy: {global_val_acc * 100:.2f}%")
        print("-" * 78)

    print("Training complete. Use the above metrics/weights directly in your presentation.")


if __name__ == "__main__":
    main()
