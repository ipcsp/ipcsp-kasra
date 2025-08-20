#!/usr/bin/env python3
"""
Using pymatgen for structural analysis ONLY, keeping SPP for energy.
This avoids Ewald/Buckingham potentials entirely.
"""

from pymatgen.core import Structure, Lattice
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from pymatgen.symmetry.groups import SpaceGroup
import numpy as np

def get_symmetry_operations_pymatgen(space_group_number):
    """
    Get symmetry operations using pymatgen (replaces your manual G{number}.txt files).
    This is what your current system does manually.
    """
    print(f"Getting symmetry operations for space group {space_group_number}")
    
    # Get space group object
    sg = SpaceGroup.from_int_number(space_group_number)
    symmetry_ops = sg.symmetry_ops
    
    print(f"Found {len(symmetry_ops)} symmetry operations")
    print(f"Space group: {sg.symbol}")
    print(f"Crystal system: {sg.crystal_system}")
    
    return symmetry_ops

def generate_orbits_pymatgen_simple(grid_size, space_group_number):
    """
    Generate symmetry orbits using pymatgen symmetry operations.
    This replaces your manual orbit generation.
    """
    print(f"Generating orbits for {grid_size}x{grid_size}x{grid_size} grid, SG {space_group_number}")
    
    # Get symmetry operations
    symmetry_ops = get_symmetry_operations_pymatgen(space_group_number)
    
    # Generate grid points (same as your current approach)
    grid_points = []
    for i in range(grid_size):
        for j in range(grid_size):
            for k in range(grid_size):
                grid_points.append([i/grid_size, j/grid_size, k/grid_size])
    
    grid_points = np.array(grid_points)
    
    # Generate orbits (same logic as your current system)
    orbits = {}
    remaining_points = list(range(len(grid_points)))
    
    while remaining_points:
        point_idx = remaining_points.pop()
        orbits[point_idx] = []
        
        for op in symmetry_ops:
            # Apply symmetry operation
            transformed_point = op.operate(grid_points[point_idx])
            
            # Apply periodic boundary conditions
            transformed_point = (transformed_point + 0.5) % 1.0 - 0.5
            
            # Find equivalent grid points
            for idx, p in enumerate(grid_points):
                if idx in remaining_points:
                    if np.allclose(transformed_point, p, atol=1e-4):
                        remaining_points.remove(idx)
                        orbits[point_idx].append(idx)
                        break
    
    print(f"Generated {len(orbits)} orbits from {len(grid_points)} grid points")
    return orbits

def analyze_structure_symmetry_pymatgen(structure):
    """
    Analyze structure symmetry using pymatgen (no energy calculations).
    """
    print("=== Structure Symmetry Analysis (No Energy) ===")
    
    analyzer = SpacegroupAnalyzer(structure)
    symmetry_dataset = analyzer.get_symmetry_dataset()
    
    print(f"Space group: {symmetry_dataset['international']}")
    print(f"Space group number: {symmetry_dataset['number']}")
    print(f"Point group: {symmetry_dataset['pointgroup']}")
    print(f"Crystal system: {symmetry_dataset['crystal_system']}")
    print(f"Number of symmetry operations: {len(analyzer.get_symmetry_operations())}")
    
    return symmetry_dataset

def create_structure_for_analysis(composition, cell_params):
    """
    Create a structure for analysis (no energy calculations).
    """
    if composition == "NaCl":
        lattice = Lattice.cubic(cell_params['a'])
        structure = Structure(
            lattice=lattice,
            species=['Na', 'Cl'],
            coords=[[0, 0, 0], [0.5, 0.5, 0.5]]
        )
    elif composition == "MgO":
        lattice = Lattice.cubic(cell_params['a'])
        structure = Structure(
            lattice=lattice,
            species=['Mg', 'O'],
            coords=[[0, 0, 0], [0.5, 0.5, 0.5]]
        )
    else:
        # Generic approach
        lattice = Lattice.cubic(cell_params['a'])
        structure = Structure(
            lattice=lattice,
            species=['Si'],  # Placeholder
            coords=[[0, 0, 0]]
        )
    
    return structure

def main():
    """
    Demonstrate using pymatgen for structure analysis only,
    keeping your SPP energy model.
    """
    print("Pymatgen for Structure Analysis + SPP for Energy")
    print("=" * 60)
    
    # 1. Get symmetry operations (replaces your G{number}.txt files)
    print("\n1. Getting symmetry operations:")
    for sg_num in [1, 195, 221, 136]:
        get_symmetry_operations_pymatgen(sg_num)
    
    # 2. Generate orbits (replaces your manual orbit generation)
    print("\n2. Generating orbits:")
    orbits = generate_orbits_pymatgen_simple(6, 195)
    
    # 3. Analyze structure symmetry (no energy calculations)
    print("\n3. Structure analysis (no energy):")
    cell_params = {'a': 5.64, 'b': 5.64, 'c': 5.64}
    structure = create_structure_for_analysis("NaCl", cell_params)
    analyze_structure_symmetry_pymatgen(structure)
    
    print("\n" + "=" * 60)
    print("What this gives you:")
    print("✓ Automatic symmetry operations for ALL 230 space groups")
    print("✓ No manual G{number}.txt files needed")
    print("✓ Robust orbit generation")
    print("✓ Structure analysis and comparison")
    print("✓ NO Ewald/Buckingham potentials")
    print("✓ Keep your SPP energy model")
    print("✓ Much simpler code")

if __name__ == "__main__":
    main() 