# Network dashboard visuals

## 1. Network score overview

Filters: port, period, and model view. Cards show the paired peak count, UTide and ECM MAE/RMSE, and 2010 QC coverage. All-port scores are pooled from the paired peak rows, excluding the two paper-specified ECM exclusions.

## 2. Source quality and model scores

The QC panel displays valid, present, and expected exact-hour samples by port for 2010. The score chart shows MAE by paper port number; paired view hides UTide-only values for ports without ECM so the model comparison is not mixed with a different sample.

## 3. Event forecast and lag trace

For the selected port and period, compare observed H, UTide A, and ECM total-H at high-water events. A detail table displays event ID/time, issue origin, and N−2/N−4/N−6 residual predictors. Rows without a forecast or lag record remain blank.

## 4. Model × port × period × target matrix

The score table retains both model rows per port-period, including `NOT_APPLICABLE_PER_PAPER`, zero-pair rows and low-coverage stations. Retrospective 2006–2009 is in-sample; 2010 is held out. Target labels remain total observed water level, gauge-only.
