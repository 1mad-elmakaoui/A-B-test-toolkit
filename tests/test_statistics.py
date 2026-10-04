"""Unit tests for the statistical building blocks in src/analysis.py."""
import numpy as np
import pytest
from scipy import stats
from statsmodels.stats.proportion import confint_proportions_2indep, proportions_ztest

from src.analysis import (
    cuped_adjust, decide, required_sample_size, simulate_peeking, srm_check,
    two_proportion_ztest, welch_ttest,
)


class TestSRM:
    def test_balanced_split_passes(self):
        assert srm_check(25_000, 25_000)["passed"]

    def test_normal_random_noise_passes(self):
        rng = np.random.default_rng(0)
        n_control = rng.binomial(50_000, 0.5)
        assert srm_check(n_control, 50_000 - n_control)["passed"]

    def test_one_percent_imbalance_is_flagged(self):
        result = srm_check(25_500, 24_500)
        assert not result["passed"]
        assert result["p_value"] < 0.001

    def test_uneven_planned_split(self):
        assert srm_check(10_000, 40_000, expected_control_share=0.2)["passed"]
        assert not srm_check(25_000, 25_000, expected_control_share=0.2)["passed"]


class TestTwoProportionZTest:
    @pytest.mark.parametrize("counts", [
        (2470, 24971, 2758, 25029),
        (100, 1000, 130, 1000),
        (5000, 50000, 4900, 50000),
    ])
    def test_matches_statsmodels(self, counts):
        x_c, n_c, x_t, n_t = counts
        ours = two_proportion_ztest(x_c, n_c, x_t, n_t)

        z_sm, p_sm = proportions_ztest([x_t, x_c], [n_t, n_c])
        ci_sm = confint_proportions_2indep(x_t, n_t, x_c, n_c, method="wald", compare="diff")

        assert ours["z"] == pytest.approx(z_sm, rel=1e-9)
        assert ours["p_value"] == pytest.approx(p_sm, rel=1e-9)
        assert ours["ci_low"] == pytest.approx(ci_sm[0], rel=1e-9)
        assert ours["ci_high"] == pytest.approx(ci_sm[1], rel=1e-9)

    def test_aa_false_positive_rate_is_about_five_percent(self):
        """Run 4,000 A/A tests through our z-test: about 5% should come out 'significant'."""
        rng = np.random.default_rng(7)
        n = 20_000
        conv_a = rng.binomial(n, 0.10, size=4000)
        conv_b = rng.binomial(n, 0.10, size=4000)
        p_values = np.array([two_proportion_ztest(a, n, b, n)["p_value"] for a, b in zip(conv_a, conv_b)])
        assert 0.04 <= (p_values < 0.05).mean() <= 0.06


class TestPeeking:
    def test_single_look_holds_alpha(self):
        result = simulate_peeking(n_sims=10_000, seed=11)
        assert 0.04 <= result["fpr_fixed_horizon"] <= 0.06

    def test_daily_peeking_inflates_false_positives(self):
        result = simulate_peeking(n_sims=10_000, seed=11)
        assert result["fpr_peeking"] > 0.15
        assert np.all(np.diff(result["fpr_by_look"]) >= 0)


class TestWelchAndCuped:
    def test_welch_matches_scipy(self):
        rng = np.random.default_rng(3)
        a, b = rng.exponential(5, 3000), rng.exponential(5.5, 2000)
        ours = welch_ttest(a, b)
        ref = stats.ttest_ind(b, a, equal_var=False)
        assert ours["p_value"] == pytest.approx(ref.pvalue)
        ci = ref.confidence_interval(0.95)
        assert ours["ci_low"] == pytest.approx(ci.low)
        assert ours["ci_high"] == pytest.approx(ci.high)

    def test_cuped_reduces_variance_and_keeps_mean(self):
        rng = np.random.default_rng(5)
        x = rng.normal(10, 2, 10_000)
        y = 3 + 0.8 * x + rng.normal(0, 1, 10_000)
        adjusted, theta = cuped_adjust(y, x)
        assert theta == pytest.approx(0.8, abs=0.02)
        assert adjusted.mean() == pytest.approx(y.mean())
        assert adjusted.var() < 0.3 * y.var()


class TestDesignAndDecision:
    def test_sample_size_matches_textbook_formula(self):
        p1, p2 = 0.10, 0.108
        z = stats.norm.ppf(0.975) + stats.norm.ppf(0.80)
        textbook = z ** 2 * (p1 * (1 - p1) + p2 * (1 - p2)) / (p2 - p1) ** 2
        assert required_sample_size(0.10, 0.08) == pytest.approx(textbook, rel=0.02)

    @pytest.mark.parametrize("args, expected", [
        ((0.001, 0.01, 0.02, 0.10, True), "Ship"),
        ((0.001, 0.01, 0.02, 0.10, False), "Invalid - SRM"),
        ((0.30, -0.01, 0.02, 0.05, True), "Inconclusive"),
        ((0.001, -0.02, -0.01, -0.10, True), "Don't ship"),
        ((0.001, 0.0001, 0.002, 0.01, True), "Not practically significant"),
    ])
    def test_decision_rules(self, args, expected):
        assert decide(*args) == expected
