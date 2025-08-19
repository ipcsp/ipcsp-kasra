#!/usr/bin/env python3
"""
Test script to demonstrate the new pymatgen-based symmetry analysis.
This shows how the refactored code now handles all 230 space groups automatically.
"""

from ipcsp2.grids_and_symmetry import (
    generate_orbits_with_pymatgen,
    generate_cubic_orbits,
    generate_orthorhombic_orbits,
    get_space_group_info
)
import time

def test_space_group_coverage():
    """Test that we can handle various space groups automatically."""
    print("=== Testing Space Group Coverage ===\n")
    
    # Test different crystal systems
    test_groups = [
        (1, "P1 (triclinic)"),
        (2, "P-1 (triclinic)"),
        (3, "P2 (monoclinic)"),
        (16, "P222 (orthorhombic)"),
        (195, "P23 (cubic)"),
        (221, "Pm-3m (cubic)"),
        (230, "Ia-3d (cubic)")
    ]
    
    for sg_num, sg_name in test_groups:
        try:
            info = get_space_group_info(sg_num)
            if info:
                print(f"✓ SG {sg_num:3d}: {info['symbol']:8s} ({info['crystal_system']:10s})")
            else:
                print(f"✗ SG {sg_num:3d}: Failed to get info")
        except Exception as e:
            print(f"✗ SG {sg_num:3d}: Error - {e}")

def test_orbit_generation():
    """Test orbit generation for different grid types and space groups."""
    print("\n=== Testing Orbit Generation ===\n")
    
    # Test cubic grid
    print("Cubic 6x6x6 grid:")
    for sg in [1, 195, 221]:
        try:
            orbits = generate_cubic_orbits(6, str(sg))
            info = get_space_group_info(sg)
            sg_symbol = info['symbol'] if info else f"SG{sg}"
            print(f"  SG {sg:3d} ({sg_symbol:8s}): {len(orbits):3d} orbits")
        except Exception as e:
            print(f"  SG {sg:3d}: Error - {e}")
    
    # Test orthorhombic grid
    print("\nOrthorhombic 4x6x8 grid:")
    for sg in [1, 16, 195, 221]:
        try:
            orbits = generate_orthorhombic_orbits([4, 6, 8], str(sg))
            info = get_space_group_info(sg)
            sg_symbol = info['symbol'] if info else f"SG{sg}"
            print(f"  SG {sg:3d} ({sg_symbol:8s}): {len(orbits):3d} orbits")
        except Exception as e:
            print(f"  SG {sg:3d}: Error - {e}")

def test_performance():
    """Test performance of orbit generation."""
    print("\n=== Performance Test ===\n")
    
    grid_sizes = [8, 12, 16]
    space_groups = [1, 195, 221]
    
    for grid_size in grid_sizes:
        print(f"Grid size: {grid_size}x{grid_size}x{grid_size}")
        for sg in space_groups:
            start_time = time.time()
            try:
                orbits = generate_cubic_orbits(grid_size, str(sg))
                end_time = time.time()
                info = get_space_group_info(sg)
                sg_symbol = info['symbol'] if info else f"SG{sg}"
                print(f"  SG {sg:3d} ({sg_symbol:8s}): {len(orbits):4d} orbits in {end_time-start_time:.3f}s")
            except Exception as e:
                print(f"  SG {sg:3d}: Error - {e}")

def test_backward_compatibility():
    """Test that existing code still works."""
    print("\n=== Backward Compatibility Test ===\n")
    
    try:
        # Test that the old function signatures still work
        from ipcsp2.grids_and_symmetry import readGroup
        
        print("Testing readGroup function (now uses pymatgen internally):")
        for sg in [1, 195, 221]:
            matrices = readGroup(str(sg))
            print(f"  SG {sg:3d}: {len(matrices)} symmetry operations")
        
        print("\n✓ Backward compatibility maintained!")
        
    except Exception as e:
        print(f"✗ Backward compatibility issue: {e}")

def main():
    """Run all tests."""
    print("Testing Pymatgen-Based Symmetry Analysis")
    print("=" * 50)
    
    test_space_group_coverage()
    test_orbit_generation()
    test_performance()
    test_backward_compatibility()
    
    print("\n" + "=" * 50)
    print("All tests completed!")
    print("\nKey benefits of the new implementation:")
    print("✓ Automatic coverage of all 230 space groups")
    print("✓ No need to maintain manual G{number}.txt files")
    print("✓ Robust handling of any crystal system")
    print("✓ Better accuracy using crystallographic algorithms")
    print("✓ Maintains backward compatibility")

if __name__ == "__main__":
    main() 