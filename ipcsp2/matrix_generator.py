"""
Phase class for reading atomic radii and closest distances.
This file has been cleaned up to remove all classical potential generation
in favor of Statistical Proxy Potentials (SPPs).

The Phase class is maintained for compatibility with existing code
but only reads radii.lib and dist.lib files.
"""

# this file is full of file path hacks, fix it at some point

import numpy as np
import os

from ipcsp2 import root_dir
from ipcsp2.grids_and_symmetry import cubic
import math
from numba import njit

filedir = root_dir / 'data/'


class Phase:
    filedir = root_dir / 'data/'

    def __init__(self, phase_name):

        self.types = []

        self.radius = {}

        self.closest_distance = {}  # dict['O', 'O'] = 2.2 A

        self.charge = {}

        self.buck = {}

        self.name = phase_name

        self.location = self.filedir / phase_name

        self.garnet = False  # HACK:garnet case is treated separately

        with open(os.path.join(".", self.filedir / phase_name / 'radii.lib'), 'r') as f:
            for line in f.readlines():
                if line.startswith('#'):
                    continue
                line = line.rstrip('\n')
                line = line.split()
                self.types.append(line[0])
                self.radius[line[0]] = float(line[1])
        print('Radii', self.radius)

        try:
            with open(os.path.join(".", self.filedir / phase_name / 'dist.lib'), 'r') as f:
                for line in f.readlines():
                    if line.startswith('#'):
                        continue
                    line = line.rstrip('\n')
                    line = line.split()
                    pair = (min(line[0], line[1]), max(line[0], line[1]))
                    self.closest_distance[pair] = float(line[2])
            print('Overriding Shannon radii with the following closest distances:', self.closest_distance)
        except IOError:
            print("No closest distances between the ions were provided")
            print("Relying on Shannon radii only")

        # Note: Buckingham potential parsing removed - only SPPs are used now
        self.charge = {}
        self.buck = {}
        self.garnet = False

    def __str__(self):
        return str(self.__class__) + ": " + str(self.__dict__)


@njit(cache=True)
def QEwald(positions, vecs, reciprocal, cell_volume, alpha=-1):
    """
    positions are relative coordinates
    vecs are the lattice vectors
    reciprocal are the reciprocal lattice vectors. I need them only to use numba, since it doesn't support cross product
    cell_volume is the volume of the cell
    alpha controls the split between the direct and reciprocal sums

    You can tweak realDepth and reciprocalDepth summation constant below in the code
    """
    N = len(positions)
    if alpha < 0:
        alpha = 2 / (cell_volume ** (1.0 / 3))
    realDepth = 4  # 3
    reciprocalDepth = 4  # 3

    pos = positions @ vecs

    d = np.zeros((N, N))

    shifts = np.zeros(((2 * realDepth + 1) ** 3 - 1, 3))
    i = 0
    tmp = np.array([realDepth, realDepth, realDepth])

    for shift in np.ndindex(2 * realDepth + 1, 2 * realDepth + 1, 2 * realDepth + 1):
        if shift != (realDepth, realDepth, realDepth):
            shifts[i,] = shift
            shifts[i,] = shifts[i,] - tmp
            i = i + 1

    shifts = shifts @ vecs

    for i in np.arange(N):
        for j in np.arange(i, N):
            if i != j:
                r = np.linalg.norm(pos[i,] - pos[j,])
                d[i, j] += math.erfc(alpha * r) / (2 * r)

            for s in np.arange(len(shifts)):
                r = np.linalg.norm(pos[i,] + shifts[s,] - pos[j,])
                d[i, j] += math.erfc(alpha * r) / (2 * r)

    # self interaction term
    for i in np.arange(N):
        d[i, i] = d[i, i] - alpha / math.sqrt(math.pi)

    # Ewald reciprocal space

    shifts_recip = np.zeros(((2 * reciprocalDepth + 1) ** 3 - 1, 3))
    i = 0
    tmp = np.array([reciprocalDepth, reciprocalDepth, reciprocalDepth])

    for shift_recip in np.ndindex(2 * reciprocalDepth + 1, 2 * reciprocalDepth + 1, 2 * reciprocalDepth + 1):
        if shift_recip != (reciprocalDepth, reciprocalDepth, reciprocalDepth):
            shifts_recip[i,] = shift_recip
            shifts_recip[i,] = shifts_recip[i,] - tmp
            i = i + 1

    shifts_recip = shifts_recip @ reciprocal

    for i in np.arange(N):
        for j in np.arange(i, N):

            for s in np.arange(len(shifts_recip)):
                k = shifts_recip[s,]
                # k = np.array(shift)@self.reciprocal
                term = (4 * math.pi ** 2) / np.dot(k, k)
                term = term * math.exp(-np.dot(k, k) / (4 * alpha ** 2))
                v = pos[j,] - pos[i,]
                term = term * math.cos(np.dot(k, v))
                d[i, j] += term / (2 * math.pi * cell_volume)

    # Unit conversion
    d = d * 14.399645351950543

    # symmetry completion
    for i in np.arange(N):
        for j in np.arange(i):
            d[i, j] = d[j, i]

    return d























if __name__ == "__main__":
    # This file now only contains the Phase class for reading radii and distances
    # All potential generation has been removed in favor of SPPs
    pass