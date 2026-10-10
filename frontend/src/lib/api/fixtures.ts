import type {
  Capability,
  ErrorCode,
  ErrorEnvelope,
  Plan,
  RunDetails,
  ServiceStatus,
} from '../../types/contract';

export const STATUS_FIXTURE: ServiceStatus = {
  state: 'ok',
  resets_at: '2026-10-10T00:00:00.000Z',
  limits: {
    max_rows: 200,
    max_cols: 50,
    max_cells: 10000,
    max_file_size_bytes: 1048576,
    max_turns: 15,
  },
  capacity: {
    active_runs: 1,
    daily_runs_remaining: 8,
  },
};

export const SESSION_CREATE_FIXTURE = {
  session_id: '018f2a9e-64d8-7b9c-8511-9a7b938f01aa',
  expires_at: '2026-10-10T22:00:00.000Z',
};

export const SESSION_DELETE_FIXTURE = {
  status: 'deleted',
  message: 'Session and ephemeral data deleted',
};

export const HEALTH_FIXTURE = {
  status: 'ok',
  version: '0.1.0',
  timestamp: '2026-10-09T22:00:00.000Z',
};

export const ERROR_FIXTURES: Record<ErrorCode, ErrorEnvelope> = {
  validation: {
    error: {
      code: 'validation',
      message: 'CSV column count exceeds limit of 50 columns (got 52).',
      request_id: 'req_val_01j7q34k89z2',
    },
  },
  unsupported: {
    error: {
      code: 'unsupported',
      message: 'Capability "reinforcement_learning" is not supported.',
      request_id: 'req_uns_01j7q34k89z3',
    },
  },
  pii_detected: {
    error: {
      code: 'pii_detected',
      message: 'Detected personal identifier patterns (SSN) in column "social_security_num".',
      request_id: 'req_pii_01j7q34k89z4',
    },
  },
  rate_limited: {
    error: {
      code: 'rate_limited',
      message: 'Client rate limit exceeded (12 requests / min limit).',
      retry_after_s: 15,
      request_id: 'req_rtl_01j7q34k89z5',
    },
  },
  queue_full: {
    error: {
      code: 'queue_full',
      message: 'Execution queue at capacity (5 concurrent runs). Try again shortly.',
      retry_after_s: 30,
      request_id: 'req_qfl_01j7q34k89z6',
    },
  },
  quota_gemini: {
    error: {
      code: 'quota_gemini',
      message: 'Daily Gemini API quota reached (20 requests/day). Resets at 00:00:00 UTC.',
      retry_after_s: 7200,
      request_id: 'req_qgm_01j7q34k89z7',
    },
  },
  quota_tabpfn: {
    error: {
      code: 'quota_tabpfn',
      message: 'Daily TabPFN token budget exhausted (5,000,000 tokens reached). Resets at 00:00:00 UTC.',
      retry_after_s: 7200,
      request_id: 'req_qtp_01j7q34k89z8',
    },
  },
  capacity_exhausted: {
    error: {
      code: 'capacity_exhausted',
      message: 'Global daily capacity limit of 100 runs reached.',
      retry_after_s: 10800,
      request_id: 'req_cap_01j7q34k89z9',
    },
  },
  kill_switch: {
    error: {
      code: 'kill_switch',
      message: 'Service is temporarily paused by administrator kill-switch.',
      request_id: 'req_ksw_01j7q34k89za',
    },
  },
  turn_limit: {
    error: {
      code: 'turn_limit',
      message: 'Session exceeded maximum limit of 15 conversational turns.',
      request_id: 'req_trn_01j7q34k89zb',
    },
  },
  backend_waking: {
    error: {
      code: 'backend_waking',
      message: 'Backend compute instance is spinning up. Retry in 10s.',
      retry_after_s: 10,
      request_id: 'req_bwk_01j7q34k89zc',
    },
  },
  upstream_unavailable: {
    error: {
      code: 'upstream_unavailable',
      message: 'Upstream Prior Labs TabPFN API unreachable (HTTP 502).',
      retry_after_s: 20,
      request_id: 'req_upv_01j7q34k89zd',
    },
  },
  internal: {
    error: {
      code: 'internal',
      message: 'Internal server error occurred.',
      request_id: 'req_int_01j7q34k89ze',
    },
  },
};

export const CHURN_PLAN: Plan = {
  plan_id: 'plan_churn_classification_v1',
  capability: 'classification',
  target: 'churned',
  features: ['tenure_months', 'monthly_charges', 'total_charges', 'age'],
  params: {
    split_strategy: 'stratified',
    holdout_fraction: 0.2,
    random_seed: 42,
    eval_metric: 'roc_auc',
    confidence_intervals: true,
  },
  estimate: {
    gemini_calls: 2,
    tabpfn_tokens: 10000,
    pct_of_daily_budget: 0.2,
  },
};

export const HOUSING_PLAN: Plan = {
  plan_id: 'plan_housing_regression_v1',
  capability: 'regression',
  target: 'median_house_value',
  features: ['median_income', 'housing_median_age', 'total_rooms', 'total_bedrooms', 'population'],
  params: {
    split_strategy: 'random',
    holdout_fraction: 0.2,
    random_seed: 42,
    eval_metric: 'rmse',
    confidence_intervals: true,
  },
  estimate: {
    gemini_calls: 2,
    tabpfn_tokens: 10000,
    pct_of_daily_budget: 0.2,
  },
};

export const AIR_PLAN: Plan = {
  plan_id: 'plan_air_passengers_forecast_v1',
  capability: 'forecasting',
  target: 'passengers',
  features: ['year', 'month_num'],
  params: {
    split_strategy: 'chronological',
    forecast_horizon: 12,
    confidence_intervals: true,
  },
  estimate: {
    gemini_calls: 2,
    tabpfn_tokens: 10000,
    pct_of_daily_budget: 0.2,
  },
};

export const CAPABILITY_RESULTS: Record<Capability, RunDetails> = {
  classification: {
    run_id: 'run_01_classification',
    plan_id: 'plan_churn_classification_v1',
    status: 'completed',
    blocks: [
      {
        type: 'metric',
        name: 'ROC-AUC',
        value: 0.885,
        baseline_value: 0.5,
        delta: 0.385,
        unit: 'auc',
        description: 'Holdout ROC-AUC vs naive majority-class baseline.',
        uncertainty: { lower: 0.84, upper: 0.93, confidence_level: 0.95 },
      },
      {
        type: 'metric',
        name: 'Accuracy',
        value: 0.857,
        baseline_value: 0.714,
        delta: 0.143,
        unit: 'ratio',
        description: 'Classification accuracy on 28 holdout test instances.',
        uncertainty: { lower: 0.72, upper: 0.94, confidence_level: 0.95 },
      },
      {
        type: 'chart',
        kind: 'reliability',
        title: 'Calibration Reliability Curve',
        description: 'Empirical accuracy plotted across predicted probability deciles.',
        data: {
          bins: [0.1, 0.3, 0.5, 0.7, 0.9],
          observed_frequencies: [0.08, 0.29, 0.52, 0.68, 0.91],
          sample_counts: [6, 7, 5, 5, 5],
        },
      },
      {
        type: 'chart',
        kind: 'importance',
        title: 'Feature Importance (Permutation)',
        description: 'Drop in ROC-AUC when feature column is randomly shuffled.',
        data: {
          features: ['tenure', 'monthly_charges', 'total_charges', 'age'],
          scores: [0.142, 0.089, 0.051, 0.012],
        },
      },
      {
        type: 'table',
        title: 'Holdout Confusion Matrix',
        description: 'Confusion matrix counts on holdout split.',
        table: {
          cols: ['actual_class', 'pred_no', 'pred_yes'],
          types: ['string', 'int', 'int'],
          rows: [
            ['Actual No', 18, 2],
            ['Actual Yes', 2, 6],
          ],
        },
      },
      {
        type: 'text',
        title: 'Grounded Narration',
        content:
          'TabPFN-3.5 attained an ROC-AUC of 0.885 (95% CI: 0.840–0.930), outperforming the majority baseline (0.500) by +0.385. Accuracy reached 85.7% vs 71.4% baseline. Tenure is the strongest predictor of customer churn.',
      },
      {
        type: 'download',
        filename: 'classification_predictions.csv',
        format: 'csv',
        description: 'Predictions with class probabilities for all holdout rows.',
        size_bytes: 1420,
        content: 'row_id,actual,pred,prob_churn\n0,0,0,0.12\n1,1,1,0.88\n2,0,0,0.05\n3,1,1,0.76',
      },
    ],
    summary: 'Completed classification run on 140 rows. Model achieved 0.885 ROC-AUC with +0.385 gain over baseline.',
  },

  regression: {
    run_id: 'run_02_regression',
    plan_id: 'plan_housing_regression_v1',
    status: 'completed',
    blocks: [
      {
        type: 'metric',
        name: 'RMSE',
        value: 4.12,
        baseline_value: 9.45,
        delta: -5.33,
        unit: 'k$',
        description: 'Root Mean Squared Error on holdout test set vs mean baseline.',
        uncertainty: { lower: 3.75, upper: 4.58, confidence_level: 0.95 },
      },
      {
        type: 'metric',
        name: 'R-squared',
        value: 0.812,
        baseline_value: 0.0,
        delta: 0.812,
        unit: 'r2',
        description: 'Variance explained by TabPFN regression model.',
      },
      {
        type: 'chart',
        kind: 'interval',
        title: 'Quantile Prediction Intervals (10% - 90%)',
        description: 'TabPFN predictive distribution quantiles compared against actual observed house prices.',
        data: {
          indices: [1, 2, 3, 4, 5],
          actuals: [24.0, 31.5, 18.2, 45.0, 22.8],
          q10: [20.5, 27.2, 15.1, 39.8, 19.4],
          q50: [23.8, 30.9, 17.8, 44.1, 22.3],
          q90: [27.9, 35.4, 21.0, 49.2, 26.1],
        },
      },
      {
        type: 'chart',
        kind: 'scatter',
        title: 'Predicted vs Actual Values',
        description: 'Holdout test predictions plotted along identity line.',
        data: {
          actual: [24.0, 31.5, 18.2, 45.0, 22.8],
          predicted: [23.8, 30.9, 17.8, 44.1, 22.3],
        },
      },
      {
        type: 'table',
        title: 'Holdout Evaluation Samples',
        description: 'Sample predictions with 80% credible intervals.',
        table: {
          cols: ['row_index', 'actual_price', 'predicted_mean', 'ci_lower_10', 'ci_upper_90'],
          types: ['int', 'float', 'float', 'float', 'float'],
          rows: [
            [1, 24.0, 23.8, 20.5, 27.9],
            [2, 31.5, 30.9, 27.2, 35.4],
            [3, 18.2, 17.8, 15.1, 21.0],
            [4, 45.0, 44.1, 39.8, 49.2],
            [5, 22.8, 22.3, 19.4, 26.1],
          ],
        },
      },
      {
        type: 'text',
        title: 'Grounded Narration',
        content:
          'TabPFN regression achieved an RMSE of 4.12k$ (95% CI: 3.75–4.58), reducing prediction error by 56% over the naive mean baseline. Median income accounted for 64% of predictive power.',
      },
      {
        type: 'download',
        filename: 'housing_predictions.csv',
        format: 'csv',
        description: 'Predicted median values with credible intervals.',
        size_bytes: 1850,
        content: 'row_id,actual,pred,ci_10,ci_90\n1,24.0,23.8,20.5,27.9\n2,31.5,30.9,27.2,35.4',
      },
    ],
    summary: 'Housing price regression completed on 100 rows. RMSE of 4.12k$ vs 9.45k$ baseline.',
  },

  forecasting: {
    run_id: 'run_03_forecasting',
    plan_id: 'plan_air_passengers_forecast_v1',
    status: 'completed',
    blocks: [
      {
        type: 'metric',
        name: 'Horizon RMSE',
        value: 18.4,
        baseline_value: 46.2,
        delta: -27.8,
        unit: 'passengers',
        description: 'Root Mean Squared Error over 12-month forward horizon vs last-known-value baseline.',
        uncertainty: { lower: 14.2, upper: 22.9, confidence_level: 0.95 },
      },
      {
        type: 'metric',
        name: 'MAPE',
        value: 4.1,
        baseline_value: 11.8,
        delta: -7.7,
        unit: 'percent',
        description: 'Mean Absolute Percentage Error on test horizon.',
      },
      {
        type: 'chart',
        kind: 'line',
        title: 'Historical Series and Forward Forecast',
        description: 'Historical passenger volume series joined with 12-month forward TabPFN predictions.',
        data: {
          x: ['1959-01', '1959-04', '1959-07', '1959-10', '1960-01', '1960-04', '1960-07', '1960-10'],
          historical: [360, 396, 548, 407, 417, null, null, null],
          forecast: [null, null, null, null, 417, 461, 622, 461],
          lower_80: [null, null, null, null, 390, 430, 580, 420],
          upper_80: [null, null, null, null, 444, 492, 664, 502],
        },
      },
      {
        type: 'table',
        title: 'Forward Forecast Horizon',
        description: 'Predicted periods with confidence bounds.',
        table: {
          cols: ['period', 'forecast_mean', 'lower_80', 'upper_80'],
          types: ['string', 'float', 'float', 'float'],
          rows: [
            ['1960-01', 417.0, 390.0, 444.0],
            ['1960-04', 461.0, 430.0, 492.0],
            ['1960-07', 622.0, 580.0, 664.0],
            ['1960-10', 461.0, 420.0, 502.0],
          ],
        },
      },
      {
        type: 'text',
        title: 'Grounded Narration',
        content:
          'TabPFN time series forecasting captured the summer passenger peak at 622 passengers (80% CI: 580–664). MAPE held at 4.1%, beating the seasonal naive baseline (11.8%).',
      },
      {
        type: 'download',
        filename: 'airline_forecast_12m.csv',
        format: 'csv',
        description: 'Forward 12-month passenger predictions with 80% uncertainty bounds.',
        size_bytes: 1100,
        content: 'period,forecast,lower_80,upper_80\n1960-01,417,390,444\n1960-04,461,430,492',
      },
    ],
    summary: 'Time series forecasting on 144 monthly points. 12-month forward horizon MAPE of 4.1%.',
  },

  anomaly_detection: {
    run_id: 'run_04_anomaly_detection',
    plan_id: 'plan_equipment_anomalies_v1',
    status: 'completed',
    blocks: [
      {
        type: 'metric',
        name: 'Anomalies Flagged',
        value: 4,
        baseline_value: 0,
        delta: 4,
        unit: 'count',
        description: 'Total instances identified with outlier probability > 0.95.',
      },
      {
        type: 'metric',
        name: 'Contamination Rate',
        value: 3.33,
        unit: 'percent',
        description: 'Percentage of dataset flagged as anomalous (4 out of 120 samples).',
      },
      {
        type: 'chart',
        kind: 'scatter',
        title: 'Anomaly Score Distribution',
        description: 'Negative log-likelihood score plotted against sensor telemetry.',
        data: {
          x: [0.12, 0.15, 0.18, 0.22, 0.85, 0.92],
          y: [1.2, 1.4, 1.8, 2.1, 8.4, 9.7],
          is_outlier: [false, false, false, false, true, true],
        },
      },
      {
        type: 'table',
        title: 'Detected Outlier Records',
        description: 'Top flagged anomalous sensor telemetry rows.',
        table: {
          cols: ['row_index', 'sensor_vibration', 'temperature', 'outlier_score'],
          types: ['int', 'float', 'float', 'float'],
          rows: [
            [48, 8.45, 112.4, 0.985],
            [92, 9.72, 118.1, 0.991],
            [104, 7.89, 105.3, 0.962],
            [118, 8.11, 109.8, 0.974],
          ],
        },
      },
      {
        type: 'text',
        title: 'Grounded Narration',
        content:
          'TabPFN prior-fitted density modeling isolated 4 severe anomalous telemetry rows (3.33% contamination rate) exhibiting concurrent abnormal vibration and temperature surges.',
      },
      {
        type: 'download',
        filename: 'flagged_anomalies.csv',
        format: 'csv',
        description: 'Full dataset with anomaly probability scores and outlier flags.',
        size_bytes: 2300,
        content: 'row_id,vibration,temp,score,outlier\n48,8.45,112.4,0.985,true\n92,9.72,118.1,0.991,true',
      },
    ],
    summary: 'Detected 4 anomalous records in 120 sensor readings.',
  },

  data_generation: {
    run_id: 'run_05_data_generation',
    plan_id: 'plan_synthetic_patients_v1',
    status: 'completed',
    blocks: [
      {
        type: 'metric',
        name: 'Wasserstein Distance',
        value: 0.042,
        unit: 'distance',
        description: "Earth Mover's Distance between real and synthetic marginals.",
      },
      {
        type: 'metric',
        name: 'Correlation Fidelity',
        value: 0.968,
        unit: 'cosine_similarity',
        description: 'Cosine similarity between real and synthetic feature correlation matrices.',
      },
      {
        type: 'chart',
        kind: 'bar',
        title: 'Marginal Distribution Comparison',
        description: 'Frequency alignment between real and synthetic cohorts.',
        data: {
          categories: ['Age <30', 'Age 30-50', 'Age >50'],
          real_percentages: [24.0, 52.0, 24.0],
          synthetic_percentages: [23.5, 51.8, 24.7],
        },
      },
      {
        type: 'table',
        title: 'Generated Synthetic Records Preview',
        description: '5 sampled rows from generated synthetic population.',
        table: {
          cols: ['patient_id', 'age', 'bmi', 'blood_pressure', 'diabetic'],
          types: ['string', 'int', 'float', 'int', 'boolean'],
          rows: [
            ['syn_01', 34, 22.4, 118, false],
            ['syn_02', 58, 29.1, 142, true],
            ['syn_03', 42, 25.8, 126, false],
            ['syn_04', 67, 31.4, 150, true],
            ['syn_05', 28, 21.0, 114, false],
          ],
        },
      },
      {
        type: 'text',
        title: 'Grounded Narration',
        content:
          'Generated 100 synthetic tabular instances matching training joint distributions. Correlation fidelity scored 0.968 with 0.042 mean Wasserstein distance.',
      },
      {
        type: 'download',
        filename: 'synthetic_cohort.csv',
        format: 'csv',
        description: '100 generated synthetic tabular records.',
        size_bytes: 4800,
        content: 'patient_id,age,bmi,bp,diabetic\nsyn_01,34,22.4,118,0\nsyn_02,58,29.1,142,1',
      },
    ],
    summary: 'Generated 100 synthetic records with 0.968 correlation fidelity.',
  },

  interpretability: {
    run_id: 'run_06_interpretability',
    plan_id: 'plan_medical_diagnostics_v1',
    status: 'completed',
    blocks: [
      {
        type: 'metric',
        name: 'Top Feature Influence',
        value: 0.245,
        unit: 'roc_auc_drop',
        description: 'Drop in ROC-AUC when Glucose Level is randomly permuted.',
      },
      {
        type: 'metric',
        name: 'Cumulative Top-3 Share',
        value: 78.4,
        unit: 'percent',
        description: 'Percentage of total permutation importance variance from top 3 features.',
      },
      {
        type: 'chart',
        kind: 'importance',
        title: 'Permutation Feature Importance',
        description: 'Validation ROC-AUC drop per feature across 50 permutations.',
        data: {
          features: ['glucose', 'insulin', 'bmi', 'age', 'pedigree'],
          scores: [0.245, 0.138, 0.092, 0.041, 0.028],
          std_dev: [0.018, 0.012, 0.009, 0.005, 0.004],
        },
      },
      {
        type: 'chart',
        kind: 'line',
        title: 'Partial Dependence: Glucose Level',
        description: 'Marginal effect of glucose on predicted probability.',
        data: {
          x: [80, 100, 120, 140, 160, 180],
          pdp_mean: [0.08, 0.14, 0.28, 0.58, 0.82, 0.94],
        },
      },
      {
        type: 'table',
        title: 'Feature Importance Summary Table',
        description: 'Ranked importance scores with statistical significance bounds.',
        table: {
          cols: ['rank', 'feature', 'roc_auc_drop', 'p_value'],
          types: ['int', 'string', 'float', 'float'],
          rows: [
            [1, 'glucose', 0.245, 0.0001],
            [2, 'insulin', 0.138, 0.0008],
            [3, 'bmi', 0.092, 0.0042],
            [4, 'age', 0.041, 0.031],
            [5, 'pedigree', 0.028, 0.084],
          ],
        },
      },
      {
        type: 'text',
        title: 'Grounded Narration',
        content:
          'Permutation importance confirms Glucose as the dominant diagnostic factor (drop: 0.245, p < 0.001), followed by Insulin (0.138). Partial dependence reveals a sharp non-linear risk escalation above 120 mg/dL.',
      },
      {
        type: 'download',
        filename: 'feature_importances.csv',
        format: 'csv',
        description: 'Full permutation importance results with p-values and standard deviations.',
        size_bytes: 840,
        content: 'rank,feature,roc_drop,p_val\n1,glucose,0.245,0.0001\n2,insulin,0.138,0.0008',
      },
    ],
    summary: 'Interpretability analysis completed. Glucose identified as top driver (0.245 ROC-AUC drop).',
  },
};

export const SAMPLE_CHURN_CSV = `customer_id,age,tenure_months,monthly_charges,total_charges,contract_type,tech_support,churned
CUST_0001,56,62,37.87,2520.37,Month-to-month,No,0
CUST_0002,69,37,56.64,2152.85,Month-to-month,Yes,0
CUST_0003,46,44,94.41,4404.07,Month-to-month,No,1
CUST_0004,32,35,92.08,3337.00,Month-to-month,Yes,1
CUST_0005,60,65,50.80,3350.45,Month-to-month,No,0
CUST_0006,25,47,74.24,3230.03,Month-to-month,No,1
CUST_0007,38,3,70.87,225.84,Month-to-month,Yes,1
CUST_0008,56,1,83.62,88.98,One year,No,1
CUST_0009,36,5,45.04,230.87,Month-to-month,Yes,1
CUST_0010,48,68,20.25,1422.35,Two year,No,0
CUST_0011,29,12,65.30,780.12,Month-to-month,No,0
CUST_0012,62,54,89.10,4812.50,One year,Yes,0
CUST_0013,41,2,79.40,158.80,Month-to-month,No,1
CUST_0014,53,40,49.95,2001.00,Two year,Yes,0
CUST_0015,31,18,55.20,993.60,Month-to-month,No,0`;

export const SAMPLE_HOUSING_CSV = `sold_date,median_income,housing_median_age,total_rooms,total_bedrooms,population,median_house_value
2023-01-19,5.279,37,3224,657,673,234.83
2023-01-21,9.607,50,2432,603,2493,317.25
2023-01-25,8.622,27,1303,330,523,308.71
2023-01-29,11.293,37,4596,936,1562,369.85
2023-01-31,6.853,27,4186,911,2524,308.10
2023-02-02,3.080,31,4219,984,2102,181.11
2023-02-06,9.432,20,1024,235,1152,334.18
2023-02-09,9.940,48,3711,812,362,351.42
2023-02-13,7.806,20,1598,335,1540,306.32
2023-02-17,4.112,42,2281,490,1204,215.60
2023-02-20,6.540,15,3890,720,1830,289.40
2023-02-24,3.890,35,1820,410,950,192.50
2023-02-27,8.230,22,2980,540,1410,318.90`;

export const SAMPLE_AIR_CSV = `date,year,month_num,passengers
1949-01-01,1949,1,112
1949-02-01,1949,2,118
1949-03-01,1949,3,132
1949-04-01,1949,4,129
1949-05-01,1949,5,121
1949-06-01,1949,6,135
1949-07-01,1949,7,148
1949-08-01,1949,8,148
1949-09-01,1949,9,136
1949-10-01,1949,10,119
1949-11-01,1949,11,104
1949-12-01,1949,12,118
1950-01-01,1950,1,115
1950-02-01,1950,2,126
1950-03-01,1950,3,141
1950-04-01,1950,4,135`;
