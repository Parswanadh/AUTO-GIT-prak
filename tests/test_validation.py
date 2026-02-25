#!/usr/bin/env python3
"""
Test the validation system with the broken DPNN code.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.validation.syntax_validator import SyntaxValidator
from src.utils.validation.import_validator import ImportValidator
from src.utils.validation.execution_sandbox import ExecutionSandbox


# The broken DPNN code we generated earlier
BROKEN_CODE = {
    "model.py": '''import torch
from torch import nn
from torch_geometric.nn import GCNConv
import pytorch_lightning as pl
from typing import Tuple, Dict, Any

class DynamicPlasticityController(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, plasticity_strength: float = 0.1):
        super().__init__()
        self.conv = GCNConv(in_channels, out_channels)
        self.plasticity_strength = plasticity_strength

    def forward(self, data: Dict[str, torch.Tensor]) -> Tuple[torch.Tensor, torch.Tensor]:
        x, edge_index = data['x'], data['edge_index']
        z = self.conv(x, edge_index)
        plasticity_score = nn.functional.softmax(z, dim=1)  # Softmax to get probabilities for pruning/growing
        return plasticity_score, z

    def update_connections(self, plasticity_scores: torch.Tensor):
        # Simple thresholding for demonstration; in practice, more sophisticated rules might be used
        mask = (plasticity_scores > self.plasticity_strength).float()
        return self.conv.weight * mask

class TaskEncoder(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int, output_dim: int):
        super().__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, output_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = torch.relu(self.fc1(x))
        return self.fc2(x)

class DPNN(pl.LightningModule):
    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.save_hyperparameters()
        # Base Network (simplified for demonstration purposes)
        self.base_network = nn.Sequential(
            nn.Conv2d(1, 32, kernel_size=3),
            nn.ReLU(),
            nn.Flatten(),
            nn.Linear(32*6*6, 128),
            nn.ReLU()
        )
        self.plasticity_controller = DynamicPlasticityController(in_channels=128, out_channels=10)
        self.task_encoder = TaskEncoder(input_dim=10, hidden_dim=64, output_dim=32)

    def forward(self, data: Dict[str, torch.Tensor]) -> Tuple[torch.Tensor, torch.Tensor]:
        x, edge_index = data['x'], data['edge_index']
        x = self.base_network(x)
        plasticity_scores, z = self.plasticity_controller({
            'x': x,
            'edge_index': edge_index
        })
        updated_weights = self.plasticity_controller.update_connections(plasticity_scores)
        return updated_weights, z

    def training_step(self, batch: Tuple[torch.Tensor, Dict], batch_idx: int):
        inputs, data = batch
        updated_weights, task_features = self(data)
        # Placeholder for actual loss computation and backpropagation
        loss = self._compute_loss(inputs, updated_weights, task_features)
        self.log('train_loss', loss)
        return loss

    def configure_optimizers(self):
        optimizer = torch.optim.Adam(self.parameters(), lr=self.hparams['learning_rate'])
        scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=10, gamma=0.9)
        return [optimizer], [scheduler]

    def _compute_loss(self, inputs: torch.Tensor, updated_weights: torch.Tensor, task_features: torch.Tensor):
        # Placeholder for actual loss computation
        prediction = self.task_encoder(task_features)
        return nn.functional.mse_loss(prediction, inputs)  # Simplified MSE loss for demonstration

# Example usage
if __name__ == "__main__":
    config = {
        'learning_rate': 0.001,
        'plasticity_strength': 0.5,
        # Other hyperparameters and network parameters would be defined here
    }
    model = DPNN(config)
    data = {'x': torch.randn(32, 128), 'edge_index': torch.randint(0, 32, (2, 64))}
    updated_weights, task_features = model(data)
''',
    "train.py": '''import argparse
import yaml
from model import DPNN
import torch
from torch_geometric.data import Data
from torch_geometric.loader import DataLoader
import gymnasium as gym
import pytorch_lightning as pl

def load_config(path: str):
    with open(path, 'r') as file:
        return yaml.safe_load(file)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, required=True, help='Path to the config file.')
    args = parser.parse_args()

    config = load_config(args.config)
    model = DPNN(config)
    model.hparams.update(config)  # Ensure all hyperparameters are set from config

    # Setup environment and dataloader (simplified for demonstration)
    env = gym.make('CartPole-v1')
    dataset = [Data(x=torch.randn(128), edge_index=torch.randint(0, 128, (2, 64))) for _ in range(100)]
    dataloader = DataLoader(dataset, batch_size=32, shuffle=True)

    trainer = pl.Trainer(**config['trainer'])  # Assuming PyTorch Lightning Trainer setup is defined in config
    trainer.fit(model, dataloader)

if __name__ == "__main__":
    main()
''',
    "config.yaml": '''trainer:
  max_epochs: 100
  gpus: 1
learning_rate: 0.001
plasticity_strength: 0.5
# Other hyperparameters would be defined here
'''
}


def test_syntax_validator():
    """Test syntax validation."""
    print("\n" + "="*60)
    print("TEST 1: Syntax Validator")
    print("="*60)

    validator = SyntaxValidator()

    for filename, code in BROKEN_CODE.items():
        if filename.endswith('.py'):
            print(f"\n[VALIDATE] {filename}")
            result = validator.validate(code, filename)

            print(f"  Valid: {result.is_valid}")
            print(f"  Errors: {len(result.errors)}")
            print(f"  Warnings: {len(result.warnings)}")

            if result.errors:
                for error in result.errors:
                    print(f"    - {error}")


def test_import_validator():
    """Test import validation."""
    print("\n" + "="*60)
    print("TEST 2: Import Validator")
    print("="*60)

    validator = ImportValidator()

    for filename, code in BROKEN_CODE.items():
        if filename.endswith('.py'):
            print(f"\n[VALIDATE] {filename}")
            result = validator.validate(
                code=code,
                file_name=filename,
                available_files=BROKEN_CODE
            )

            print(f"  Valid: {result.is_valid}")
            print(f"  Errors: {len(result.errors)}")

            if result.errors:
                for error in result.errors:
                    print(f"    - {error}")
                    if error.suggestion:
                        print(f"      Suggestion: {error.suggestion}")


def test_execution_sandbox():
    """Test execution sandbox."""
    print("\n" + "="*60)
    print("TEST 3: Execution Sandbox (import test only)")
    print("="*60)

    sandbox = ExecutionSandbox(timeout=10)

    print("\n[EXECUTE] Attempting to import the modules...")
    result = sandbox.execute(BROKEN_CODE)

    print(f"  Success: {result.success}")
    print(f"  Timeout: {result.timeout}")
    print(f"  Duration: {result.duration:.2f}s")

    if result.output:
        print(f"\n  Output:\n{result.output[:200]}")

    if result.error:
        print(f"\n  Error:\n{result.error[:500]}")


async def test_full_validation():
    """Test full validation with orchestrator."""
    print("\n" + "="*60)
    print("TEST 4: Full Validation with Orchestrator")
    print("="*60)

    from src.utils.validation.orchestrator import ValidationOrchestrator

    orchestrator = ValidationOrchestrator(
        enable_execution=False,  # Skip execution to avoid dependency issues
        auto_fix=False  # Don't auto-fix for this test
    )

    print("\n[VALIDATE] Running full validation...")
    result = await orchestrator.validate_and_fix(
        code_files=BROKEN_CODE,
        solution="DPNN test"
    )

    report = result["validation_report"]

    print(f"\n  Total Files: {report.total_files}")
    print(f"  Total Errors: {report.total_errors}")
    print(f"  Total Warnings: {report.total_warnings}")
    print(f"  Files with Errors: {report.files_with_errors}")

    print(f"\n{orchestrator.validate_report_summary(report)}")


if __name__ == "__main__":
    print("="*60)
    print("AUTO-GIT Validation System Test")
    print("Testing with broken DPNN code")
    print("="*60)

    # Run tests
    test_syntax_validator()
    test_import_validator()
    test_execution_sandbox()

    # Run async test
    asyncio.run(test_full_validation())

    print("\n" + "="*60)
    print("Tests completed!")
    print("="*60)
