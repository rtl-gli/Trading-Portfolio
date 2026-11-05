# Gaussian hidden-Markov regime model

The regime page fits a Gaussian hidden Markov model to daily SPY, QQQ, TLT, or
GLD log returns. The model assumes a hidden state follows a Markov chain and
the return distribution depends on the current state:

$$
P(S_t=j\mid S_{t-1}=i)=A_{ij},\qquad
r_t\mid S_t=k\sim\mathcal{N}(\mu_k,\sigma_k^2).
$$

## Fit and chronological filtering

The first configured fraction of observations is used to estimate the state
means, variances, and transition probabilities by the Gaussian HMM EM
(Baum-Welch) algorithm. The implementation tries multiple deterministic
initialisations and selects the fit with the highest training-sample
log-likelihood. After fitting, parameters are frozen; observations are then
processed in time order with the forward algorithm. Non-monotone likelihood
steps are counted and shown rather than silently ignored.

The app reports the most likely state, filtered probabilities, a transition
matrix, and fitted daily return means and volatilities. State labels are
assigned in order of fitted variance. They are descriptive labels only, not
identified economic causes.

The fixed-parameter filtered probability at date *t* uses observations through
*t* and is suitable for studying real-time information flow. This is not a
walk-forward trading evaluation: parameters are estimated once on the early
training sample and never retrained. The displayed smoothed probabilities
come from the entire observed series and use future observations to revise
earlier states. They are explicitly separated in the UI and must not be used
as historical signals.

## Visuals and learning goals

- Shaded adjusted-price plot: most likely **filtered** state by date, with the
  chronological parameter-training cutoff.
- Filtered-probability plot: uncertainty about the current state, not just its
  most likely label.
- Separate optional smoothed-probability plot: demonstrates how later
  information changes the interpretation of earlier dates.
- Transition matrix and emission summaries: inspect persistence and whether
  the fitted states actually differ in volatility.

## Limitations

- Gaussian emissions may be a poor description of fat tails, jumps, or
  changing correlations.
- The number of states is chosen by the user; more states add flexibility and
  can overfit.
- EM can converge to local optima. Multiple starts help but do not prove a
  global optimum or model adequacy.
- State labels can switch between fits; sorting by volatility only makes
  display order more readable.
- A high-volatility state is not a crash prediction or an explanation of
  market causes.
- Provider prices may be revised, and the sample is subject to data-coverage
  and survivorship limitations. No transaction-cost-adjusted strategy result
  is reported.

Tests use a deterministic synthetic two-state process. They check probability
normalization, parameter ordering, chronological holdout handling, and that
changing future returns cannot change earlier filtered probabilities. They do
not claim the market has two true regimes.
