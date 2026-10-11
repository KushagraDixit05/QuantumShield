B = 1.5963 (||Δ||), seeds = [0, 1, 2, 3, 4], final-round test accuracy, mean ± std (population std); diverged runs (int64 range exceeded) score 0.0

| attack | fedavg | norm_filter | median | norm-check rejections (malicious / benign, of all client-rounds) |
|---|---|---|---|---|
| none | 0.9421 ± 0.0145 | 0.9421 ± 0.0145 | 0.9426 ± 0.0156 | 0/50 / 0/200 |
| scaled | 0.0000 ± 0.0000 (diverged 5/5) | 0.9376 ± 0.0165 | 0.9443 ± 0.0165 | 50/50 / 0/200 |
| sign_flip | 0.9075 ± 0.0175 | 0.9075 ± 0.0175 | 0.9253 ± 0.0154 | 0/50 / 0/200 |
| label_flip | 0.9253 ± 0.0131 | 0.9253 ± 0.0131 | 0.9331 ± 0.0163 | 0/50 / 0/200 |
| replay | 0.9265 ± 0.0189 | 0.9265 ± 0.0189 | 0.9348 ± 0.0182 | 0/50 / 0/200 |
