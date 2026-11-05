# Option-pricing foundations

This note explains the Stage 2 European Black-Scholes and
Cox-Ross-Rubinstein (CRR) binomial implementations. They are educational
reference models, not market forecasts or investment advice.

## Inputs and units

- \(S_0\): current underlying price, strictly positive.
- \(K\): strike, strictly positive.
- \(T\): time to expiry in years; the app converts days using ACT/365.
- \(r\): continuously compounded annual risk-free rate, as a decimal.
- \(q\): continuously compounded annual dividend yield, as a decimal.
- \(\sigma\): annualized volatility, as a decimal.
- Calls and puts are supported. Black-Scholes is European-only.

The app's default inputs are synthetic values in `config/options.yaml`. They
are not a current SPY spot price, rate, dividend yield, or volatility.

## Black-Scholes

For \(\sigma > 0\), define

\[
d_1 = \frac{\ln(S_0/K) + (r-q+\sigma^2/2)T}{\sigma\sqrt{T}},
\qquad d_2 = d_1 - \sigma\sqrt{T}.
\]

With \(\Phi\) the standard normal cumulative distribution function,

\[
C = S_0 e^{-qT}\Phi(d_1) - K e^{-rT}\Phi(d_2),
\]
\[
P = K e^{-rT}\Phi(-d_2) - S_0 e^{-qT}\Phi(-d_1).
\]

At expiry the implementation returns intrinsic value. At zero volatility it
uses the discounted deterministic payoff rather than dividing by zero.

The model assumes lognormal underlying prices, constant volatility and rates,
continuous trading, and no market frictions. Real implied volatility varies
by strike and maturity; rates and dividends are not known with certainty.

## CRR binomial tree

For \(N\) equal time steps, let \(\Delta t=T/N\),
\[
u=e^{\sigma\sqrt{\Delta t}}, \quad d=u^{-1}, \quad
p=\frac{e^{(r-q)\Delta t}-d}{u-d}.
\]
The risk-neutral probability \(p\) must be in \([0,1]\). The code raises a
clear error outside those bounds; it does not clip the value to make a tree
appear valid.

At each node, the European value is the discounted expectation of the next
two node values. For an American option, the node value is the greater of
continuation value and immediate exercise value. The tree is a discrete
approximation, so its price can oscillate with the step count. The API caps
the number of steps to bound runtime.

When volatility is zero, European values use the same deterministic limit as
Black-Scholes. For American contracts, the implementation checks exercise
along the deterministic path.

## Saved option data

The local snapshot loader verifies schema version, supported provider and
underlying, retrieval-date consistency, expiration list, contract/side counts,
contract symbols, and the CSV's SHA-256 digest. The digest is useful for
detecting accidental changes while the manifest is unchanged; it is not
signed, so it does not prove authenticity or provider provenance. Quotes from
yfinance may be delayed, stale, revised, or unsynchronized. Stage 2 displays
validated rows but does not fit parameters to them.

## Learning checks

1. For a European contract, what should happen to the binomial price as the
   number of steps increases?
2. Why can an American put be worth more than a European put with the same
   contract terms?
3. If the binomial risk-neutral probability is outside \([0,1]\), why is
   clipping it a poor fix?
4. Which model inputs in the demo are synthetic, and why should they not be
   described as current market data?

## References

- Black, F. and Scholes, M. (1973), “The Pricing of Options and Corporate
  Liabilities,” *Journal of Political Economy*, 81(3), 637–654.
  <https://doi.org/10.1086/260062>
- Cox, J. C., Ross, S. A., and Rubinstein, M. (1979), “Option Pricing: A
  Simplified Approach,” *Journal of Financial Economics*, 7(3), 229–263.
  <https://doi.org/10.1016/0304-405X(79)90015-1>
