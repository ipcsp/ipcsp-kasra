import os
import pandas as pd
from pymatgen.core import Structure
from pymatgen.analysis.structure_matcher import StructureMatcher


def read_energy(energy_file, idx, energy_type="final"):
    """
    Reads the initial or final energy for a given solution index from the energies.txt file.
    Args:
        energy_file (str): Path to the energies.txt file.
        idx (int): 1-based index of the solution (e.g., 1 for solution1).
        energy_type (str): 'initial' or 'final'.
    Returns:
        float or None: The energy value if found, else None.
    """
    try:
        with open(energy_file) as f:
            lines = []
            for l in f:
                if l.strip():
                    lines.append(l)
            if idx-1 < len(lines):
                line = lines[idx-1]
                if energy_type+":" in line:
                    return float(line.split(energy_type+":")[1].split()[0])
    except Exception:
        pass
    return None


def get_structures_and_energies(results_dir, prefix="solution", suffix=".vasp"):
    """
    Loads all available structures and their corresponding energies from a results directory.
    Args:
        results_dir (str): Path to the directory containing solution files and energies.txt.
        prefix (str): Prefix for solution files (default: 'solution').
        suffix (str): Suffix for solution files (default: '.vasp').
    Returns:
        list of tuples: Each tuple is (solution_number, Structure object, energy).
    """
    structures = []
    energy_file = os.path.join(results_dir, "energies.txt")
    i = 1
    while True:
        vasp_file = os.path.join(results_dir, f"{prefix}{i}{suffix}")
        if not os.path.exists(vasp_file):
            break  # Stop if the next solution file does not exist
        try:
            struct = Structure.from_file(vasp_file)
            if "minimised" in suffix:
                energy = read_energy(energy_file, i, energy_type="final")
            else:
                energy = read_energy(energy_file, i, energy_type="initial")
            structures.append((i, struct, energy))
        except Exception as e:
            print(f"Error reading {vasp_file}: {e}")
        i += 1
    return structures


def parse_summary(path, is_typical=False):
    """
    Parse the summary.txt file and return a dictionary mapping problem name to grid and group.
    """
    summary = {}
    try:
        with open(path) as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Warning: Summary file not found at {path}. Using empty summary.")
        return summary
    
    # Find the table header
    for i, line in enumerate(lines):
        if line.strip().startswith('|') and 'grid' in line:
            header = []
            for h in line.strip().split('|'):
                if h.strip():
                    header.append(h.strip())
            start = i + 2
            break
        if is_typical and line.strip().startswith('|') and 'Discretisation' in line:
            header = []
            for h in line.strip().split('|'):
                if h.strip():
                    header.append(h.strip())
            start = i + 2
            break
    else:
        return summary
    # Parse the table rows
    for line in lines[start:]:
        if not line.strip().startswith('|'):
            break
        row = []
        for c in line.strip().split('|'):
            if c.strip():
                row.append(c.strip())
        if not row:
            continue
        if is_typical:
            name = row[0]
            grid = int(row[1])
            group = int(row[2])
        else:
            name = row[0]
            grid = int(row[1])
            group = int(row[2])
        summary[name] = {'grid': grid, 'group': group}
    return summary


def compare_structures(spp_structs, ff_structs, prob, structure_type, matcher, spp_info, ff_info):
    """
    Compare all SPP solutions to all typical results for a given structure type.
    Match if structures are equivalent AND energies are exactly equal.
    Returns a list of result rows for the output table and a set of matched SPP solution indices.
    """
    rows = []
    matched_spp_solutions = set()  # Track which SPP solutions found matches
    
    for spp_idx, spp_struct, spp_energy in spp_structs:
        for ff_idx, ff_struct, ff_energy in ff_structs:
            match = matcher.fit(spp_struct, ff_struct)
            energies_match = (spp_energy == ff_energy) if spp_energy is not None and ff_energy is not None else False
            
            # Full match: both structures and energies match
            if match and energies_match:
                matched_spp_solutions.add(spp_idx)
                rows.append({
                    "problem": prob,
                    "structure_type": structure_type,
                    "spp_solution": spp_idx,
                    "spp_energy": spp_energy,
                    "spp_grid": spp_info.get('grid'),
                    "spp_group": spp_info.get('group'),
                    "matched_ff_solution": ff_idx,
                    "matched_ff_energy": ff_energy,
                    "ff_grid": ff_info.get('grid'),
                    "ff_group": ff_info.get('group'),
                    "structures_match": True,
                    "match_type": "full_match"
                })
            # Energy match but structure mismatch: interesting case
            elif not match and energies_match:
                rows.append({
                    "problem": prob,
                    "structure_type": structure_type,
                    "spp_solution": spp_idx,
                    "spp_energy": spp_energy,
                    "spp_grid": spp_info.get('grid'),
                    "spp_group": spp_info.get('group'),
                    "matched_ff_solution": ff_idx,
                    "matched_ff_energy": ff_energy,
                    "ff_grid": ff_info.get('grid'),
                    "ff_group": ff_info.get('group'),
                    "structures_match": False,
                    "match_type": "energy_only"
                })
    
    return rows, matched_spp_solutions


def main():
    """
    Compares SPP and typical (force-field) solutions for each problem, matches structures (both minimised and lattice),
    and outputs a table summarizing the correspondence and energies, including only matching pairs and extra info.
    Also includes unmatched SPP solutions at the bottom of the table.
    """
    spp_base = "results"  # Directory containing SPP results
    ff_base = "typical_results"  # Directory containing typical force-field results
    spp_summary = parse_summary(os.path.join(spp_base, "summary.txt"))
    ff_summary = parse_summary(os.path.join(ff_base, "summary.txt"), is_typical=True)
    problems = []
    for d in os.listdir(spp_base):
        if os.path.isdir(os.path.join(spp_base, d)):
            problems.append(d)
    matcher = StructureMatcher()  # Pymatgen's structure matcher for equivalence
    rows = []  # Will hold all rows for the output table
    
    for prob in problems:
        spp_dir = os.path.join(spp_base, prob)
        ff_dir = os.path.join(ff_base, prob)
        
        # Skip if the corresponding typical result directory doesn't exist
        if not os.path.exists(ff_dir):
            print(f"Warning: No typical results found for {prob}")
            continue
            
        spp_info = spp_summary.get(prob, {})
        ff_info = ff_summary.get(prob, {})
        
        # Track all SPP solutions for this problem
        all_spp_solutions = set()
        
        # Compare minimised structures
        spp_min_structs = get_structures_and_energies(spp_dir, suffix="_minimised.vasp")
        ff_min_structs = get_structures_and_energies(ff_dir, suffix="_minimised.vasp")
        min_rows, min_matched = compare_structures(spp_min_structs, ff_min_structs, prob, "minimised", matcher, spp_info, ff_info)
        rows.extend(min_rows)
        for idx, _, _ in spp_min_structs:
            all_spp_solutions.add((idx, "minimised"))
        
        # Compare lattice structures
        spp_lat_structs = get_structures_and_energies(spp_dir, suffix="_lattice.vasp")
        ff_lat_structs = get_structures_and_energies(ff_dir, suffix="_lattice.vasp")
        lat_rows, lat_matched = compare_structures(spp_lat_structs, ff_lat_structs, prob, "lattice", matcher, spp_info, ff_info)
        rows.extend(lat_rows)
        for idx, _, _ in spp_lat_structs:
            all_spp_solutions.add((idx, "lattice"))
        
        # Find unmatched SPP solutions
        matched_solutions = set()
        for idx in min_matched:
            matched_solutions.add((idx, "minimised"))
        for idx in lat_matched:
            matched_solutions.add((idx, "lattice"))
        
        unmatched_solutions = all_spp_solutions - matched_solutions
        
        # Add unmatched solutions to the main table
        for spp_idx, structure_type in unmatched_solutions:
            # Get the energy for this unmatched solution
            if structure_type == "minimised":
                spp_structs = spp_min_structs
            else:
                spp_structs = spp_lat_structs
            
            spp_energy = None
            for idx, _, energy in spp_structs:
                if idx == spp_idx:
                    spp_energy = energy
                    break
            
            rows.append({
                "problem": prob,
                "structure_type": structure_type,
                "spp_solution": spp_idx,
                "spp_energy": spp_energy,
                "spp_grid": spp_info.get('grid'),
                "spp_group": spp_info.get('group'),
                "matched_ff_solution": None,
                "matched_ff_energy": None,
                "ff_grid": None,
                "ff_group": None,
                "structures_match": False
            })
    
    # Create DataFrame and sort
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(by=["problem", "spp_solution"])
        # Convert solution numbers to integer type (nullable Int64)
        df["spp_solution"] = df["spp_solution"].astype('Int64')
        df["matched_ff_solution"] = df["matched_ff_solution"].astype('Int64')
        # Convert grid and group columns to integer type (nullable Int64)
        for col in ["ff_grid", "ff_group", "spp_grid", "spp_group"]:
            if col in df.columns:
                df[col] = df[col].astype('Int64')
    
    # Save to CSV and print
    df.to_csv("structure_comparison_table.csv", index=False)
    print(df)


if __name__ == "__main__":
    main()
