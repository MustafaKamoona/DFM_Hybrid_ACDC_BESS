"""Regenerate the data-driven figures of the DFM study from the released CSV files.

Usage (from the repository root):
    python code/generate_figures.py                         # all figures, PDF, into output/figures/
    python code/generate_figures.py Fig_monte_carlo         # selected figures
    python code/generate_figures.py --png --dpi 200         # also write PNG images
    python code/generate_figures.py --list                  # list the available figures

Only plotting is performed: the figures are drawn from the saved results in ``data/``.
No network simulation, optimization or Monte Carlo experiment is executed. Outputs are written
inside the repository (default ``output/figures/``) and never into ``figures/``, which holds
the final figure files of the paper.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib.pyplot as plt  # noqa: E402

from dfm_figures import FIGURES, AUTHOR_ARTWORK, build  # noqa: E402
from dfm_figures.common import REPO_ROOT  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("figures", nargs="*", help="figure names (default: all)")
    parser.add_argument("--out", default="output/figures", help="output folder, relative to the repository root")
    parser.add_argument("--png", action="store_true", help="also write PNG images")
    parser.add_argument("--dpi", type=int, default=200, help="PNG resolution (default: 200)")
    parser.add_argument("--list", action="store_true", help="list the available figures and exit")
    args = parser.parse_args(argv)

    if args.list:
        print("Generated from the released data:\n  " + "\n  ".join(FIGURES))
        print("Author-created artwork (final files in figures/, not generated):\n  " + "\n  ".join(AUTHOR_ARTWORK))
        return 0

    names = args.figures or list(FIGURES)
    unknown = [n for n in names if n not in FIGURES]
    if unknown:
        parser.error(f"unknown or non-generated figure(s): {', '.join(unknown)} (see --list)")

    out = (REPO_ROOT / args.out).resolve()
    if REPO_ROOT not in out.parents or out == (REPO_ROOT / "figures").resolve():
        parser.error("the output folder must lie inside the repository and must not be figures/")
    out.mkdir(parents=True, exist_ok=True)

    for name in names:
        fig = build(name)
        fig.savefig(out / f"{name}.pdf", format="pdf", bbox_inches="tight")
        if args.png:
            fig.savefig(out / f"{name}.png", dpi=args.dpi, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        print(f"{name}: written to {out.relative_to(REPO_ROOT).as_posix()}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
