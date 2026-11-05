"""Small, inspectable molecular display presets."""

PRESETS = {
    "protein-protein": {
        "description": "Protein partner in cartoon against a recessive target.",
        "defaults": {"partner_representation": "cartoon", "target_transparency": 0.18},
    },
    "protein-ligand": {
        "description": "Ligand in sticks, visible through a transparent target.",
        "defaults": {"partner_representation": "sticks", "target_transparency": 0.5},
    },
    "cyclic-peptide": {
        "description": "Peptide in thick sticks, including nonpolymer CCD models.",
        "defaults": {"partner_representation": "sticks", "partner_stick_radius": 0.30,
                     "target_transparency": 0.35},
    },
}
