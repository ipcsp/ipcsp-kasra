import os
import numpy as np
from scipy.interpolate import interp1d
import ase
from ase.geometry import get_distances

class SPP:
    """
    Represents a single Statistically Derived Proxy Potential (SPP) for a given atom pair.
    Provides interpolation for U(r) values.
    """
    def __init__(self, r_grid, U_grid):
        """
        Initialize the SPP with a grid of distances and corresponding potential values.
        Args:
            r_grid (np.ndarray): Array of distances (Angstrom).
            U_grid (np.ndarray): Array of SPP values at those distances.
        """
        self.r_grid = r_grid
        self.U_grid = U_grid
        # Create an interpolation function for the potential
        self.interp = interp1d(r_grid, U_grid, kind='cubic', bounds_error=False, fill_value=np.max(U_grid))

    def __call__(self, r):
        """
        Evaluate the SPP at a given distance r (Angstrom).
        Args:
            r (float): Distance between two atoms.
        Returns:
            float: SPP value at distance r.
        """
        return self.interp(r)

class SPPCollection:
    """
    Loads and manages a collection of SPPs for all relevant atom pairs.
    Provides scoring for atomic structures using the SPP potentials.
    """
    def __init__(self, spp_dir):
        """
        Args:
            spp_dir (str): Path to the directory containing SPP .POT files.
        """
        self.spp_dir = spp_dir
        self.spps = {}  # Dictionary to store SPP objects for each atom pair

    def load(self, pairs):
        """
        Load SPPs for all unique pairs in the provided set.
        Args:
            pairs (Iterable[Tuple[str, str]]): Atom type pairs to load SPPs for.
        Raises:
            FileNotFoundError: If a required SPP .POT file is missing.
        """
        for pair in pairs:
            a, b = pair
            # Always sort the pair alphabetically for consistency
            key = tuple(sorted([a, b]))
            if key in self.spps:
                continue  # Already loaded
            # Build the folder and file name for the SPP .POT file
            folder = f"{a.upper()}-{b.upper()}"
            pot_file_1 = os.path.join(self.spp_dir, folder, f"{a.upper()}-{b.upper()}.POT")
            pot_file_2 = os.path.join(self.spp_dir, folder, f"{b.upper()}-{a.upper()}.POT")
            # Try both possible file name orders
            if os.path.exists(pot_file_1):
                pot_file = pot_file_1
            elif os.path.exists(pot_file_2):
                pot_file = pot_file_2
            else:
                raise FileNotFoundError(f"SPP .POT file not found for pair {a}-{b} in {self.spp_dir}")
            # Read the .POT file to get r and U(r)
            r_grid, U_grid = self._read_pot(pot_file)
            # Create an SPP object and store it in the dictionary
            self.spps[key] = SPP(r_grid, U_grid)

    @staticmethod
    def _read_pot(filename):
        """
        Read an SPP .POT file and return r and U(r) arrays.
        Args:
            filename (str): Path to the .POT file.
        Returns:
            Tuple[np.ndarray, np.ndarray]: r_grid, U_grid
        """
        data = []
        with open(filename, 'r') as f:
            for line in f:
                # Ignore lines that are not data (e.g., headers, comments)
                line = line.strip()
                if line == '':
                    continue
                if line.lower().startswith('spline'):
                    continue
                if line[0].isalpha():
                    continue
                # Split the line into parts and convert to floats
                parts = line.split()
                if len(parts) == 2:
                    r_value = float(parts[0])
                    U_value = float(parts[1])
                    data.append([r_value, U_value])
        # Convert the data list to numpy arrays
        data = np.array(data)
        r_grid = data[:, 0]
        U_grid = data[:, 1]
        return r_grid, U_grid

    def get(self, a, b):
        """
        Retrieve the SPP object for a given atom pair.
        Args:
            a (str): Atom type 1
            b (str): Atom type 2
        Returns:
            SPP: The SPP object for the pair
        """
        key = tuple(sorted([a, b]))
        return self.spps[key]

    def score(self, symbols, positions, cell, pbc=True):
        """
        Compute the total SPP score for a structure.
        Args:
            symbols (List[str]): List of atom symbols (e.g., ['O', 'Sr', 'Ti', ...])
            positions (np.ndarray): Nx3 array of atomic positions
            cell (np.ndarray): 3x3 cell matrix
            pbc (bool): Whether to use periodic boundary conditions
        Returns:
            float: The total SPP score (lower is more stable/likely)
        """
        spp_score = 0.0
        n_atoms = len(symbols)
        # Loop over all unique pairs of atoms
        for i in range(n_atoms):
            for j in range(i+1, n_atoms):
                atom1 = symbols[i]
                atom2 = symbols[j]
                pair = tuple(sorted([atom1, atom2]))
                # Get the SPP object for this pair
                spp = self.spps.get(pair)
                if spp is None:
                    # If no SPP is found for this pair, skip it
                    continue
                # Compute the distance between atom i and atom j
                # get_distances returns a tuple, we want the scalar distance
                distance = get_distances(positions[i], positions[j], cell, pbc=pbc)[1][0][0]
                # Add the SPP value for this distance to the total score
                spp_score += spp(distance)
        return spp_score


def compute_spp_objective(atoms, spp):
    """
    Compute the SPP objective for a given ASE Atoms object and SPPCollection.
    Args:
        atoms (ase.Atoms): The structure to score.
        spp (SPPCollection): The loaded SPP potentials.
    Returns:
        float: The total SPP score for the structure.
    """
    # Get the chemical symbols, positions, and cell from the Atoms object
    symbols = atoms.get_chemical_symbols()
    positions = atoms.get_positions()
    cell = atoms.get_cell()
    # Compute the SPP score using the SPPCollection
    score = spp.score(symbols, positions, cell, pbc=True)
    return score 