import torch
from ase.spacegroup import crystal
from ase.io import write

from typing import List
import io


def make_cif(
    rho: torch.FloatTensor,
    x: torch.FloatTensor,
    z: torch.LongTensor,
    num_atoms: torch.LongTensor,
) -> List[str]:
    n_struct = num_atoms.shape[0]

    batch = torch.arange(num_atoms.shape[0], device=num_atoms.device).repeat_interleave(
        num_atoms
    )

    crystals = [
        crystal(
            z[batch == i].cpu(),
            x[batch == i].cpu(),
            cellpar=rho[0][i].cpu().tolist() + rho[1][i].cpu().tolist(),
        )
        for i in range(n_struct)
    ]

    buf = io.BytesIO()
    write(buf, crystals, format="cif")
    buf.seek(0)
    cif = buf.read().decode()
    buf.close()

    return cif
