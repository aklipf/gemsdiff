import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch_geometric.loader import DataLoader
from torch_scatter import scatter_mean
import pandas as pd
import tqdm

import matplotlib.pyplot as plt
from ase.visualize.plot import plot_atoms
from ase.io import write
from ase.spacegroup import crystal

import os
import json
import math
import random
import datetime

from src.utils.scaler import LatticeScaler
from src.utils.data import MP20, Carbon24, Perov5
from src.utils.hparams import Hparams
from src.utils.metrics import get_metrics
from src.model.gemsnet import GemsNetDiffusion
from src.utils.video import make_video
from src.utils.cif import make_cif
from src.loss import OptimalTrajLoss, LatticeParametersLoss


def get_dataloader(path: str, dataset: str, batch_size: int):
    assert dataset in ["mp-20", "carbon-24", "perov-5"]

    dataset_path = os.path.join(path, dataset)
    if dataset == "mp-20":
        test_set = MP20(dataset_path, "test")
    elif dataset == "carbon-24":
        test_set = Carbon24(dataset_path, "test")
    elif dataset == "perov-5":
        test_set = Perov5(dataset_path, "test")

    loader_test = DataLoader(
        test_set, batch_size=batch_size, shuffle=True, num_workers=4
    )

    return loader_test


if __name__ == "__main__":
    import argparse

    from torch.utils.tensorboard import SummaryWriter

    parser = argparse.ArgumentParser(description="train denoising model")
    parser.add_argument("--checkpoint", "-c")
    parser.add_argument("--output", "-o", default="sampling.cif")
    parser.add_argument("--dataset", "-D", default="mp-20")
    parser.add_argument("--dataset-path", "-dp", default="./data")
    parser.add_argument("--device", "-d", default="cuda")
    parser.add_argument("--threads", "-t", type=int, default=8)

    args = parser.parse_args()

    torch.set_num_threads(args.threads)
    torch.set_num_interop_threads(args.threads)

    # basic setup
    device = args.device

    hparams = Hparams()
    hparams.from_json(os.path.join(args.checkpoint, "hparams.json"))

    loader_test = get_dataloader(args.dataset_path, args.dataset, 512)

    scaler = LatticeScaler().to(device)

    model = GemsNetDiffusion(
        lattice_scaler=scaler,
        features=hparams.features,
        knn=hparams.knn,
        num_blocks=hparams.layers,
        vector_fields=hparams.vector_fields,
        diffusion_steps=hparams.diffusion_steps,
    ).to(device)

    model.load_state_dict(torch.load(os.path.join(args.checkpoint, "best.pt")))
    model.eval()

    with torch.no_grad():
        rho, x, z, num_atoms = [], [], [], []
        for idx, batch in enumerate(tqdm.tqdm(loader_test)):
            batch = batch.to(device)

            for _ in range(3):
                try:
                    pred_rho, pred_x = model.sampling(
                        batch.z, batch.num_atoms, verbose=True
                    )
                except:
                    print("generation fail, restart!")
                    continue
                break
            else:
                raise Exception("fail to sample a batch after 3 attempts")

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
