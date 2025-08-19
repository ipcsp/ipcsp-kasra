import os
import shutil
import subprocess
import sys
from time import time
from copy import deepcopy
import pandas as pd
from tabulate import tabulate
import ase.io
from ase.calculators.gulp import GULP
import json
try:
    import yaml
except Exception:
    yaml = None

from ipcsp2 import root_dir
from ipcsp2.integer_program import Allocate
from ipcsp2.matrix_generator import Phase
from ipcsp2.spp import SPPCollection, compute_spp_objective

class MLatticeABCInterface:
    def __init__(self, base_root_dir=None):
        self.base_root_dir = base_root_dir if base_root_dir is not None else root_dir

    def _find_mlattice_dir(self):
        possible_paths = [
            os.path.join(self.base_root_dir, 'MLatticeABC'),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'MLatticeABC'),
            os.path.join(os.getcwd(), 'MLatticeABC'),
            'MLatticeABC'
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
        print("Error: MLatticeABC directory not found. Tried paths:")
        for path in possible_paths:
            print(f"  - {os.path.abspath(path)}")
        return None

    def predict_lattice_parameters(self, composition, crystal_system):
        try:
            mlattice_dir = self._find_mlattice_dir()
            if not mlattice_dir or not os.path.exists(mlattice_dir):
                return None
            cmd = ['conda', 'run', '-n', 'mlatticeabc', 'python', 'predict.py', '-i', composition, '-s', crystal_system]
            print("Running MLatticeABC prediction...")
            print(f"Command: {' '.join(cmd)}")
            result = subprocess.run(cmd, cwd=mlattice_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=True)
            output = result.stdout
            print(f"MLatticeABC output:\n{output}")
            lattice_params = {}
            import re
            if crystal_system.lower() == 'crystal':
                a_match = re.search(r'a=\s*([\d.]+)', output)
                b_match = re.search(r'b=\s*([\d.]+)', output)
                c_match = re.search(r'c=\s*([\d.]+)', output)
                cubic_match = re.search(r'a=b=c=\s*([\d.]+)', output)
                tetragonal_match_a = re.search(r'a=b=\s*([\d.]+)', output)
                tetragonal_match_c = re.search(r'c=\s*([\d.]+)', output)
                if cubic_match:
                    value = float(cubic_match.group(1))
                    lattice_params = {'a': value, 'b': value, 'c': value}
                elif tetragonal_match_a and tetragonal_match_c:
                    a_value = float(tetragonal_match_a.group(1))
                    c_value = float(tetragonal_match_c.group(1))
                    lattice_params = {'a': a_value, 'b': a_value, 'c': c_value}
                elif a_match and b_match and c_match:
                    lattice_params = {'a': float(a_match.group(1)), 'b': float(b_match.group(1)), 'c': float(c_match.group(1))}
            elif crystal_system.lower() in ['cubic']:
                match = re.search(r'a=b=c=\s*([\d.]+)', output)
                if match:
                    value = float(match.group(1))
                    lattice_params = {'a': value, 'b': value, 'c': value}
            elif crystal_system.lower() in ['hexagonal', 'trigonal', 'tetragonal']:
                a_match = re.search(r'a=b=\s*([\d.]+)', output)
                c_match = re.search(r'c=\s*([\d.]+)', output)
                if a_match and c_match:
                    a_value = float(a_match.group(1))
                    c_value = float(c_match.group(1))
                    lattice_params = {'a': a_value, 'b': a_value, 'c': c_value}
            else:
                a_match = re.search(r'a=\s*([\d.]+)', output)
                b_match = re.search(r'b=\s*([\d.]+)', output)
                c_match = re.search(r'c=\s*([\d.]+)', output)
                if a_match and b_match and c_match:
                    lattice_params = {'a': float(a_match.group(1)), 'b': float(b_match.group(1)), 'c': float(c_match.group(1))}
            if not lattice_params:
                print("Warning: Could not parse lattice parameters from output")
                return None
            return lattice_params
        except subprocess.CalledProcessError as e:
            print(f"Error running MLatticeABC: {e}")
            print(f"Error output: {e.stderr}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None

class CrystalSystemAnalyzer:
    @staticmethod
    def detect_crystal_system(a, b, c, alpha, beta, gamma):
        is_90 = lambda x: x == 90.0
        is_equal = lambda x, y: x == y
        all_90 = is_90(alpha) and is_90(beta) and is_90(gamma)
        if not all_90:
            return 'triclinic'
        a_eq_b = is_equal(a, b)
        b_eq_c = is_equal(b, c)
        a_eq_c = is_equal(a, c)
        if a_eq_b and b_eq_c:
            return 'cubic'
        if a_eq_b and not b_eq_c:
            return 'tetragonal'
        if not (a_eq_b or b_eq_c or a_eq_c):
            return 'orthorhombic'
        return 'orthorhombic'

class PhaseNameDeterminer:
    @staticmethod
    def determine_phase_name(ions_count):
        elements = set(ions_count.keys())
        if {'Sr', 'Ti', 'O'} <= elements:
            return 'SrTiO'
        elif {'Y', 'O'} <= elements and 'Ti' not in elements:
            return 'YSrTiO'
        elif {'Y', 'Ti', 'O'} <= elements:
            return 'YSrTiO'
        elif {'Mg', 'Al', 'O'} <= elements:
            return 'LiMgAlPO'
        elif {'Ca', 'Al', 'Si', 'O'} <= elements:
            return 'CaAlSiO'
        elif {'Zn', 'S'} <= elements:
            return 'ZnS'
        elif {'Zr', 'O'} <= elements:
            return 'ZrO'
        print("Warning: Unknown composition, defaulting to SrTiO phase.")
        return 'SrTiO'

class CLIInputManager:
    def __init__(self, analyzer: CrystalSystemAnalyzer, phase_determiner: PhaseNameDeterminer, ml_interface: MLatticeABCInterface):
        self.analyzer = analyzer
        self.phase_determiner = phase_determiner
        self.ml_interface = ml_interface

    def get_mlattice_prediction(self):
        print("\n" + "="*60)
        print("MLatticeABC Lattice Parameter Prediction")
        print("="*60)
        print("\nEnter chemical composition (e.g., SrTiO3):")
        while True:
            composition = input("Composition: ").strip()
            if composition:
                break
            print("Please enter a valid composition.")
        print("\nEnter crystal system:")
        print("Available options: crystal (unknown), cubic, hexagonal, trigonal, tetragonal, orthorhombic, monoclinic, triclinic")
        while True:
            crystal_system = input("Crystal system: ").strip().lower()
            valid_systems = ['crystal', 'cubic', 'hexagonal', 'trigonal', 'tetragonal', 'orthorhombic', 'monoclinic', 'triclinic']
            if crystal_system in valid_systems:
                break
            print(f"Please enter one of: {', '.join(valid_systems)}")
        print(f"\nPredicting lattice parameters for {composition} ({crystal_system} system)...")
        lattice_params = self.ml_interface.predict_lattice_parameters(composition, crystal_system)
        if lattice_params:
            print(f"\nPrediction successful!")
            print(f"Predicted lattice parameters:")
            print(f"  a = {lattice_params['a']:.4f} Å")
            print(f"  b = {lattice_params['b']:.4f} Å")
            print(f"  c = {lattice_params['c']:.4f} Å")
            if crystal_system == 'crystal':
                alpha = beta = gamma = 90.0
            elif crystal_system == 'cubic':
                alpha = beta = gamma = 90.0
            elif crystal_system in ['hexagonal', 'trigonal', 'tetragonal']:
                alpha = beta = 90.0
                gamma = 120.0 if crystal_system in ['hexagonal', 'trigonal'] else 90.0
            else:
                alpha = beta = gamma = 90.0
            use_for_csp = input("\nWould you like to use these parameters for Crystal Structure Prediction? (y/n): ").strip().lower()
            return {
                'composition': composition,
                'crystal_system': crystal_system,
                'lattice_params': lattice_params,
                'angles': {'alpha': alpha, 'beta': beta, 'gamma': gamma},
                'use_for_csp': use_for_csp in ['y', 'yes']
            }
        else:
            print("Prediction failed. Please check the composition and crystal system.")
            return None

    def get_user_input(self, mlattice_params=None):
        print("\nEnter chemical composition (e.g., Mg8Al16O32, SrTiO3):")
        while True:
            try:
                composition_input = input("Composition: ").strip()
                if not composition_input:
                    print("Please enter a valid composition.")
                    continue
                ions_count = {}
                i = 0
                while i < len(composition_input):
                    if composition_input[i].isupper():
                        element = composition_input[i]
                        i += 1
                        while i < len(composition_input) and composition_input[i].islower():
                            element += composition_input[i]
                            i += 1
                        count = ""
                        while i < len(composition_input) and composition_input[i].isdigit():
                            count += composition_input[i]
                            i += 1
                        if count:
                            ions_count[element] = int(count)
                        else:
                            ions_count[element] = 1
                    else:
                        i += 1
                if not ions_count:
                    print("No valid elements found. Please try again.")
                    continue
                print(f"Composition: {ions_count}")
                if mlattice_params and mlattice_params.get('use_for_csp'):
                    print(f"\nUsing MLatticeABC predicted lattice parameters:")
                    a = mlattice_params['lattice_params']['a']
                    b = mlattice_params['lattice_params']['b']
                    c = mlattice_params['lattice_params']['c']
                    alpha = mlattice_params['angles']['alpha']
                    beta = mlattice_params['angles']['beta']
                    gamma = mlattice_params['angles']['gamma']
                    print(f"a = {a:.4f} Å, b = {b:.4f} Å, c = {c:.4f} Å")
                    print(f"α = {alpha:.2f}°, β = {beta:.2f}°, γ = {gamma:.2f}°")
                else:
                    print("\nEnter unit cell parameters:")
                    while True:
                        try:
                            a_input = input("a (Å): ").strip()
                            b_input = input("b (Å): ").strip()
                            c_input = input("c (Å): ").strip()
                            alpha_input = input("α (degrees): ").strip()
                            beta_input = input("β (degrees): ").strip()
                            gamma_input = input("γ (degrees): ").strip()
                            a = float(a_input)
                            b = float(b_input)
                            c = float(c_input)
                            alpha = float(alpha_input)
                            beta = float(beta_input)
                            gamma = float(gamma_input)
                            break
                        except ValueError:
                            print("Invalid cell parameters. Please enter numeric values.")
                            continue
                crystal_system = CrystalSystemAnalyzer.detect_crystal_system(a, b, c, alpha, beta, gamma)
                cell_parameters = {
                    'a': a,
                    'b': b,
                    'c': c,
                    'alpha': alpha,
                    'beta': beta,
                    'gamma': gamma,
                    'type': crystal_system
                }
                print(f"\nDetected crystal system: {crystal_system}")
                print(f"Cell parameters: a={a}Å, b={b}Å, c={c}Å, α={alpha}°, β={beta}°, γ={gamma}°")
                if crystal_system == 'cubic':
                    grid_input = input("Grid size (4-8, default 4): ").strip()
                    try:
                        grid = int(grid_input)
                        if grid <= 0:
                            grid = 4
                    except ValueError:
                        grid = 4
                    grid_parameters = {'x': grid, 'y': grid, 'z': grid}
                elif crystal_system == 'tetragonal':
                    grid_input = input("Grid size X=Y (4-8, default 4): ").strip()
                    grid_z_input = input("Grid size Z (4-8, default 4): ").strip()
                    try:
                        grid_xy = int(grid_input) if grid_input else 4
                        grid_z = int(grid_z_input) if grid_z_input else 4
                        if grid_xy <= 0: grid_xy = 4
                        if grid_z <= 0: grid_z = 4
                    except ValueError:
                        grid_xy = grid_z = 4
                    grid_parameters = {'x': grid_xy, 'y': grid_xy, 'z': grid_z}
                else:
                    print("\nEnter grid sizes for each dimension:")
                    grid_x_input = input("Grid size X (4-8, default 4): ").strip()
                    grid_y_input = input("Grid size Y (4-8, default 4): ").strip()
                    grid_z_input = input("Grid size Z (4-8, default 4): ").strip()
                    try:
                        grid_x = int(grid_x_input) if grid_x_input else 4
                        grid_y = int(grid_y_input) if grid_y_input else 4
                        grid_z = int(grid_z_input) if grid_z_input else 4
                        if grid_x <= 0: grid_x = 4
                        if grid_y <= 0: grid_y = 4
                        if grid_z <= 0: grid_z = 4
                    except ValueError:
                        grid_x = grid_y = grid_z = 4
                    grid_parameters = {'x': grid_x, 'y': grid_y, 'z': grid_z}
                print("\nEnter space group number:")
                print("  • 1 = P1 (no symmetry constraints)")
                print("  • 195, 221, 227 = Common cubic space groups")
                print("  • Other numbers = Any valid space group")
                group_input = input("Space group number (default 1): ").strip()
                try:
                    if group_input:
                        group = int(group_input)
                        if group <= 0:
                            print("Invalid space group number. Using P1 (group 1)")
                            group = 1
                    else:
                        group = 1
                except ValueError:
                    print("Invalid input. Using P1 (group 1)")
                    group = 1
                if group == 1:
                    print(f"Selected: P1 (no symmetry constraints)")
                else:
                    print(f"Selected: Space group {group}")
                top_input = input("Top solutions (1-20, default 1): ").strip()
                try:
                    top = int(top_input)
                    if top <= 0:
                        top = 1
                except ValueError:
                    top = 1
                phase_name = PhaseNameDeterminer.determine_phase_name(ions_count)
                return {
                    'ions_count': ions_count,
                    'phase_name': phase_name,
                    'cell_parameters': cell_parameters,
                    'grid_parameters': grid_parameters,
                    'group': group,
                    'top': top
                }
            except KeyboardInterrupt:
                print("\nExiting...")
                return None
            except Exception as e:
                print(f"Error: {e}")
                print("Please try again.")

class CSPApplication:
    def __init__(self, settings_dict):
        self.settings = settings_dict
        self.ml_interface = MLatticeABCInterface()
        self.analyzer = CrystalSystemAnalyzer()
        self.phase_determiner = PhaseNameDeterminer()
        self.cli = CLIInputManager(self.analyzer, self.phase_determiner, self.ml_interface)

    def run(self):
        print("=" * 60)
        print("IPCSP - Integer Programming for Crystal Structure Prediction")
        print("=" * 60)
        print("Choose an option:")
        print("1. Run predefined benchmarks")
        print("2. Enter custom chemical composition")
        print("3. Predict lattice parameters using MLatticeABC")
        
        while True:
            try:
                choice = input("\nEnter your choice (1, 2, or 3): ").strip()
                
                if choice == "1":
                    print("\nRunning predefined benchmarks...")
                    runner = CSPBenchmarkRunner(self.settings)
                    runner.run()
                    break
                elif choice == "2":
                    composition_params = self.cli.get_user_input()
                    if composition_params:
                        print(f"\nRunning custom case with composition: {composition_params['ions_count']}")
                        test_case = run_user_input_case(composition_params)
                        print(f"\nCustom case completed!")
                        print(f"Best energy found: {test_case.best_energy} eV")
                        print(f"Runtime: {test_case.runtime:.2f} seconds")
                    break
                elif choice == "3":
                    ml_prediction_params = self.cli.get_mlattice_prediction()
                    if ml_prediction_params:
                        print(f"\nMLatticeABC prediction for {ml_prediction_params['composition']} ({ml_prediction_params['crystal_system']} system):")
                        print(f"  a = {ml_prediction_params['lattice_params']['a']:.4f} Å")
                        print(f"  b = {ml_prediction_params['lattice_params']['b']:.4f} Å")
                        print(f"  c = {ml_prediction_params['lattice_params']['c']:.4f} Å")
                        
                        if ml_prediction_params['use_for_csp']:
                            print("\nMLatticeABC prediction will be used for Crystal Structure Prediction.")
                            print(f"  α = {ml_prediction_params['angles']['alpha']:.2f}°")
                            print(f"  β = {ml_prediction_params['angles']['beta']:.2f}°")
                            print(f"  γ = {ml_prediction_params['angles']['gamma']:.2f}°")
                            
                            print("\nWould you like to run the CSP with these MLatticeABC parameters? (y/n): ")
                            if input().strip().lower() in ['y', 'yes']:
                                print("Proceeding with CSP using MLatticeABC parameters...")
                                composition_params = self.cli.get_user_input(ml_prediction_params)
                                if composition_params:
                                    print(f"\nRunning custom case with composition: {composition_params['ions_count']}")
                                    test_case = run_user_input_case(composition_params)
                                    print(f"\nCustom case completed!")
                                    print(f"Best energy found: {test_case.best_energy} eV")
                                    print(f"Runtime: {test_case.runtime:.2f} seconds")
                        else:
                            print("\nMLatticeABC prediction will not be used for CSP.")
                    break
                else:
                    print("Please enter 1, 2, or 3.")
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {e}")
                print("Please try again.")

def predict_lattice_parameters(composition, crystal_system):
    """
    Object-oriented wrapper that delegates to MLatticeABCInterface.
    """
    return MLatticeABCInterface().predict_lattice_parameters(composition, crystal_system)

def get_mlattice_prediction():
    """
    Object-oriented wrapper that delegates to CLIInputManager.
    """
    return CLIInputManager(CrystalSystemAnalyzer(), PhaseNameDeterminer(), MLatticeABCInterface()).get_mlattice_prediction()

def get_user_input(mlattice_params=None):
    """
    Object-oriented wrapper that delegates to CLIInputManager.
    """
    return CLIInputManager(CrystalSystemAnalyzer(), PhaseNameDeterminer(), MLatticeABCInterface()).get_user_input(mlattice_params)



def detect_crystal_system(a, b, c, alpha, beta, gamma):
    """
    Object-oriented wrapper that delegates to CrystalSystemAnalyzer.
    """
    return CrystalSystemAnalyzer.detect_crystal_system(a, b, c, alpha, beta, gamma)

def determine_phase_name(ions_count):
    """
    Object-oriented wrapper that delegates to PhaseNameDeterminer.
    """
    return PhaseNameDeterminer.determine_phase_name(ions_count)

def run_user_input_case(composition_params):
    """
    Run a single case with user-provided composition parameters.
    """
    name = "user_input"
    params = {
        'test': True,
        'grid': composition_params['grid_parameters'],
        'group': composition_params['group'],
        'top': composition_params['top']
    }
    
    test_case = CSPTestCase(name, params)
    test_case.user_ions_count = composition_params['ions_count']
    test_case.user_phase_name = composition_params['phase_name']
    test_case.user_cell_parameters = composition_params['cell_parameters']
    
    print(f"Running: {composition_params['ions_count']} | {composition_params['phase_name']} | Cell: {composition_params['cell_parameters']} | Grid: {composition_params['grid_parameters']} | Group: {composition_params['group']}")
    
    test_case.run()
    
    return test_case

# Settings dictionary as before
# This dictionary defines all the test cases and their parameters.
settings = {
    # The first part is done using Gurobi on a local machine.
    # Every line corresponds to a row in Table 1.

    # perovskite structure of SrTiO
    'SrTiO3_1': {'test': True, 'multiple': 1, 'group': 1, 'top': 1, 'grid': 4},  # group is 221, sub 195
    'SrTiO3_2': {'test': False, 'multiple': 2, 'group': 195, 'top': 1, 'grid': 8},  # group is 221, sub 195
    'SrTiO3_3': {'test': False, 'multiple': 3, 'group': 221, 'top': 1, 'grid': 6},  # group is 221, sub 195
    'SrTiO3_4': {'test': False, 'multiple': 3, 'group': 200, 'top': 1, 'grid': 6},  # group is 221, sub 195
    'SrTiO3_5': {'test': False, 'multiple': 3, 'group': 195, 'top': 1, 'grid': 6},  # group is 221, sub 195
    # bixbyite structure of Y2O3f
    'Y2O3_1': {'test': True, 'group': 206, 'top': 1, 'grid': 8},  # group is 206, sub 199, sub 198
    'Y2O3_2': {'test': False, 'group': 199, 'top': 1, 'grid': 8},  # group is 206, sub 199, sub 198
    'Y2O3_3': {'test': False, 'group': 206, 'top': 1, 'grid': 8},  # group is 206, sub 199, sub 198
    # pyrochlore structure of Y2Ti2O7
    'Y2Ti2O7_1': {'test': True, 'group': 227, 'top': 2, 'grid': 8},  # group is 227, 196, 195
    'Y2Ti2O7_2': {'test': False, 'group': 227, 'top': 1, 'grid': 8},  # group is 227, 196, 195
    # spinel structure of MgAl2O4
    'MgAl2O4_1': {'test': True, 'group': 227, 'top': 1, 'grid': 8},  # group is 227, sub 195, 196, grid is 8
    'MgAl2O4_2': {'test': False, 'group': 227, 'top': 1, 'grid': 8},  # 16 group is 227, sub 195, 196, grid is 8
    'MgAl2O4_3': {'test': False, 'group': 196, 'top': 1, 'grid': 8},  # group is 227, sub 195, 196, grid is 8
    'MgAl2O4_4': {'test': False, 'group': 195, 'top': 20, 'grid': 8},  # group is 227, sub 195, 196, grid is 8
    # garnet structure of Ca3Al2Si3O12
    'Ca3Al2Si3O12_1': {'test': True, 'group': 230, 'top': 1, 'grid': 8},  # 16 group is 230, sub 206, 199, grid is 8
    'Ca3Al2Si3O12_2': {'test': False, 'group': 206, 'top': 1, 'grid': 8},  # group is 230, sub 206, 199, grid is 8

    # Quantum annealer section. We use D-Wave SDK to solve the periodic lattice atom allocation problems.

    'quantum_SrO': {'test': True, 'group': 195, 'at_dwave': False, 'num_reads': 100,
                    'multiple': 1, 'infinity_placement': 100, 'infinity_orbit': 100,
                    'annealing_time': 200},  # 'group': 225; pass group 195
    'quantum_SrTiO3': {'test': True, 'group': 221, 'at_dwave': False, 'num_reads': 100,
                       'multiple': 1, 'infinity_placement': 100, 'infinity_orbit': 100,
                       'annealing_time': 200},  # group 221, passed 221
    'quantum_ZnS': {'test': True, 'group': 195, 'at_dwave': False, 'num_reads': 200,
                    'multiple': 1, 'infinity_placement': 100, 'infinity_orbit': 100,
                    'annealing_time': 200},  # 'group': 216; passed 196
    'quantum_ZrO2': {'test': True, 'group': 198, 'at_dwave': False, 'num_reads': 300,
                     'multiple': 1, 'infinity_placement': 50, 'infinity_orbit': 50,
                     'annealing_time': 1000},  # group 225, sub 200, 198, 195
}

class CSPTestCase:
    """
    Represents a single CSP test case (classical or quantum).
    Handles allocation, optimization, and result processing.
    """
    def __init__(self, name, params):
        """
        Initialize the test case with its name and parameters.
        Args:
            name (str): The name of the test case (e.g., 'MgAl2O4_1').
            params (dict): The parameters for the test case from the settings dictionary.
        """
        self.name = name
        self.params = params
        self.results_dir = params.get('results_dir', os.path.join("..", "results", name))
        self.best_energy = None
        self.expected_energy = None
        self.runtime = None
        self.at_dwave = params.get('at_dwave', False)
        self.output_formats = params.get('output_formats', ['vasp'])
        # User input parameters (for custom compositions)
        self.user_ions_count = None
        self.user_phase_name = None
        self.user_cell_parameters = None

    def run(self):
        """
        Run the test case (classical or quantum).
        Calls the appropriate method based on the test case name.
        """
        if self.name.startswith('quantum_'):
            self._run_quantum()
        else:
            self._run_classical()

    def _run_classical(self):
        """
        Run a classical (Gurobi) test case.
        Sets up the ions, phase, and cell size, then runs the SPP allocation and optimization.
        Also computes the expected energy from the reference CIF structure.
        """
        if self.user_ions_count is not None:
            # Use user-provided parameters
            ions_count = self.user_ions_count
            phase_name = self.user_phase_name
            cell_parameters = self.user_cell_parameters
        else:
            # Use hard-coded parameters
            ions_count, phase_name, cell_size = self._get_classical_params()
            cell_parameters = {'a': cell_size, 'b': cell_size, 'c': cell_size, 'alpha': 90.0, 'beta': 90.0, 'gamma': 90.0, 'type': 'cubic'}
            
        grid_params = self.params['grid']
        group = self.params['group']
        top = self.params['top']
        
        # Run allocation and optimization
        self.best_energy, self.runtime = self.run_spp_allocation(phase_name, ions_count, grid_params, cell_parameters, group, top)
        
        # Get expected energy from CIF
        cif_file, lib_file = self._get_cif_and_lib(phase_name)
        self.expected_energy = self.get_cif_energy(cif_file, lib_file, ions_count)
        
        # Adjust for multiples if needed
        if 'multiple' in self.params and self.params['multiple'] > 1:
            self.expected_energy *= self.params['multiple'] ** 3

    def _run_quantum(self):
        """
        Run a quantum (annealer) test case.
        Sets up the ions, phase, and allocation, then runs the quantum optimization.
        """
        # Setup ions, phase, and allocation based on the test case name
        if self.name == 'quantum_SrO':
            phase = Phase('SrTiO')
            multiple = self.params['multiple']
            ions_count = {'O': 4 * multiple ** 3, 'Sr': 4 * multiple ** 3}
            grid_size = multiple * 2
            cell_size = 5.2 * multiple
        elif self.name == 'quantum_ZnS':
            phase = Phase('ZnS')
            ions_count = {'Zn': 4, 'S': 4}
            grid_size = 4
            cell_size = 5.4
        elif self.name == 'quantum_ZrO2':
            phase = Phase('ZrO')
            ions_count = {'Zr': 4, 'O': 8}
            grid_size = 4
            cell_size = 5.07
        elif self.name == 'quantum_SrTiO3':
            phase = Phase('SrTiO')
            multiple = self.params['multiple']
            ions_count = {'O': 3 * multiple ** 3, 'Sr': 1 * multiple ** 3, 'Ti': 1 * multiple ** 3}
            grid_size = multiple * 2
            cell_size = 3.9 * multiple
        else:
            raise ValueError(f"Unknown quantum test case: {self.name}")
        allocation = Allocate(ions_count, grid_size=grid_size, cell_size=cell_size, phase=phase)
        start = time()
        self.best_energy, self.expected_energy = allocation.optimize_qubo(
            group=self.params['group'],
            at_dwave=self.params['at_dwave'],
            num_reads=self.params['num_reads'],
            infinity_placement=self.params['infinity_placement'],
            infinity_orbit=self.params['infinity_orbit'],
            annealing_time=self.params['annealing_time']
        )
        self.runtime = time() - start

    def run_spp_allocation(self, phase_name, ions_count, grid_params, cell_parameters, group, top):
        """
        Run SPP-based allocation and optimization for a classical test case.
        Returns the best energy and runtime.
        """
        phase = Phase(phase_name)
        spp_dir = os.path.join(os.path.dirname(__file__), 'SPP', 'SPP')
        spp_pairs = set(tuple(sorted([a, b])) for a in ions_count for b in ions_count)
        spp = SPPCollection(spp_dir)
        spp.load(spp_pairs)
        
        # Handle grid parameters - convert to appropriate format for Allocate
        if isinstance(grid_params, dict):
            # Non-cubic case: pass as list for orthorhombic grids
            grid_size = [grid_params['x'], grid_params['y'], grid_params['z']]
        else:
            # Cubic case: single grid size
            grid_size = grid_params
            
        # Handle cell parameters - pass directly to Allocate
        allocation = Allocate(ions_count, grid_size=grid_size, cell_size=cell_parameters, phase=phase)
        start = time()
        results, runtime, _ = allocation.optimize_cube_symmetry_ase(
            group=group, PoolSolutions=top, TimeLimit=0, spp=spp)
        
        # Use pedone.lib for CaAlSiO, buck.lib for others
        if phase_name == "CaAlSiO":
            libfile = phase.filedir / f"{phase_name}/pedone.lib"
        else:
            libfile = phase.filedir / f"{phase_name}/buck.lib"
        best_energy = self.process_results(lib=libfile, results=results, ions_count=ions_count)
        end = time()
        return best_energy, runtime

    def process_results(self, lib, results, ions_count, printing=False):
        """
        Process and locally optimize a list of candidate structures.
        Writes energies and structures to the results directory.
        Returns the best energy found.
        """
        os.makedirs(self.results_dir, exist_ok=True)
        calc = GULP(keywords='single', library=os.path.join(".", lib))
        results_ip = deepcopy(results)
        N_atoms = sum(ions_count.values())
        spp_dir = os.path.join(os.path.dirname(__file__), 'SPP', 'SPP')
        spp_pairs = set(tuple(sorted([i, j])) for i in ions_count for j in ions_count)
        spp = SPPCollection(spp_dir)
        spp.load(spp_pairs)
        init = [0] * len(results)
        final = [0] * len(results)
        spp_scores = [0] * len(results)
        best_val = float('inf')
        best_idx = 0
        print(f"\n========== Processing and locally optimising solutions for {self.name} ==========\n")
        for idx, cryst in enumerate(results):
            if len(cryst.arrays['positions']) == N_atoms:
                cryst.calc = calc
                init[idx] = cryst.get_potential_energy()
                spp_scores[idx] = spp.score(cryst.get_chemical_symbols(), cryst.get_positions(), cryst.get_cell(), pbc=True)
                _ = compute_spp_objective(cryst, spp)
        calc.set(keywords='opti conjugate conp diff comp c6')
        prev_energy = -1000000
        for idx, cryst in enumerate(results):
            if init[idx] < -0.00001:
                if init[idx] - prev_energy > 0.000001:
                    prev_energy = init[idx]
                    opt = calc.get_optimizer(cryst)
                    try:
                        opt.run(fmax=0.05)
                        final[idx] = cryst.get_potential_energy()
                    except ValueError:
                        print("One of the relaxations failed using initial energy instead")
                        final[idx] = init[idx]
                    if final[idx] < best_val:
                        best_idx = idx
                        best_val = final[idx]
        solution_data = []
        for i in range(len(results)):
            if final[i] != 0:
                spp_obj_min = compute_spp_objective(results[i], spp)
                print(f"SPP objective (utility) for minimized solution {i}: {spp_obj_min}")
                solution_data.append((final[i], init[i], spp_scores[i], results_ip[i], results[i]))
        solution_data.sort(key=lambda x: x[0])
        count = 1
        with open(os.path.join(self.results_dir, "energies.txt"), "w+") as f:
            for final_e, init_e, spp_score, atoms_lattice, atoms_min in solution_data:
                print(f"Solution{count}: ", "Energy initial: ", init_e, " final: ", final_e, f" SPP: {spp_score}")
                print(f"Solution{count}: ", "Energy initial: ", init_e, " final: ", final_e, f" SPP: {spp_score}", file=f)
                for fmt in self.output_formats:
                    ase.io.write(os.path.join(self.results_dir, f'solution{count}_lattice.{fmt}'), atoms_lattice)
                    ase.io.write(os.path.join(self.results_dir, f'solution{count}_minimised.{fmt}'), atoms_min)
                count += 1
        print(f"The lowest found energy is {best_val} eV")
        if printing:
            print("Paused, the files can be copied")
            input()
        return best_val

    def get_cif_energy(self, filename, library, ions_count, format='cif'):
        """
        Compute the energy of the reference CIF structure using GULP.
        Returns the energy value.
        """
        filedir = root_dir / 'structures/'
        cryst = ase.io.read(os.path.join(".", filedir / filename), format=format, parallel=False)
        calc = GULP(keywords='conp', library=library)
        calc.set(keywords='opti conjugate conp diff comp c6')
        opt = calc.get_optimizer(cryst)
        opt.run(fmax=0.05)
        energy = cryst.get_potential_energy()
        print(f"The energy of {filename} is equal to {energy} eV")
        return energy

    def _get_classical_params(self):
        """
        Returns ions_count, phase_name, cell_size for classical test cases based on the test case name.
        """
        if self.name.startswith('SrTiO3'):
            multiple = self.params['multiple']
            ions_count = {'O': 3 * multiple ** 3, 'Sr': 1 * multiple ** 3, 'Ti': 1 * multiple ** 3}
            phase_name = 'SrTiO'
            cell_size = 3.9 * multiple
        elif self.name.startswith('Y2O3'):
            ions_count = {'O': 48, 'Y': 32}
            phase_name = 'YSrTiO'
            cell_size = 10.7
        elif self.name.startswith('Y2Ti2O7'):
            ions_count = {'O': 56, 'Y': 16, 'Ti': 16}
            phase_name = 'YSrTiO'
            cell_size = 10.2
        elif self.name.startswith('MgAl2O4'):
            ions_count = {'O': 32, 'Mg': 8, 'Al': 16}
            phase_name = 'LiMgAlPO'
            cell_size = 8.2
        elif self.name.startswith('Ca3Al2Si3O12'):
            z = 8
            ions_count = {'Ca': 3 * z, 'Al': 2 * z, 'Si': 3 * z, 'O': 12 * z}
            phase_name = 'CaAlSiO'
            cell_size = 11.9
        else:
            raise ValueError(f"Unknown classical test case: {self.name}")
        return ions_count, phase_name, cell_size

    def _get_cif_and_lib(self, phase_name):
        """
        Returns the CIF filename and library file for a given phase.
        """
        if phase_name == 'SrTiO':
            return 'SrTiO3.cif', Phase('SrTiO').filedir / 'SrTiO/buck.lib'
        elif phase_name == 'YSrTiO':
            if self.name.startswith('Y2O3'):
                return 'Y2O3.cif', Phase('YSrTiO').filedir / 'YSrTiO/buck.lib'
            else:
                return 'Y2Ti2O7.cif', Phase('YSrTiO').filedir / 'YSrTiO/buck.lib'
        elif phase_name == 'LiMgAlPO':
            return 'MgAl2O4.cif', Phase('LiMgAlPO').filedir / 'LiMgAlPO/buck.lib'
        elif phase_name == 'CaAlSiO':
            return 'Ca3Al2Si3O12.cif', Phase('CaAlSiO').filedir / 'CaAlSiO/pedone.lib'
        else:
            raise ValueError(f"Unknown phase name: {phase_name}")

class CSPBenchmarkRunner:
    """
    Orchestrates running all CSP benchmarks and writing summary tables.
    """
    def __init__(self, settings):
        """
        Initialize the benchmark runner with the settings dictionary.
        """
        self.settings = settings
        self.results_dir = os.path.join("..", "results")
        self.classical_summary = []
        self.quantum_summary = []

    def run(self):
        """
        Run all benchmarks: prepares the results directory, runs classical and quantum benchmarks, and writes the summary.
        """
        self._prepare_results_dir()
        self.run_classical_benchmarks()
        self.run_quantum_benchmarks()
        self.write_summary()

    def _prepare_results_dir(self):
        """
        Remove and recreate the results directory to ensure a clean run.
        """
        shutil.rmtree(self.results_dir, ignore_errors=True)
        os.makedirs(self.results_dir, exist_ok=True)

    def run_classical_benchmarks(self):
        """
        Run all classical test cases as specified in the settings dictionary.
        """
        for i in range(1, 6):
            name = f'SrTiO3_{i}'
            if self.settings.get(name, {}).get('test', False):
                self._run_and_record(name)
        for i in range(1, 4):
            name = f'Y2O3_{i}'
            if self.settings.get(name, {}).get('test', False):
                self._run_and_record(name)
        for i in range(1, 3):
            name = f'Y2Ti2O7_{i}'
            if self.settings.get(name, {}).get('test', False):
                self._run_and_record(name)
        for i in range(1, 5):
            name = f'MgAl2O4_{i}'
            if self.settings.get(name, {}).get('test', False):
                self._run_and_record(name)
        for i in range(1, 3):
            name = f'Ca3Al2Si3O12_{i}'
            if self.settings.get(name, {}).get('test', False):
                self._run_and_record(name)

    def run_quantum_benchmarks(self):
        """
        Run all quantum test cases as specified in the settings dictionary.
        """
        for name in ['quantum_SrO', 'quantum_SrTiO3', 'quantum_ZnS', 'quantum_ZrO2']:
            if self.settings.get(name, {}).get('test', False):
                self._run_and_record(name, quantum=True)

    def _run_and_record(self, name, quantum=False):
        """
        Run a single test case and record its results in the summary tables.
        Args:
            name (str): The name of the test case.
            quantum (bool): Whether this is a quantum test case.
        """
        params = self.settings[name]
        test_case = CSPTestCase(name, params)
        test_case.run()
        if quantum:
            self.quantum_summary.append({
                'name': name,
                'dwave': params.get('at_dwave', False),
                'best_E': test_case.best_energy,
                'expected_E': test_case.expected_energy,
                'time': test_case.runtime
            })
        else:
            self.classical_summary.append({
                'name': name,
                'grid': params.get('grid'),
                'group': params.get('group'),
                'best_E': test_case.best_energy,
                'expected_E': test_case.expected_energy,
                'time': test_case.runtime
            })

    def write_summary(self):
        """
        Write the summary tables for classical and quantum benchmarks to the results directory.
        """
        # Write classical summary
        df_classical = pd.DataFrame(self.classical_summary)
        with open(os.path.join(self.results_dir, "summary.txt"), "w+") as f:
            print("Non-heuristic optimisation using Gurobi with subsequent local minimisation (test equivalent to Table 1 of the paper):", file=f)
            print(tabulate(df_classical, headers="keys", tablefmt='github', showindex=False), file=f)
        # Write quantum summary
        df_quantum = pd.DataFrame(self.quantum_summary)
        with open(os.path.join(self.results_dir, "summary.txt"), "a") as f:
            print("\n\n\n\n\n Quantum annealing for the periodic lattice atom allocation.\n", file=f)
            print(tabulate(df_quantum, headers="keys", tablefmt='github', showindex=False), file=f)

# -------------------- Config-based non-interactive runner --------------------

def _load_config_file(path):
    with open(path, 'r') as f:
        text = f.read()
    lower = path.lower()
    if lower.endswith('.json'):
        return json.loads(text)
    if lower.endswith(('.yml', '.yaml')):
        if yaml is None:
            raise RuntimeError("PyYAML is not installed. Please install with 'pip install pyyaml' or use JSON config.")
        return yaml.safe_load(text)
    raise ValueError("Unsupported config file type. Use .json, .yml or .yaml")

class CSPConfigRunner:
    def __init__(self, config_dict):
        self.config = config_dict or {}
        self.global_results_dir = self.config.get('results_dir', os.path.join('..', 'results-config'))
        self.global_output_formats = self.config.get('output_formats', ['vasp'])
        os.makedirs(self.global_results_dir, exist_ok=True)
        self.summary_rows = []

    def _make_results_dir_for_job(self, name, job):
        job_dir = job.get('results_dir') or os.path.join(self.global_results_dir, name)
        os.makedirs(job_dir, exist_ok=True)
        return job_dir

    def run(self):
        jobs = self.config.get('jobs', [])
        if not jobs:
            # If no jobs specified, optionally run predefined benchmarks if requested
            if self.config.get('run_benchmarks', False):
                runner = CSPBenchmarkRunner(settings)
                runner.run()
                # copy/merge summary into config results dir
                shutil.copyfile(os.path.join('..', 'results', 'summary.txt'), os.path.join(self.global_results_dir, 'summary.txt'))
                return
            raise ValueError("Config has no 'jobs' and 'run_benchmarks' is not set.")
        for idx, job in enumerate(jobs, start=1):
            preset = job.get('preset')
            name = job.get('name') or (preset if preset else f'job_{idx}')
            output_formats = job.get('output_formats', self.global_output_formats)
            results_dir = self._make_results_dir_for_job(name, job)

            if preset:
                if preset not in settings:
                    raise ValueError(f"Preset '{preset}' not found in settings")
                params = dict(settings[preset])
                params['results_dir'] = results_dir
                params['output_formats'] = output_formats
                test_case = CSPTestCase(name, params)
                test_case.run()
                self.summary_rows.append({
                    'name': name,
                    'grid': params.get('grid'),
                    'group': params.get('group'),
                    'best_E': test_case.best_energy,
                    'expected_E': test_case.expected_energy,
                    'time': test_case.runtime,
                    'results_dir': results_dir
                })
                continue

            job_type = job.get('type', 'classical')
            if job_type == 'classical':
                ions_count = job['ions_count']
                phase_name = job.get('phase_name') or PhaseNameDeterminer.determine_phase_name(ions_count)
                cell_parameters = job['cell_parameters']
                grid = job['grid']
                group = job['group']
                top = job.get('top', 1)
                params = {
                    'grid': grid,
                    'group': group,
                    'top': top,
                    'results_dir': results_dir,
                    'output_formats': output_formats
                }
                test_case = CSPTestCase(name, params)
                test_case.user_ions_count = ions_count
                test_case.user_phase_name = phase_name
                test_case.user_cell_parameters = cell_parameters
                test_case.run()
                self.summary_rows.append({
                    'name': name,
                    'grid': grid,
                    'group': group,
                    'best_E': test_case.best_energy,
                    'expected_E': test_case.expected_energy,
                    'time': test_case.runtime,
                    'results_dir': results_dir
                })
            elif job_type == 'quantum':
                qname = job['name']  # must be one of the supported quantum_* names
                params = {
                    'group': job['group'],
                    'at_dwave': job.get('at_dwave', False),
                    'num_reads': job.get('num_reads', 100),
                    'infinity_placement': job.get('infinity_placement', 100),
                    'infinity_orbit': job.get('infinity_orbit', 100),
                    'annealing_time': job.get('annealing_time', 200),
                    'multiple': job.get('multiple', 1),
                    'results_dir': results_dir,
                    'output_formats': output_formats
                }
                test_case = CSPTestCase(qname, params)
                test_case.run()
                self.summary_rows.append({
                    'name': qname,
                    'grid': None,
                    'group': params.get('group'),
                    'best_E': test_case.best_energy,
                    'expected_E': test_case.expected_energy,
                    'time': test_case.runtime,
                    'results_dir': results_dir
                })
            else:
                raise ValueError(f"Unsupported job type '{job_type}'. Use 'classical', 'quantum', or 'preset'.")
        # Write combined summary
        df = pd.DataFrame(self.summary_rows)
        with open(os.path.join(self.global_results_dir, 'summary.txt'), 'w+') as f:
            print(tabulate(df, headers='keys', tablefmt='github', showindex=False), file=f)

# -------------------- Entry point --------------------

if __name__ == "__main__":
    # If a config file is passed, run non-interactively using the config
    if len(sys.argv) > 1 and sys.argv[1].lower().endswith(('.json', '.yml', '.yaml')):
        config_path = sys.argv[1]
        
        # Try to find the config file - first check if it's a relative path from current directory
        if os.path.isfile(config_path):
            # File exists as provided (absolute or relative to current directory)
            pass
        elif os.path.isfile(os.path.join(os.getcwd(), config_path)):
            # File exists relative to current working directory
            config_path = os.path.join(os.getcwd(), config_path)
        else:
            # File not found
            print(f"Error: Config file '{sys.argv[1]}' not found.")
            print(f"Current working directory: {os.getcwd()}")
            print(f"Tried paths:")
            print(f"  - {sys.argv[1]}")
            print(f"  - {os.path.join(os.getcwd(), sys.argv[1])}")
            sys.exit(1)
            
        cfg = _load_config_file(config_path)
        runner = CSPConfigRunner(cfg)
        runner.run()
    else:
        CSPApplication(settings).run()
