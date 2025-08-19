import gurobipy as gb
import numpy as np
import os

from ipcsp2 import root_dir
from ipcsp2.matrix_generator import Phase
import ase
from ipcsp2.grids_and_symmetry import cubic
import json
from ipcsp2.lp_to_bqm import BQM
from ipcsp2.spp import SPPCollection

griddir = root_dir / 'data/grids/'

class Allocate:
    """
    Handles the integer programming atom allocation problem for crystal structure prediction.
    Responsible for building the Gurobi model, converting solutions to ASE Atoms objects,
    and running optimization with SPP-based or physical objectives.
    """
    def __init__(self, ions_count, grid_size, cell_size, phase):
        """
        Initialize the allocation problem with the given parameters.
        Args:
            ions_count (dict): e.g., {'O': 3, 'Sr': 1, 'Ti': 1}
            grid_size (int or list): Number of grid points per cell edge (int for cubic, list for orthorhombic)
            cell_size (float or dict): Cell parameters (float for cubic, dict for orthorhombic)
            phase (Phase): Phase object with chemistry and parameters
        """
        self.ions = ions_count
        self.phase = phase
        self.grid = grid_size
        self.cell = cell_size
        self.model = None
        
        # Handle different cell parameter formats
        if isinstance(cell_size, dict):
            # Orthorhombic or custom cell
            self.cell_a = cell_size['a']
            self.cell_b = cell_size['b']
            self.cell_c = cell_size['c']
            self.cell_alpha = cell_size.get('alpha', 90.0)
            self.cell_beta = cell_size.get('beta', 90.0)
            self.cell_gamma = cell_size.get('gamma', 90.0)
            self.cell_type = cell_size.get('type', 'custom')
        else:
            # Cubic cell (backward compatibility)
            self.cell_a = self.cell_b = self.cell_c = cell_size
            self.cell_alpha = self.cell_beta = self.cell_gamma = 90.0
            self.cell_type = 'cubic'
        
        # Handle different grid parameter formats
        if isinstance(grid_size, list):
            # Orthorhombic grid
            self.grid_x, self.grid_y, self.grid_z = grid_size
            self.total_grid_points = self.grid_x * self.grid_y * self.grid_z
        else:
            # Cubic grid (backward compatibility)
            self.grid_x = self.grid_y = self.grid_z = grid_size
            self.total_grid_points = grid_size ** 3

    def __str__(self):
        return str(self.__class__) + ": " + str(self.__dict__)

    def solution_to_Atoms(self, i, orbits):
        """
        Convert a Gurobi solution to an ASE Atoms object, respecting symmetry orbits.
        Args:
            i (int): Solution index
            orbits (dict): Orbit mapping from symmetry file
        Returns:
            ase.Atoms: The atomic structure for solution i
        """
        self.model.params.SolutionNumber = i
        
        # Generate grid positions based on cell type
        if self.cell_type == 'cubic':
            from ipcsp2.grids_and_symmetry import cubic
            grid_positions = cubic(self.grid_x)
        else:
            from ipcsp2.grids_and_symmetry import generate_orthorhombic
            grid_positions = generate_orthorhombic([self.grid_x, self.grid_y, self.grid_z])
        
        symbols = ''
        positions = []
        # Loop through all variables in the Gurobi model
        for v in self.model.getVars():
            if v.Xn == 1:
                t, o = v.varName.split(sep='_')
                o_int = int(o)
                positions.append(grid_positions[o_int])
                symbols += t
                # Handle both string and integer keys in orbits
                orbit_key = o_int if o_int in orbits else str(o_int)
                if orbit_key in orbits:
                    for pos in orbits[orbit_key]:
                        positions.append(grid_positions[pos])
                        symbols += t
        
        # Create cell based on cell type
        if self.cell_type == 'cubic':
            cell = [self.cell_a, self.cell_b, self.cell_c]
        else:
            # For orthorhombic cells, we need to handle angles properly
            # For now, assume orthorhombic (all angles 90°)
            if (abs(self.cell_alpha - 90.0) < 0.1 and 
                abs(self.cell_beta - 90.0) < 0.1 and 
                abs(self.cell_gamma - 90.0) < 0.1):
                cell = [self.cell_a, self.cell_b, self.cell_c]
            else:
                # For non-orthorhombic cells, we need to construct the full cell matrix
                # This is a simplified version - in practice, you'd want to handle this more carefully
                import numpy as np
                alpha_rad = np.radians(self.cell_alpha)
                beta_rad = np.radians(self.cell_beta)
                gamma_rad = np.radians(self.cell_gamma)
                
                # Construct cell matrix (simplified)
                cell = [
                    [self.cell_a, 0, 0],
                    [self.cell_b * np.cos(gamma_rad), self.cell_b * np.sin(gamma_rad), 0],
                    [self.cell_c * np.cos(beta_rad), 
                     self.cell_c * (np.cos(alpha_rad) - np.cos(beta_rad) * np.cos(gamma_rad)) / np.sin(gamma_rad),
                     self.cell_c * np.sqrt(1 - np.cos(alpha_rad)**2 - np.cos(beta_rad)**2 - np.cos(gamma_rad)**2 + 
                                        2*np.cos(alpha_rad)*np.cos(beta_rad)*np.cos(gamma_rad)) / np.sin(gamma_rad)]
                ]
        
        # Create and return an ASE Atoms object
        return ase.Atoms(symbols=symbols, scaled_positions=positions, cell=cell, pbc=True)

    def optimize_cube_symmetry_ase(self, group='1', PoolSolutions=1, TimeLimit=0, verbose=True, spp: SPPCollection = None):
        """
        Generate and solve the integer program for atom allocation with symmetry constraints and SPP-based objective.
        Args:
            group (str): Space group number as string
            PoolSolutions (int): Number of solutions to pool from Gurobi
            TimeLimit (int): Time limit for Gurobi (seconds)
            verbose (bool): Print progress
            spp (SPPCollection): SPP potentials for scoring (required)
        Returns:
            (list[ase.Atoms], float, float): List of solutions, runtime, best objective value
        """
        if spp is None:
            raise ValueError("SPPCollection must be provided for SPP-based optimization.")
        
        N = self.total_grid_points
        T = len(self.ions)
        
        # Load symmetry orbits from JSON file or generate them
        orbit_path = os.path.join(".", griddir / f'CO{self.grid_x}G{group}.json')
        
        # Check if orbit file exists, if not, try to generate orbits
        if not os.path.exists(orbit_path):
            if verbose:
                print(f"Orbit file {orbit_path} not found. Attempting to generate orbits...")
            
            # For orthorhombic grids, we need to generate orbits dynamically
            if self.cell_type != 'cubic':
                from ipcsp2.grids_and_symmetry import generate_orthorhombic_orbits
                orbits = generate_orthorhombic_orbits([self.grid_x, self.grid_y, self.grid_z], group)
            else:
                from ipcsp2.grids_and_symmetry import generate_cubic_orbits
                orbits = generate_cubic_orbits(self.grid_x, group)
        else:
            # Load existing orbit file
            with open(orbit_path, "r") as f:
                orbits = json.load(f)
        
        orb_key = list(orbits.keys())
        if verbose:
            print("Generating integer program\n")
        orb_size = [len(orbits[k]) + 1 for k in orb_key]
        
        # Map each grid position to its orbit index
        o_pos = []
        for i in range(N):
            for orb, pos in orbits.items():
                if int(orb) == i or i in pos:
                    o_pos.append(orb_key.index(orb))
                    break
        
        O = len(orbits)
        types = list(self.ions.keys())
        counts = [self.ions[t] for t in types]
        m = gb.Model(f'Ion allocation in {self.phase.name} with symmetry {group}')
        Vars = [[] for _ in range(T)]
        # Create variables and constraints for each orbit
        for i in range(O):
            tmp_var = []
            for j in range(T):
                Vars[j] += [m.addVar(vtype=gb.GRB.BINARY, name=str(types[j]) + '_' + str(orb_key[i]))]
                tmp_var += [Vars[j][-1]]
            if i == 0:
                # The first orbit must be occupied by exactly one ion
                m.addConstr(gb.LinExpr([1.0] * T, tmp_var) == 1, 'first_orbit_has_ion')
            else:
                # All other orbits can have at most one ion (physically correct)
                m.addConstr(gb.LinExpr([1.0] * T, tmp_var) <= 1, f'one_per_orbit_{i}')
        for j in range(T):
            tmp = gb.LinExpr()
            for i in range(O):
                tmp.add(Vars[j][i], orb_size[i])
            # Enforce the correct number of each ion type
            m.addConstr(tmp == counts[j], f"number_of_ions_type_{j}")
        print("Variables and constraints were generated")
        # --- SPP-based quadratic objective (FIXED: sum over all symmetry-equivalent pairs) ---
        # Generate grid positions based on cell type
        if self.cell_type == 'cubic':
            from ipcsp2.grids_and_symmetry import cubic
            grid_positions = cubic(self.grid_x)
        else:
            from ipcsp2.grids_and_symmetry import generate_orthorhombic
            grid_positions = generate_orthorhombic([self.grid_x, self.grid_y, self.grid_z])
        
        obj = gb.QuadExpr()
        for t1, type1 in enumerate(types):
            for t2, type2 in enumerate(types):
                spp_obj = spp.get(type1, type2)
                for i in range(O):
                    for j in range(i, O):  # include i==j for intra-orbit pairs
                        # Get all symmetry-equivalent positions for orbits i and j
                        positions_i = [int(orb_key[i])] + orbits[orb_key[i]]
                        positions_j = [int(orb_key[j])] + orbits[orb_key[j]]
                        spp_sum = 0.0
                        for idx_i in positions_i:
                            for idx_j in positions_j:
                                # Avoid double-counting for i==j (intra-orbit): only count idx_i < idx_j
                                if (i == j and idx_i >= idx_j):
                                    continue
                                pos_i = grid_positions[idx_i]
                                pos_j = grid_positions[idx_j]
                                # Compute minimum image convention distance in fractional coordinates
                                d = np.linalg.norm((pos_i - pos_j + 0.5) % 1.0 - 0.5)
                                
                                # For orthorhombic cells, we need to scale the distance by the cell dimensions
                                if self.cell_type == 'cubic':
                                    scaled_distance = d * self.cell_a
                                else:
                                    # Use average cell dimension for distance scaling
                                    avg_cell = (self.cell_a + self.cell_b + self.cell_c) / 3.0
                                    scaled_distance = d * avg_cell
                                
                                spp_val = float(spp_obj(scaled_distance))
                                if spp_val > 1e6:
                                    continue
                                spp_sum += spp_val
                        # For i != j, each pair is counted twice in the full sum, so multiply by 2
                        if i != j:
                            spp_sum *= 2
                        obj.add(Vars[t1][i] * Vars[t2][j], spp_sum)
        m.setObjective(obj, gb.GRB.MINIMIZE)
        # -------------------------------------------------------------
        self.model = m
        if TimeLimit > 0:
            m.params.TimeLimit = TimeLimit
        if not verbose:
            m.params.OutputFlag = 0
        if PoolSolutions > 1:
            m.params.PoolSolutions = PoolSolutions
            m.params.PoolSearchMode = 2
        m.Params.NodefileStart = 1
        print("Writing model file")
        m.write("model.lp")
        m.optimize()
        runtime = m.Runtime
        if m.status == gb.GRB.CUTOFF:
            print("Cutoff! No solution with negative energy.")
            return None
        if m.status in [gb.GRB.OPTIMAL, gb.GRB.TIME_LIMIT, gb.GRB.INTERRUPTED]:
            print("There are", m.SolCount, "solutions")
            res = [self.solution_to_Atoms(i, orbits) for i in range(m.SolCount)]
            if PoolSolutions > 1:
                return res, runtime, m.objVal
            else:
                return res[0:1], runtime, m.objVal
        return None

    def optimize_qubo(self, group='1', at_dwave=False, num_reads=10,
                             infinity_placement=100, infinity_orbit=100, annealing_time=200):
        """
        The function to optimise the structure on the quantum annealer or with simulated annealing.
        infinity_orbit is the penalty for putting two ions on the orbit
        infinity_placement is the penalty for placing the incorrect number of ions into the structure
        """
        import neal
        import dimod
        import dwave.embedding
        import dwave.system
        from dwave.system.samplers import DWaveSampler
        from dwave.system.composites import EmbeddingComposite

        print("Running integer programming optimisation to generate a model file with the required coefficients and "
              "obtain the ground truth for the lowest energy allocation.")

        # Build SPPCollection for all relevant pairs
        symbols = list(self.ions.keys())
        spp_pairs = set()
        for a in symbols:
            for b in symbols:
                spp_pairs.add(tuple(sorted([a, b])))
        spp_dir = os.path.join(os.path.dirname(__file__), 'SPP', 'SPP')
        spp = SPPCollection(spp_dir)
        spp.load(spp_pairs)

        _, _, target_energy = self.optimize_cube_symmetry_ase(group=group, verbose=False, spp=spp)

        print("Generating quadratic unconstrained binary problem from model.lp")

        bqm_model = BQM()
        bqm_model.parse_lp("model.lp")
        bqm_model.parse_constraints()
        bqm_model.max_bound()
        bqm_model.qubofy(infinity_placement, infinity_orbit)

        np.set_printoptions(suppress=True)
        print('Five number summary of the interaction coefficients of the Ising hamiltonian:', np.percentile(
            np.array(list(bqm_model.quadratic.values())), [0, 25, 50, 75, 100], interpolation='midpoint'))

        # print(bqm_model.linear, bqm_model.quadratic, bqm_model.offset)
        print("The offset is equal to", bqm_model.offset)

        # solver = neal.SimulatedAnnealingSampler()
        bqm = dimod.BinaryQuadraticModel(bqm_model.linear, bqm_model.quadratic, bqm_model.offset, dimod.BINARY)

        # bqm.fix_variable(('Sr', 7), 1)
        # bqm.fix_variable(('Ti', 0), 1)
        # print(list(bqm.variables))
        print("There are ", len(bqm.variables), "variables in the program")
        print("Running the Annealer")
        print("A series of readouts with the energy, allocation to the lattice positions:")

        def stoic(datum):
            # Helper to count ions in a sample (for debugging)
            counts = {}
            for k, v in datum[0].items():
                if k[0] in counts:
                    counts[k[0]] += v
                else:
                    counts[k[0]] = v
            return 'Counts: ' + str(counts)

        def simplify(datum):
            # Helper to extract sample info from annealer output
            sample = {'energy': 0, 'sample': [], 'num_occurrences': 0}
            sample['energy'] = datum[1]
            sample['num_occurrences'] = int(datum[2])

            for k, v in datum[0].items():
                if v == 1:
                    sample['sample'].append(k)
            return sample

        if at_dwave:
            # Quantum annealing path (requires D-Wave hardware)
            embedding = dwave.embedding.chimera.find_clique_embedding(len(bqm.variables), 16)
            print("The number of qubits: ", sum(len(chain) for chain in embedding.values()))
            print("The longest chain: ", max(len(chain) for chain in embedding.values()))
            exit()
            sampler = EmbeddingComposite(DWaveSampler())
            response = sampler.sample(bqm, num_reads=num_reads, annealing_time=annealing_time)
            min_energy = 1000000
            sol = None
            json_result = []

            i = 1
            for datum in response.data(['sample', 'energy', 'num_occurrences']):
                print(f"Readout {i}:", simplify(datum))
                i += 1
                json_result.append(simplify(datum))

                if datum.energy < min_energy:
                    sol = datum
                    min_energy = datum.energy
            with open('last_dwave.json', 'w') as f:
                json.dump(json_result, f, indent=2)

            print("The best found allocation:\n(atom specie, position on a lattice)")
            for i in sol.sample.keys():
                if sol.sample[i] == 1:
                    print(i)
            print("The lowest found energy: ", sol.energy, "Occurrences: ", sol.num_occurrences)
            return sol.energy, target_energy
        else:
            # Classical simulated annealing path (neal)
            solver = neal.SimulatedAnnealingSampler()
            response = solver.sample(bqm, num_reads=num_reads)
            min_energy = 10000
            sample = 0

            i = 1
            for datum in response.data(['sample', 'energy', 'num_occurrences']):
                print(f"Readout {i}:", simplify(datum))
                i += 1

                if datum.energy < min_energy:
                    sample = datum
                    min_energy = datum.energy

            print("The best found allocation: (atom specie, position on a lattice)")
            for i in sample.sample.keys():
                if sample.sample[i] == 1:
                    print(i)
            print("The lowest found energy: ", sample.energy, "Occurrences: ", sample.num_occurrences)
            return sample.energy, target_energy
