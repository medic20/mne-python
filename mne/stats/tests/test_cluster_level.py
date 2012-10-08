import numpy as np
from numpy.testing import assert_equal, assert_array_equal
from nose.tools import assert_true
import mne.stats as mnestats
from mne.stats.cluster_level import permutation_cluster_test, \
                                    permutation_cluster_1samp_test
from scipy import stats, linalg, sparse

noiselevel = 20

normfactor = np.hanning(20).sum()

rng = np.random.RandomState(42)
condition1 = rng.randn(40, 350) * noiselevel
for c in condition1:
    c[:] = np.convolve(c, np.hanning(20), mode="same") / normfactor

condition2 = rng.randn(33, 350) * noiselevel
for c in condition2:
    c[:] = np.convolve(c, np.hanning(20), mode="same") / normfactor

pseudoekp = 5 * np.hanning(150)[None, :]
condition1[:, 100:250] += pseudoekp
condition2[:, 100:250] -= pseudoekp


def test_cluster_permutation_test():
    """Test cluster level permutations tests."""
    T_obs, clusters, cluster_p_values, hist = permutation_cluster_test(
                                [condition1, condition2], n_permutations=500,
                                tail=1, verbose=0)
    assert_equal(np.sum(cluster_p_values < 0.05), 1)

    T_obs, clusters, cluster_p_values, hist = permutation_cluster_test(
                                [condition1, condition2], n_permutations=500,
                                tail=0, verbose=0)
    assert_equal(np.sum(cluster_p_values < 0.05), 1)


def test_cluster_permutation_t_test():
    """Test cluster level permutations T-test."""
    my_condition1 = condition1[:, :, None]  # to test 2D also
    T_obs, clusters, cluster_p_values, hist = permutation_cluster_1samp_test(
                                my_condition1, n_permutations=500, tail=0,
                                verbose=0)
    assert_equal(np.sum(cluster_p_values < 0.05), 1)

    T_obs_pos, c_1, cluster_p_values_pos, _ = permutation_cluster_1samp_test(
                                my_condition1, n_permutations=500, tail=1,
                                threshold=1.67, verbose=0)

    T_obs_neg, c_2, cluster_p_values_neg, _ = permutation_cluster_1samp_test(
                                -my_condition1, n_permutations=500, tail=-1,
                                threshold=-1.67, verbose=0)
    assert_array_equal(T_obs_pos, -T_obs_neg)
    assert_array_equal(cluster_p_values_pos < 0.05,
                       cluster_p_values_neg < 0.05)
    # make sure that everything that should have been clustered was
    assert_array_equal(np.where(np.any(np.array(c_1), axis=0))[0],
                       np.where(ttest_1samp(my_condition1) > 1.67)[0])


def test_cluster_permutation_t_test_with_connectivity():
    """Test cluster level permutations T-test with connectivity matrix."""
    try:
        try:
            from sklearn.feature_extraction.image import grid_to_graph
        except ImportError:
            from scikits.learn.feature_extraction.image import grid_to_graph
    except ImportError:
        return

    out = permutation_cluster_1samp_test(condition1, n_permutations=500,
                                         verbose=0)
    connectivity = grid_to_graph(1, condition1.shape[1])
    out_connectivity = permutation_cluster_1samp_test(condition1,
                             n_permutations=500, connectivity=connectivity,
                             verbose=0)

    assert_array_equal(out[0], out_connectivity[0])
    for a, b in zip(out_connectivity[1], out[1]):
        assert_true(np.sum(out[0][a]) == np.sum(out[0][b]))
        assert_true(np.all(a[b]))

    # test spatio-temporal with no time connectivity (repeat spatial pattern)
    connectivity_2 = sparse.coo_matrix(linalg.block_diag(connectivity.todense(),
                                                         connectivity.todense()))
    condition1_2 = np.concatenate((condition1,
                                   condition1), axis=1)

    out_connectivity_2 = permutation_cluster_1samp_test(condition1_2,
                               n_permutations=500, connectivity=connectivity_2,
                               verbose=0)
    # make sure we were operating on the same values
    split = len(out[0])
    assert_array_equal(out[0], out_connectivity_2[0][:split])
    assert_array_equal(out[0], out_connectivity_2[0][split:])

    # make sure we really got 2x the number of original clusters
    n_clust_orig = len(out[1])
    assert_true(len(out_connectivity_2[1]) == 2 * n_clust_orig)

    # Make sure that we got the old ones back
    n_pts = condition1.shape[1]
    data_1 = set([np.sum(out[0][b[:n_pts]]) for b in out[1]])
    data_2 = set([np.sum(out_connectivity_2[0][a[:n_pts]]) for a in
        out_connectivity_2[1][:]])
    assert_true(len(data_1.intersection(data_2)) == len(data_1))

    # now use the other algorithm
    condition1_3 = np.reshape(condition1_2, (40, 350, 2))
    out_connectivity_3 = mnestats.spatio_temporal_cluster_test(condition1_3,
                               n_permutations=500, connectivity=connectivity,
                               verbose=0, max_tstep=0, threshold=1.67)
    # make sure we were operating on the same values
    split = len(out[0])
    assert_array_equal(out[0], out_connectivity_3[0][:split])
    assert_array_equal(out[0], out_connectivity_3[0][split:])

    # make sure we really got 2x the number of original clusters
    assert_true(len(out_connectivity_3[1]) == 2 * n_clust_orig)

    # Make sure that we got the old ones back
    data_1 = set([np.sum(out[0][b[:n_pts]]) for b in out[1]])
    data_2 = set([np.sum(out_connectivity_3[0][a[:n_pts]]) for a in
        out_connectivity_2[1][:]])
    assert_true(len(data_1.intersection(data_2)) == len(data_1))


def ttest_1samp(X):
    """Returns T-values
    """
    T, _ = stats.ttest_1samp(X, 0)
    return T