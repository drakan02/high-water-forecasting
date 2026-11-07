# P2 local resource-controlled run

Branch: `phase/P2-harmonic-baseline`. No phase commit was made.

## Resource finding

The first chronological attempt used UTide `conf_int=linear` and reached 3.40 GiB process-tree RSS in about 9 seconds. A 3 GiB watchdog sent SIGTERM before the system ran out of RAM; system available RAM remained about 7.17 GiB. This was a controlled stop, not an OOM kill. The confidence interval code forms additional weighted design-matrix temporaries and covariance matrices. P2 does not use confidence intervals in any reported output or in `reconstruct`.

Set UTide `conf_int=none` for both designs. UTide OLS harmonic coefficients are unaffected by the optional CI calculation. A new synthetic regression test compares the linear-CI and no-CI paths and confirms identical amplitudes and phases to numerical tolerance. With CI disabled, the real local fits completed well below the same 3 GiB RSS threshold.

## Fit results

| Design | Fit interval | Valid observations | Constituents | Hourly rows | H valid | A valid | Residual valid | Peak process-tree RSS |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Chronological | 1988-01-01 to 2004-12-31 | 123,271 | 68 | 8,760 | 8,759 | 8,760 | 8,759 | 1.41 GiB |
| Retrospective | 1988-01-01 to 2007-12-31 | 148,551 | 68 | 8,760 | 8,759 | 8,760 | 8,759 | 1.55 GiB |

The chronological output is `data/clean/p2_gauge_only/chronological_fit_through_2004/`; the retrospective output is `data/clean/p2_gauge_only/retrospective_1988_2007/`. Both retain A(t) over the full 2007 hourly grid and null H/residual where the observed minute-00 value is invalid. Final guarded reruns peaked at 1.41 GiB (chronological) and 1.55 GiB (retrospective); logs are `reports/p2_chronological_final_guarded.log` and `reports/p2_retrospective_final_guarded.log`. The initial controlled stop is recorded in `reports/p2_chronological_local_conf_linear_stopped.log`. Both now save `utide_reconstruction_state.json`; replaying A(t) from that state differs from the output Parquet by at most 2.7e-15 m.

Raw source SHA-256: `7a796fcb64215becd2fb429b75a48be5afcb392c613a7f54e509c36250e71bb8`.

Hourly output SHA-256:

- Chronological: `bbb2406b7ea326c78bc3670a56634493edc5db804f75032b2f1b05fe097b5511`
- Retrospective: `2aebf511b5ddee4b1cb879ba7b05fb7b3723a87263f86c22196cba74658eae3a`

The full pytest suite passed: 10 tests. Output schema/count checks passed; `git diff --check` passed. This is a gauge-only UTide analysis, not a surge hindcast, paper EHM equivalence claim, or Table 1b reproduction.
