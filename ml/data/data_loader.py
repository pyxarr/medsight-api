from ml.data.wdbc_loader import load_wdbc
from ml.data.ucth_loader import load_ucth
from ml.data.coimbra_loader import load_coimbra


def load_all_datasets():
    print("Loading all datasets...")
    print("-" * 40)

    wisconsin_features, wisconsin_labels, wisconsin_metadata = load_wdbc()
    print(f"WDBC     → {wisconsin_metadata['n_samples']} samples | "
          f"Malignant: {wisconsin_metadata['n_malignant']} | "
          f"Benign: {wisconsin_metadata['n_benign']}")

    ucth_features, ucth_labels, ucth_metadata = load_ucth()
    print(f"UCTH     → {ucth_metadata['n_samples']} samples | "
          f"Malignant: {ucth_metadata['n_malignant']} | "
          f"Benign: {ucth_metadata['n_benign']}")

    coimbra_features, coimbra_labels, coimbra_metadata = load_coimbra()
    print(f"Coimbra  → {coimbra_metadata['n_samples']} samples | "
          f"Malignant: {coimbra_metadata['n_malignant']} | "
          f"Benign: {coimbra_metadata['n_benign']}")

    print("-" * 40)
    print(f"Total samples: {wisconsin_metadata['n_samples'] + ucth_metadata['n_samples'] + coimbra_metadata['n_samples']}")

    return {
        "wisconsin": (wisconsin_features, wisconsin_labels, wisconsin_metadata),
        "ucth":      (ucth_features, ucth_labels, ucth_metadata),
        "coimbra":   (coimbra_features, coimbra_labels, coimbra_metadata),
    }