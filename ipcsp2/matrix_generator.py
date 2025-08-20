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

# Shannon radii for common elements (in Angstroms)
SHANNON_RADII = {
    'H': 0.31, 'He': 0.28, 'Li': 0.76, 'Be': 0.45, 'B': 0.27, 'C': 0.16, 'N': 1.46, 'O': 1.35, 'F': 1.33, 'Ne': 1.12,
    'Na': 1.02, 'Mg': 0.72, 'Al': 0.54, 'Si': 0.40, 'P': 0.44, 'S': 1.84, 'Cl': 1.81, 'Ar': 1.54,
    'K': 1.38, 'Ca': 1.00, 'Sc': 0.75, 'Ti': 0.42, 'V': 0.59, 'Cr': 0.44, 'Mn': 0.46, 'Fe': 0.49, 'Co': 0.42, 'Ni': 0.48, 'Cu': 0.46, 'Zn': 0.60,
    'Ga': 0.47, 'Ge': 0.39, 'As': 0.58, 'Se': 1.98, 'Br': 1.96, 'Kr': 1.69,
    'Rb': 1.52, 'Sr': 1.18, 'Y': 0.90, 'Zr': 0.72, 'Nb': 0.64, 'Mo': 0.59, 'Tc': 0.56, 'Ru': 0.53, 'Rh': 0.50, 'Pd': 0.50, 'Ag': 0.59, 'Cd': 0.78,
    'In': 0.62, 'Sn': 0.55, 'Sb': 0.76, 'Te': 2.21, 'I': 2.20, 'Xe': 1.90,
    'Cs': 1.67, 'Ba': 1.35, 'La': 1.03, 'Ce': 1.01, 'Pr': 0.99, 'Nd': 0.98, 'Pm': 0.97, 'Sm': 0.96, 'Eu': 0.95, 'Gd': 0.94, 'Tb': 0.92, 'Dy': 0.91, 'Ho': 0.90, 'Er': 0.89, 'Tm': 0.88, 'Yb': 0.87, 'Lu': 0.86,
    'Hf': 0.71, 'Ta': 0.64, 'W': 0.60, 'Re': 0.56, 'Os': 0.54, 'Ir': 0.51, 'Pt': 0.50, 'Au': 0.51, 'Hg': 0.69, 'Tl': 0.62, 'Pb': 0.55, 'Bi': 0.76, 'Po': 1.67, 'At': 1.50, 'Rn': 1.45
}

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

        # Check if phase directory exists
        phase_dir = os.path.join(".", self.filedir / phase_name)
        if os.path.exists(phase_dir) and os.path.exists(os.path.join(phase_dir, 'radii.lib')):
            # Use existing radii.lib file
            with open(os.path.join(phase_dir, 'radii.lib'), 'r') as f:
                for line in f.readlines():
                    if line.startswith('#'):
                        continue
                    line = line.rstrip('\n')
                    line = line.split()
                    self.types.append(line[0])
                    self.radius[line[0]] = float(line[1])
            print('Radii', self.radius)
        else:
            # Auto-generate radii for any composition using Shannon radii
            print(f"Phase directory for '{phase_name}' not found. Auto-generating radii from Shannon radii.")
            self._auto_generate_radii(phase_name)
            print('Auto-generated radii', self.radius)

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

    def _auto_generate_radii(self, phase_name):
        """
        Auto-generate radii for any composition using Shannon radii.
        This allows the system to work with any chemical composition.
        """
        # Extract elements from phase name (simple approach)
        # For more complex cases, we could pass the ions_count directly
        elements = []
        
        # Try to extract elements from phase name (e.g., "NaCl" -> ["Na", "Cl"])
        i = 0
        while i < len(phase_name):
            if phase_name[i].isupper():
                element = phase_name[i]
                i += 1
                while i < len(phase_name) and phase_name[i].islower():
                    element += phase_name[i]
                    i += 1
                elements.append(element)
            else:
                i += 1
        
        # If no elements found, try common patterns
        if not elements:
            if phase_name == 'NaCl':
                elements = ['Na', 'Cl']
            elif phase_name == 'KCl':
                elements = ['K', 'Cl']
            elif phase_name == 'LiF':
                elements = ['Li', 'F']
            elif phase_name == 'MgO':
                elements = ['Mg', 'O']
            elif phase_name == 'CaO':
                elements = ['Ca', 'O']
            elif phase_name == 'TiO2':
                elements = ['Ti', 'O']
            elif phase_name == 'SiO2':
                elements = ['Si', 'O']
            elif phase_name == 'Al2O3':
                elements = ['Al', 'O']
            else:
                # Default fallback - try to extract any known elements
                for element in SHANNON_RADII.keys():
                    if element in phase_name:
                        elements.append(element)
        
        # Generate radii for found elements
        for element in elements:
            if element in SHANNON_RADII:
                self.types.append(element)
                self.radius[element] = SHANNON_RADII[element]
            else:
                print(f"Warning: No Shannon radius found for element {element}, using default value of 1.0")
                self.types.append(element)
                self.radius[element] = 1.0

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