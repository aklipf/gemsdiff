import torch
from torch_scatter import scatter_mean

from typing import Dict

from src.utils.scaler import LatticeScaler


@torch.no_grad()
def get_metrics(
    rho: torch.FloatTensor,
    rho_prime: torch.FloatTensor,
    x: torch.FloatTensor,
    x_prime: torch.FloatTensor,
    num_atoms: torch.LongTensor,
    by_structure: bool = False,
) -> Dict[str, torch.FloatTensor]:
    rho = rho.cpu()
    rho_prime = rho_prime.cpu()
    x = x.cpu() % 1.0
    x_prime = x_prime.cpu() % 1.0
    num_atoms = num_atoms.cpu()

    offset = torch.tensor(
        [
            [-1, -1, -1],
            [-1, -1, 0],
            [-1, -1, 1],
            [-1, 0, -1],
            [-1, 0, 0],
            [-1, 0, 1],
            [-1, 1, -1],
            [-1, 1, 0],
            [-1, 1, 1],
            [0, -1, -1],
            [0, -1, 0],
            [0, -1, 1],
            [0, 0, -1],
            [0, 0, 0],
            [0, 0, 1],
            [0, 1, -1],
            [0, 1, 0],
            [0, 1, 1],
            [1, -1, -1],
            [1, -1, 0],
            [1, -1, 1],
            [1, 0, -1],
            [1, 0, 0],
            [1, 0, 1],
            [1, 1, -1],
            [1, 1, 0],
            [1, 1, 1],
        ]
    )

    struct_idx = torch.arange(rho.shape[0], device=rho.device)
    batch = struct_idx.repeat_interleave(num_atoms)

    euc_x_prime = torch.einsum(rho[batch], [0, 1, 2], x_prime, [0, 2], [0, 1])

    euc_x = torch.einsum(
        rho[batch],
        [0, 2, 3],
        x[:, None, :] + offset[None, :, :],
        [0, 1, 3],
        [0, 1, 2],
    )

    min_idx = (euc_x_prime[:, None] - euc_x).norm(dim=2).argmin(dim=1)

    error_pos = (x_prime - (x + offset[min_idx])).norm(dim=1)
    if by_structure:
        mae_pos = scatter_mean(
            error_pos, batch, dim=0, dim_size=num_atoms.shape[0]
        ).detach()
    else:
        mae_pos = error_pos.mean().detach()

    rho_lengths, rho_angles = LatticeScaler.get_lattices_parameters(rho)
    rho_prime_lengths, rho_prime_angles = LatticeScaler.get_lattices_parameters(
        rho_prime
    )

    error_lengths = (rho_lengths - rho_prime_lengths).abs()
    error_angles = (rho_angles - rho_prime_angles).abs()
    if by_structure:
        mae_lengths = error_lengths.detach()
        mae_angles = error_angles.detach()
    else:
        mae_lengths = error_lengths.mean().detach()
        mae_angles = error_angles.mean().detach()

    return {
        "mae_pos": mae_pos,
        "mae_lengths": mae_lengths,
        "mae_angles": mae_angles,
    }
