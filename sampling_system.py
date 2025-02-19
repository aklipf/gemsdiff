import torch
from torch_geometric.loader import DataLoader

import tqdm

import os

from src.utils.scaler import LatticeScaler
from src.utils.data.system import SystemDataset
from src.utils.hparams import Hparams
from src.model.gemsnet import GemsNetDiffusion
from src.utils.cif import make_cif

if __name__ == "__main__":
    import argparse

    from torch.utils.tensorboard import SummaryWriter

    parser = argparse.ArgumentParser(description="train denoising model")
    parser.add_argument("system")
    parser.add_argument("--checkpoint", "-c")
    parser.add_argument("--output", "-o", default="sampling.cif")
    parser.add_argument("--device", "-d", default="cuda")
    parser.add_argument("--threads", "-t", type=int, default=8)

    args = parser.parse_args()

    torch.set_num_threads(args.threads)
    torch.set_num_interop_threads(args.threads)

    # basic setup
    device = args.device

    hparams = Hparams()
    hparams.from_json(os.path.join(args.checkpoint, "hparams.json"))

    dataset = SystemDataset(args.system.split("-"))
    loader = DataLoader(dataset, batch_size=128, num_workers=0)

    scaler = LatticeScaler().to(device)

    model = GemsNetDiffusion(
        lattice_scaler=scaler,
        features=hparams.features,
        knn=hparams.knn,
        num_blocks=hparams.layers,
        diffusion_steps=hparams.diffusion_steps,
        x_betas=hparams.x_betas,
    ).to(device)

    model.load_state_dict(
        torch.load(
            os.path.join(args.checkpoint, "best.pt"), map_location=torch.device(device)
        ),
        strict=False,
    )
    model.eval()

    with torch.no_grad():
        rho, x, z, num_atoms = [], [], [], []
        for idx, batch in enumerate(tqdm.tqdm(loader)):
            batch = batch.to(device)

            pred_rho, pred_x = model.sampling(batch.z, batch.num_atoms, verbose=True)

            rho.append(pred_rho)
            x.append(pred_x)
            z.append(batch.z)
            num_atoms.append(batch.num_atoms)

        cat_rho, cat_x, cat_z, cat_num_atoms = (
            torch.cat(rho, dim=0),
            torch.cat(x, dim=0),
            torch.cat(z, dim=0),
            torch.cat(num_atoms, dim=0),
        )
        cif = make_cif(cat_rho, cat_x, cat_z, cat_num_atoms)
        with open(args.output, "w") as fp:
            fp.write(cif)
