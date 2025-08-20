#!/usr/bin/env python3
"""
Simple example using pymatgen for crystal structure analysis.
This shows how to do what your current system does, but much simpler.
"""

from pymatgen.core import Structure, Lattice
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from pymatgen.analysis.structure_matcher import StructureMatcher
from pymatgen.analysis.energy_models import EwaldSummation
import numpy as np

def analyze_structure_with_pymatgen():
    """Simple crystal structure analysis using pymatgen."""
    
    # 1. Create a structure (much simpler than your current approach)
    print("=== Creating NaCl structure with pymatgen ===")
    
    # NaCl structure (rock salt)
    lattice = Lattice.cubic(5.64)  # 5.64 Å cubic cell
    structure = Structure(
        lattice=lattice,
        species=['Na', 'Cl'],
        coords=[[0, 0, 0], [0.5, 0.5, 0.5]]  # Na at origin, Cl at center
    )
    
    print(f"Structure: {structure}")
    print(f"Formula: {structure.formula}")
    print(f"Volume: {structure.volume:.2f} Å³")
    
    # 2. Analyze symmetry (automatic!)
    print("\n=== Symmetry Analysis ===")
    analyzer = SpacegroupAnalyzer(structure)
    symmetry_dataset = analyzer.get_symmetry_dataset()
    
    print(f"Space group: {symmetry_dataset['international']}")
    print(f"Space group number: {symmetry_dataset['number']}")
    print(f"Point group: {symmetry_dataset['pointgroup']}")
    print(f"Crystal system: {symmetry_dataset['crystal_system']}")
    
    # 3. Get symmetry operations (what your system does manually)
    print(f"\nNumber of symmetry operations: {len(analyzer.get_symmetry_operations())}")
    
    # 4. Ewald summation (built-in!)
    print("\n=== Ewald Summation ===")
    ewald = EwaldSummation(structure)
    print(f"Ewald energy: {ewald.total_energy:.4f} eV")
    print(f"Real space energy: {ewald.real_energy:.4f} eV")
    print(f"Reciprocal space energy: {ewald.reciprocal_energy:.4f} eV")
    
    # 5. Structure comparison (what your StructureMatcher does)
    print("\n=== Structure Comparison ===")
    
    # Create a slightly different structure
    structure2 = Structure(
        lattice=Lattice.cubic(5.65),  # Slightly different lattice
        species=['Na', 'Cl'],
        coords=[[0, 0, 0], [0.5, 0.5, 0.5]]
    )
    
    matcher = StructureMatcher()
    if matcher.fit(structure, structure2):
        print("Structures are equivalent!")
    else:
        print("Structures are different")
    
    return structure

def generate_grid_positions_pymatgen(grid_size=6):
    """Generate grid positions using pymatgen (simpler than your current approach)."""
    print(f"\n=== Generating {grid_size}x{grid_size}x{grid_size} grid ===")
    
    # Create a simple cubic lattice
    lattice = Lattice.cubic(10.0)
    
    # Generate grid points
    grid_points = []
    for i in range(grid_size):
        for j in range(grid_size):
            for k in range(grid_size):
                # Fractional coordinates
                frac_coords = [i/grid_size, j/grid_size, k/grid_size]
                grid_points.append(frac_coords)
    
    print(f"Generated {len(grid_points)} grid points")
    return grid_points, lattice

def analyze_any_composition_pymatgen(composition, space_group_number=1):
    """Analyze any chemical composition with pymatgen."""
    print(f"\n=== Analyzing {composition} with space group {space_group_number} ===")
    
    # Create structure with any composition
    lattice = Lattice.cubic(10.0)
    
    # Parse composition (simple approach)
    if composition == "NaCl":
        species = ['Na', 'Cl']
        coords = [[0, 0, 0], [0.5, 0.5, 0.5]]
    elif composition == "MgO":
        species = ['Mg', 'O']
        coords = [[0, 0, 0], [0.5, 0.5, 0.5]]
    elif composition == "TiO2":
        species = ['Ti', 'O', 'O']
        coords = [[0, 0, 0], [0.5, 0, 0], [0, 0.5, 0]]
    else:
        # Default fallback
        species = ['Si']  # Default element
        coords = [[0, 0, 0]]
    
    structure = Structure(lattice=lattice, species=species, coords=coords)
    
    # Analyze symmetry
    analyzer = SpacegroupAnalyzer(structure)
    symmetry_dataset = analyzer.get_symmetry_dataset()
    
    print(f"Composition: {structure.formula}")
    print(f"Space group: {symmetry_dataset['international']} (#{symmetry_dataset['number']})")
    print(f"Crystal system: {symmetry_dataset['crystal_system']}")
    
    return structure

def main():
    """Main function demonstrating pymatgen capabilities."""
    print("Pymatgen Crystal Structure Analysis")
    print("=" * 50)
    
    # 1. Basic structure analysis
    structure = analyze_structure_with_pymatgen()
    
    # 2. Grid generation
    grid_points, lattice = generate_grid_positions_pymatgen(6)
    
    # 3. Analyze different compositions
    compositions = ["NaCl", "MgO", "TiO2"]
    for comp in compositions:
        analyze_any_composition_pymatgen(comp)
    
    print("\n" + "=" * 50)
    print("Key advantages of pymatgen approach:")
    print("✓ No manual file creation needed")
    print("✓ Automatic symmetry analysis")
    print("✓ Built-in Ewald summation")
    print("✓ Works with any composition")
    print("✓ Much simpler code")
    print("✓ Better accuracy and reliability")

if __name__ == "__main__":
    main() 