# Snowball Title-only F1 結果（兩篇 paper）

說明：以下結果以 **title 正規化後 exact match** 計算（移除 `{}`、TeX 命令、標點，轉小寫）。

## Discrete Audio Tokens ("Discrete Audio Tokens: More Than a Survey")
- Oracle 來源：`target_papers/discrete_audio_tokens_more_than_a_survey/reference_oracle.jsonl`
- Oracle title 數：326

| Round | Retrieved | TP | Precision | Recall | F1 | 備註 |
| --- | --- | --- | --- | --- | --- | --- |
| round_01 | 25 | 12 | 0.480000 | 0.036810 | 0.068376 | |
| round_02 | 71 | 18 | 0.253521 | 0.055215 | 0.090680 | |
| round_03 | 131 | 30 | 0.229008 | 0.092025 | 0.131291 | |
| round_04 | 186 | 42 | 0.225806 | 0.128834 | 0.164062 | |
| round_05 | 203 | 44 | 0.216749 | 0.134969 | 0.166352 | |
| round_06 | 206 | 44 | 0.213592 | 0.134969 | 0.165414 | |
| round_07 | 207 | 45 | 0.217391 | 0.138037 | 0.168856 | |
| round_08 | 207 | 45 | 0.217391 | 0.138037 | 0.168856 | |
| round_09 | NA | NA | NA | NA | NA | round_09 目錄無 `final_included.json` |

## Spoken Language Models ("On The Landscape of Spoken Language Models: A Comprehensive Survey")
- Oracle 來源：`target_papers/on_the_landscape_of_spoken_language_models_a_comprehensive_survey/reference_oracle.jsonl`
- Oracle title 數：194

| Round | Retrieved | TP | Precision | Recall | F1 | 備註 |
| --- | --- | --- | --- | --- | --- | --- |
| round_01 | 64 | 15 | 0.234375 | 0.077320 | 0.116279 | |
| round_02 | 68 | 17 | 0.250000 | 0.087629 | 0.129771 | |
| round_03 | 70 | 17 | 0.242857 | 0.087629 | 0.128788 | |
| round_04 | 70 | 17 | 0.242857 | 0.087629 | 0.128788 | |
| round_05 | NA | NA | NA | NA | NA | round_05 目錄無 `final_included.json` |
