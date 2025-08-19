import argparse
import warnings
import os
from pymatgen.core.structure import Structure
from pymatgen.analysis.structure_matcher import StructureMatcher, SpeciesComparator, ElementComparator, SpinComparator, FrameworkComparator


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compare two CIF structures using pymatgen's StructureMatcher"
    )
    parser.add_argument(
        "cif1", help="Path to the first .cif file"
    )
    parser.add_argument(
        "cif2", help="Path to the second .cif file"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # 1. Read structures from two files (.cif or .vasp)
    def read_structure(file_path):
        ext = os.path.splitext(file_path)[1].lower()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if ext == ".cif":
                return Structure.from_file(file_path)
            elif ext == ".vasp" or ext == ".poscar":
                return Structure.from_file(file_path)
            else:
                raise ValueError(f"Unsupported file extension: {ext}. Only .cif and .vasp are supported.")

    struct1 = read_structure(args.cif1)
    print("Parsed composition 1:", struct1.composition.reduced_formula)

    struct2 = read_structure(args.cif2)
    print("Parsed composition 2:", struct2.composition.reduced_formula)

    # 2. Set matching parameters (tolerances & options) as variables
    LATTICE_TOL = 0.2         # max fractional lattice vector difference
    SITE_TOL = 0.3            # site-distance tolerance as fraction of average bond length
    ANGLE_TOL = 5             # lattice angle tolerance in degrees
    PRIMITIVE_CELL = False    # reduce to primitive cell before matching
    SCALE = True              # scale volumes to match
    ATTEMPT_SUPERCELL = False # attempt supercell transformations
    ALLOW_SUBSET = False      # allow one structure to be subset of the other

    # 3. Choose a comparator (SpeciesComparator for exact species match)
    # COMPARATOR = SpeciesComparator()
    COMPARATOR = ElementComparator()  # only match by element
    # COMPARATOR = SpinComparator()     # include spin in species matching
    # COMPARATOR = FrameworkComparator()

    # 4. Optionally ignore certain species (e.g. guest ions)
    IGNORED_SPECIES = []
    # e.g., IGNORED_SPECIES = ["Li"] to compare only host framework

    # 5. Instantiate the StructureMatcher
    matcher = StructureMatcher(
        ltol=LATTICE_TOL,
        stol=SITE_TOL,
        angle_tol=ANGLE_TOL,
        primitive_cell=PRIMITIVE_CELL,
        scale=SCALE,
        attempt_supercell=ATTEMPT_SUPERCELL,
        allow_subset=ALLOW_SUBSET,
        comparator=COMPARATOR,
        ignored_species=IGNORED_SPECIES
    )

    # 6. Perform the match
    is_match = matcher.fit(struct1, struct2)

    # 7. Compute RMS distance if matched
    rms = None
    if is_match:
        rms_list = matcher.get_rms_dist(struct1, struct2)
        if rms_list:
            rms = rms_list[0]

    # 8. Output results
    print(f"Structures match: {is_match}")
    if rms is not None:
        print(f"RMS displacement: {rms:.4e} Å")


if __name__ == "__main__":
    main()
