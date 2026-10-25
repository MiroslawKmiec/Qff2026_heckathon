"""Small, explicit fidelity kernels; no cloud access or fitted global state."""
import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC


class WineFeatures(BaseEstimator):
    """Training-only standardization, four PCs, then bounded angle coordinates."""
    def fit(self, X, y=None):
        self.scaler_ = StandardScaler().fit(X)
        self.pca_ = PCA(n_components=4, svd_solver="full").fit(self.scaler_.transform(X))
        self.pc_scaler_ = StandardScaler().fit(self.pca_.transform(self.scaler_.transform(X)))
        return self

    def transform(self, X):
        pcs = self.pca_.transform(self.scaler_.transform(X))
        return np.arctan(self.pc_scaler_.transform(pcs))

    def fit_transform(self, X, y=None):
        return self.fit(X, y).transform(X)


def feature_circuit(x, entangled=False, depth=1, scale=1.0):
    """RZZ angles depend on input, so they do not cancel from overlaps."""
    x = np.asarray(x) * scale
    qc = QuantumCircuit(len(x))
    for _ in range(depth):
        for i, angle in enumerate(x):
            qc.ry(float(angle), i)
            qc.rz(float(angle / 2), i)
        if entangled:
            for i in range(len(x) - 1):
                qc.rzz(float(x[i] * x[i + 1]), i, i + 1)
    return qc


def states(X, **settings):
    return np.asarray([Statevector.from_instruction(feature_circuit(x, **settings)).data for x in X])


def fidelity_kernel(left, right):
    return np.clip(np.abs(left.conj() @ right.T) ** 2, 0, 1)


def overlap_circuit(x, y, **settings):
    qc = feature_circuit(x, **settings)
    qc.barrier()
    qc.compose(feature_circuit(y, **settings).inverse(), inplace=True)
    qc.measure_all()
    return qc


class QuantumKernelSVC(ClassifierMixin, BaseEstimator):
    def __init__(self, C=1.0, entangled=False, depth=1, scale=1.0):
        self.C, self.entangled, self.depth, self.scale = C, entangled, depth, scale

    def settings(self):
        return dict(entangled=self.entangled, depth=self.depth, scale=self.scale)

    def fit(self, X, y):
        self.states_ = states(X, **self.settings())
        self.svc_ = SVC(C=self.C, kernel="precomputed").fit(fidelity_kernel(self.states_, self.states_), y)
        self.classes_ = self.svc_.classes_
        self.n_features_in_ = np.asarray(X).shape[1]
        return self

    def predict(self, X):
        return self.svc_.predict(fidelity_kernel(states(X, **self.settings()), self.states_))


def psd_features(train_kernel, test_kernel, tolerance=1e-8):
    """Training-only PSD projection with a consistent out-of-sample extension.

    Test labels and test-test similarities are never used. Negative/tiny training
    eigenmodes are dropped; test features use the SAME retained eigensystem.
    """
    values, vectors = np.linalg.eigh((train_kernel + train_kernel.T) / 2)
    keep = values > tolerance
    if not np.any(keep):
        raise ValueError("No positive kernel eigenmodes")
    root = np.sqrt(values[keep])
    return vectors[:, keep] * root, test_kernel @ vectors[:, keep] / root
