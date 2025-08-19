"""
Code generating lattices (grids) as well as dealing with symmetry constraints.
Now uses pymatgen for robust symmetry analysis instead of manual text files.
Space groups are automatically handled for all 230 international tables groups.
"""
import os.path
import numpy as np
import json
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from pymatgen.core import Structure, Lattice
from pymatgen.symmetry.groups import SpaceGroup
from ipcsp2 import root_dir

filedir = root_dir / 'data/grids/'

def generate_orthorhombic(ions_on_sides):
    """
    Ions_on_side=4 will generate points with x coordinates 0, 0.25, 0.5 and 0.75.
    Note that 1 is kind of another cell already. So, side/ions is the step size
    There will be prod(ions_on_sides) points in total in the cell.
    Check separately whether you get charge NEUTRAL system!
    """
    if isinstance(ions_on_sides, int):
        # Handle cubic case (backward compatibility)
        ions_on_sides = [ions_on_sides, ions_on_sides, ions_on_sides]
    
    step = 1.0 / np.array(ions_on_sides)

    pos = np.zeros((ions_on_sides[0] * ions_on_sides[1] * ions_on_sides[2], 3))
    # print("The total number of points in the cell is ", len(self.ions))

    row = 0
    for (i, j, k) in np.ndindex(ions_on_sides[0], ions_on_sides[1], ions_on_sides[2]):
        pos[row,] = np.array([i * step[0], j * step[1], k * step[2]])
        row = row + 1
    return pos


def cubic(ions_on_side):
    """
    generate points for the cubic grid
    """
    return generate_orthorhombic([ions_on_side, ions_on_side, ions_on_side])


def generate_orbits_with_pymatgen(ions_on_sides, space_group_number, cell_params=None):
    """
    Generate symmetry orbits using pymatgen for any space group and grid type.
    
    Args:
        ions_on_sides (list or int): Grid dimensions [nx, ny, nz] or single value for cubic
        space_group_number (int): International Tables space group number
        cell_params (dict): Cell parameters for non-cubic systems
        
    Returns:
        dict: Orbit mapping with same format as current implementation
    """
    if isinstance(ions_on_sides, int):
        ions_on_sides = [ions_on_sides, ions_on_sides, ions_on_sides]
    
    # Generate grid points
    step = 1.0 / np.array(ions_on_sides)
    points = []
    for (i, j, k) in np.ndindex(ions_on_sides[0], ions_on_sides[1], ions_on_sides[2]):
        points.append([i * step[0], j * step[1], k * step[2]])
    points = np.array(points)
    
    # Create a dummy structure with the desired space group
    if cell_params is None:
        # Default to cubic cell
        lattice = Lattice.cubic(10.0)
    else:
        lattice = Lattice.from_parameters(
            cell_params.get('a', 10.0), cell_params.get('b', 10.0), cell_params.get('c', 10.0),
            cell_params.get('alpha', 90), cell_params.get('beta', 90), cell_params.get('gamma', 90)
        )
    
    # Create a dummy structure (we only need the symmetry operations)
    dummy_structure = Structure(lattice, ["Si"], [[0, 0, 0]])
    
    # Get symmetry operations for the specified space group
    try:
        # Get the space group object
        sg = SpaceGroup.from_int_number(space_group_number)
        symmetry_ops = sg.symmetry_ops
    except Exception as e:
        print(f"Warning: Could not get space group {space_group_number}, using P1: {e}")
        # Fallback to P1 (no symmetry)
        symmetry_ops = [sg.symmetry_ops[0]] if hasattr(sg, 'symmetry_ops') else []
    
    # Generate orbits
    orbits = {}
    remaining_points = list(range(len(points)))
    
    while remaining_points:
        point_idx = remaining_points.pop()
        orbits[point_idx] = []
        
        for op in symmetry_ops:
            # Apply symmetry operation to the point
            transformed_point = op.operate(points[point_idx])
            
            # Apply periodic boundary conditions
            transformed_point = (transformed_point + 0.5) % 1.0 - 0.5
            
            # Find equivalent grid points
            for idx, p in enumerate(points):
                if idx in remaining_points:
                    # Check if points are equivalent within tolerance
                    if np.allclose(transformed_point, p, atol=1e-4):
                        remaining_points.remove(idx)
                        orbits[point_idx].append(idx)
                        break
    
    total_points = len(points)
    print(f"Grid {ions_on_sides} ({total_points} points): {len(orbits)} orbits for SG {space_group_number}")
    return orbits


def readGroup(number):
    '''
    DEPRECATED: Returns the list of augmented matrices of a space group with given number.
    This function is kept for backward compatibility but now uses pymatgen internally.
    '''
    print(f"Warning: readGroup({number}) is deprecated. Using pymatgen for space group {number}.")
    
    try:
        # Get the space group object
        sg = SpaceGroup.from_int_number(int(number))
        symmetry_ops = sg.symmetry_ops
    except Exception as e:
        print(f"Error getting space group {number}: {e}")
        # Return identity matrix for P1
        return [np.eye(4)]
    
    # Convert pymatgen symmetry operations to 4x4 matrices
    result = []
    for op in symmetry_ops:
        # Convert pymatgen symmetry operation to 4x4 matrix
        matrix = np.eye(4)
        matrix[:3, :3] = op.rotation_matrix
        matrix[:3, 3] = op.translation_vector
        result.append(matrix)
    
    return result


def generate_cubic_orbits(ions_on_side, group):
    """
    Generate symmetry orbits for cubic grids using pymatgen.
    Args:
        ions_on_side (int): Grid size for cubic grid
        group (str): Space group number as string
    Returns:
        dict: Orbit mapping
    """
    return generate_orbits_with_pymatgen(ions_on_side, int(group))


def generate_orthorhombic_orbits(ions_on_sides, group):
    """
    Generate symmetry orbits for orthorhombic grids using pymatgen.
    Args:
        ions_on_sides (list): List of grid sizes for each dimension [nx, ny, nz]
        group (str): Space group number as string
    Returns:
        dict: Orbit mapping
    """
    if isinstance(ions_on_sides, int):
        # Handle cubic case (backward compatibility)
        return generate_cubic_orbits(ions_on_sides, group)
    
    return generate_orbits_with_pymatgen(ions_on_sides, int(group))


def save_orthorhombic_orbits(ions_on_sides, group, output_dir=None):
    """
    Generate and save orthorhombic orbit files using pymatgen.
    Args:
        ions_on_sides (list): List of grid sizes for each dimension [nx, ny, nz]
        group (str): Space group number as string
        output_dir (str): Output directory (defaults to filedir)
    """
    if output_dir is None:
        output_dir = filedir
    
    # Create filename for orthorhombic grid
    grid_str = f"O{ions_on_sides[0]}{ions_on_sides[1]}{ions_on_sides[2]}G{group}"
    output_path = os.path.join(output_dir, f"{grid_str}.json")
    
    # Generate orbits using pymatgen
    orbits = generate_orthorhombic_orbits(ions_on_sides, group)
    
    # Save to file
    with open(output_path, "w") as f:
        json.dump(orbits, f, indent=2)
    
    print(f"Saved orthorhombic orbits to {output_path}")
    return output_path


def get_space_group_info(space_group_number):
    """
    Get information about a space group using pymatgen.
    Args:
        space_group_number (int): International Tables space group number
    Returns:
        dict: Space group information
    """
    try:
        sg = SpaceGroup.from_int_number(space_group_number)
        return {
            'number': space_group_number,
            'symbol': sg.symbol,
            'point_group': sg.point_group,
            'crystal_system': sg.crystal_system,
            'laue_group': getattr(sg, 'laue_group', 'Unknown')
        }
    except Exception as e:
        print(f"Error getting space group info for {space_group_number}: {e}")
        return None


if __name__ == "__main__":
    # Example usage of orthorhombic grids
    print("Testing orthorhombic grid generation...")
    
    # Test orthorhombic grid generation
    positions = generate_orthorhombic([4, 6, 8])
    print(f"Generated {len(positions)} positions for orthorhombic grid [4, 6, 8]")
    print(f"First few positions: {positions[:5]}")
    
    # Test orthorhombic orbit generation for P1 (no symmetry)
    print("\nTesting orthorhombic orbit generation for P1...")
    orbits_p1 = generate_orthorhombic_orbits([4, 6, 8], '1')
    print(f"P1 orbits: {len(orbits_p1)} orbits for grid [4, 6, 8]")
    
    # Test saving orthorhombic orbits
    print("\nTesting orthorhombic orbit file saving...")
    try:
        save_orthorhombic_orbits([4, 6, 8], '1')
        print("Successfully saved orthorhombic orbit file")
    except Exception as e:
        print(f"Error saving orthorhombic orbit file: {e}")
    
    # Test pymatgen-based orbit generation
    print("\nTesting pymatgen-based orbit generation...")
    test_grids = [[4, 4, 6], [6, 6, 8], [4, 8, 8]]
    test_groups = ['1', '195', '221']  # P1, P23, Pm-3m
    
    for grid in test_grids:
        for group in test_groups:
            try:
                print(f"Generating orbits for grid {grid}, group {group}...")
                orbits = generate_orthorhombic_orbits(grid, group)
                print(f"  Grid {grid}, Group {group}: {len(orbits)} orbits")
                
                # Get space group info
                sg_info = get_space_group_info(int(group))
                if sg_info:
                    print(f"    Space group: {sg_info['symbol']} ({sg_info['crystal_system']})")
            except Exception as e:
                print(f"  Error with grid {grid}, group {group}: {e}")
    
    # Test space group information
    print("\nTesting space group information...")
    for group_num in [1, 195, 221]:
        info = get_space_group_info(group_num)
        if info:
            print(f"SG {group_num}: {info['symbol']} ({info['crystal_system']})")
    
    exit()
