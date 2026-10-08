"""
SecureDerm AI — Global configuration.

Central place for all tunable parameters. Import from here
instead of scattering magic numbers across modules.
"""

import logging
import os
import secrets
from pathlib import Path

_logger = logging.getLogger("config.settings")

# ── Paths ────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASETS_DIR = PROJECT_ROOT / "datasets"
KAGGLE_DATASET_DIR = PROJECT_ROOT / "wound_dataset" / "Wound_dataset copy"
CHECKPOINTS_DIR = PROJECT_ROOT / "checkpoints"
LOGS_DIR = PROJECT_ROOT / "logs"

# ── Model ────────────────────────────────────────────────────────────────
NUM_CLASSES = 10
IMAGE_SIZE = 224
CLASS_LABELS = {
    0: "Abrasions",
    1: "Bruises",
    2: "Burns",
    3: "Cut",
    4: "Diabetic Wounds",
    5: "Laseration",
    6: "Normal",
    7: "Pressure Wounds",
    8: "Surgical Wounds",
    9: "Venous Wounds",
}

# ── Training ─────────────────────────────────────────────────────────────
LEARNING_RATE = 1e-4
BATCH_SIZE = 16
LOCAL_EPOCHS = 1          # epochs per federated round
LOSS_FUNCTION = "CrossEntropyLoss"
OPTIMIZER = "Adam"

# ── Federated Learning ───────────────────────────────────────────────────
AGGREGATOR_HOST = os.getenv("AGGREGATOR_HOST", "127.0.0.1")
AGGREGATOR_PORT = int(os.getenv("AGGREGATOR_PORT", "8000"))
AGGREGATOR_URL = f"http://{AGGREGATOR_HOST}:{AGGREGATOR_PORT}"
FEDERATED_ROUNDS = 5
# Optional operator credential for the aggregator's read-only admin views
# (round metrics, final model download) — lets scripts such as run_demo read
# them without holding a hospital node's token. Unset = admin access off.
AGGREGATOR_ADMIN_TOKEN = os.getenv("AGGREGATOR_ADMIN_TOKEN", "")
# Optional shared secret a new hospital must present (X-Registration-Key) to
# register with the aggregator. Without it anyone who can reach the port can
# enrol a node, receive a token and download the global model.
AGGREGATOR_REGISTRATION_KEY = os.getenv("AGGREGATOR_REGISTRATION_KEY", "")
# Upper bound on enrolled nodes, so open registration can't grow memory forever.
AGGREGATOR_MAX_NODES = int(os.getenv("AGGREGATOR_MAX_NODES", "1000"))
# Maximum L2 distance an uploaded model may sit from the current global model;
# farther updates are scaled back to this radius (limits any one node's
# influence, incl. poisoning). 0 disables clipping.
AGGREGATOR_MAX_UPDATE_NORM = float(os.getenv("AGGREGATOR_MAX_UPDATE_NORM", "0"))
# Persist the global model across aggregator restarts (see aggregator.server).
AGGREGATOR_PERSIST = os.getenv("AGGREGATOR_PERSIST", "true").lower() != "false"

# ── Dataset Split ────────────────────────────────────────────────────────
TRAIN_SPLIT = 0.8
VALIDATION_SPLIT = 0.2
SPLIT_SEED = 42

# ── Out-of-Distribution / Unknown Detection ─────────────────────────────
# The classifier is closed-set: softmax always picks one of NUM_CLASSES
# even on an image of something it never trained on (a new wound type,
# a new infection presentation, or a non-wound photo). Below this
# max-softmax confidence, we refuse to commit to a class and instead
# flag the case as "Unknown — refer for manual review" so a doctor sees
# it, rather than silently returning a wrong label with a confident-
# looking number attached. Tune on a held-out validation set: lower it
# if too many real cases get flagged Unknown, raise it if wrong labels
# are getting through with high confidence.
OOD_CONFIDENCE_THRESHOLD = 0.55
# Temperature-scaling divisor applied to logits before softmax (>1 softens an
# over-confident model; fit it on held-out data, e.g. with
# `python -m scripts.evaluate_global_model`, which reports a suggestion).
INFERENCE_TEMPERATURE = float(os.getenv("INFERENCE_TEMPERATURE", "1.0"))
# Average predictions over the image and its horizontal mirror (2x cost).
if INFERENCE_TEMPERATURE <= 0:
    raise ValueError("INFERENCE_TEMPERATURE must be positive.")
INFERENCE_TTA = os.getenv("INFERENCE_TTA", "false").lower() == "true"
# How many ranked candidate classes /api/predict returns.
TOP_K_PREDICTIONS = 3

# ── Differential Privacy (Opacus) ────────────────────────────────────────
USE_DIFFERENTIAL_PRIVACY = True
DP_EPSILON = 3.0
DP_DELTA = 1e-5
DP_MAX_GRAD_NORM = 1.0
# Smallest local dataset a node may train on with DP enabled.
DP_MIN_TRAIN_SAMPLES = int(os.getenv("DP_MIN_TRAIN_SAMPLES", "8"))
# Lifetime epsilon a node may spend across all federated rounds (each round
# costs up to DP_EPSILON). 0 disables enforcement. See PrivacyBudget.
DP_TOTAL_EPSILON_BUDGET = float(os.getenv("DP_TOTAL_EPSILON_BUDGET", "100"))

# ── Security ─────────────────────────────────────────────────────────────
# Never fall back to a fixed, source-controlled string here: a hardcoded
# secret lets anyone who has read the code forge valid tokens for any
# account. If JWT_SECRET isn't set, generate a random one for this process
# instead — sessions won't survive a restart, but tokens can't be forged.
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    JWT_SECRET = secrets.token_hex(32)
    _logger.warning(
        "JWT_SECRET is not set — using a randomly generated, process-local "
        "secret. All issued tokens will be invalidated on restart. Set the "
        "JWT_SECRET environment variable for a stable, production deployment."
    )
JWT_ALGORITHM = "HS256"

# ── Email (verification / notifications) ──────────────────────────────────
# All optional: if SMTP_HOST/SMTP_USER/SMTP_PASSWORD aren't set, the app
# runs in "dev mode" for email — it logs the message instead of sending it
# and echoes the verification link back in the API response, so signup
# still works end-to-end with zero configuration.
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_ADDRESS = os.getenv("SMTP_FROM_ADDRESS", SMTP_USER or "no-reply@securederm.local")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() != "false"
EMAIL_SENDING_CONFIGURED = bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
EMAIL_VERIFICATION_TOKEN_TTL_HOURS = 24

# Ensure required directories exist
for _dir in (CHECKPOINTS_DIR, LOGS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)
