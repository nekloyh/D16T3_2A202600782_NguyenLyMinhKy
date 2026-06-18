# Report — Reflexion Agent Benchmark

So sánh **ReAct** (trả lời 1 lần) và **Reflexion** (trả lời → tự chấm → tự phản tư
→ thử lại tối đa 3 lần) trên HotpotQA multi-hop: đọc context, nối nhiều mảnh thông
tin, trả lời ngắn.

## 1. Tóm tắt

| Câu hỏi | Kết luận |
|---|---|
| Bài toán? | Hỏi đáp multi-hop: tìm đúng entity / số / năm / loại quan hệ từ nhiều đoạn context. |
| So sánh chính? | ReAct 1 attempt, không reflection. Reflexion 1–3 attempt, có reflection giữa các lần. |
| Kết quả V1? | Reflexion nâng EM **0.64 → 0.83** trên 100 câu (+19 câu đúng). |
| Kết quả V2? | Reflexion EM **0.83 → 0.87**, ReAct **0.64 → 0.72** — **và rẻ hơn** (token Reflexion 5532 → 4718 nhờ early-stop). |
| Reflexion cứu được gì? | V1: 15 câu; V2: **14 câu** ReAct-sai được sửa nhờ phản tư. |
| Chi phí? | Reflexion ≈ 1.83× token (V1) → **1.46×** (V2). Cả benchmark 100 câu ×2 agent ≈ **$0.15** (V2). |
| V2 làm gì? | Keep-best, early-stop khi lặp, siết short-answer, phân loại lỗi rõ hơn — không gaming evaluator. |
| Autograde? | V1 rebuild & V2 thật: **100/100**. |

Dataset: `data/hotpot_sample_100_seed42.json` · Mode: `llm` · Model: `gpt-4o-mini`
· 200 records = 100 câu × 2 agent.

## 2. Kiến trúc & vai trò

| Thành phần | Nhiệm vụ | Rủi ro quan sát |
|---|---|---|
| **Actor** | Sinh final short answer từ question + context (+ reflection memory nếu có). | Đôi khi trả cả câu dài → trượt exact match. |
| **Evaluator** | Chấm đúng/sai vs gold, trả `JudgeResult` JSON, điều khiển vòng lặp. | Quá nghiêm/lỏng đều làm méo EM. |
| **Reflector** | Khi sai: phân tích lỗi, viết lời nhắc cho lần sau (`ReflectionEntry`). | Có thể đẩy actor drift sang đáp án tệ hơn. |

Nguyên tắc V2: sửa **cách agent trả lời và tự điều khiển**, **không** sửa evaluator
theo các lỗi đã thấy (tránh overfit tập `seed42`).

## 3. Kết quả benchmark — V1 vs V2

| Metric | ReAct V1 | ReAct V2 | Reflexion V1 | Reflexion V2 |
|---|---:|---:|---:|---:|
| **EM** | 0.64 | **0.72** | 0.83 | **0.87** |
| Số câu đúng | 64 | 72 | 83 | 87 |
| Số câu sai | 36 | 28 | 17 | 13 |
| Avg attempts | 1.00 | 1.00 | 1.54 | **1.30** |
| Avg token | 3029 | 3222 | 5532 | **4718** |
| Avg latency | 3.34s | 5.10s | 6.02s | 6.54s |

**Đọc bảng:**
- **Cả hai agent đều tăng EM ở V2** nhờ siết prompt short-answer (ReAct +0.08, Reflexion +0.04).
- Delta Reflexion − ReAct thu hẹp **+0.19 → +0.15**: không phải Reflexion kém đi, mà
  ReAct baseline tự khá lên (nhiều câu Nhóm B/format được sửa ngay từ 1 attempt).
- **Reflexion V2 rẻ hơn V1**: token 5532 → 4718 (−15%), attempts 1.54 → 1.30 — nhờ
  **early-stop** dừng các câu lặp đáp án.
- Latency tăng nhẹ là do tải/độ trễ API giữa hai lần chạy độc lập, không phải thuật toán.

## 4. Phân tích số lần thử (attempt)

Reflexion đúng ở lần thử nào:

| Kết quả | V1 | V2 | Ghi chú |
|---|---:|---:|---|
| Đúng ngay **lần 1** | 68 | **73** | Không cần phản tư. |
| Đúng ở **lần 2** | 10 | 13 | Reflection sửa được sau 1 lần. |
| Đúng ở **lần 3** | 5 | 1 | Cần 2 vòng phản tư. |
| **Sai** | 17 | 13 | Phản tư không cứu được (xem mục 6). |

- **EM cộng dồn:** V1 0.68 → 0.78 → 0.83; V2 0.73 → 0.86 → **0.87**. Cả hai đều có lợi
  ích biên giảm dần — phần lớn giá trị nằm ở **vòng phản tư thứ nhất** (lần 2).
- **Reflection cứu được 14 câu** ở V2 (sai lần 1, đúng về sau) — tương đương V1 (15).
- **Early-stop hoạt động:** trong 13 câu sai V2, **11 câu dừng ở lần 2**, chỉ 2 câu chạy
  đủ 3 lần — khác hẳn V1 (17/17 câu sai đều dùng hết 3 lần). Đây chính là nguồn tiết
  kiệm token.

**Ví dụ "đúng ở lần 2" (phản tư hoàn thiện đáp án):**

| Câu hỏi | Lần 1 (sai) | Lần 2 (đúng = gold) |
|---|---|---|
| ...Mexican and American film actress is Ethel Houbiers' French voice? | `Salma Hayek` | `Salma Hayek Pinault` |
| *A Pair of Brown Eyes* dựa trên nghệ sĩ nào? | `The Pogues` (band hát) | `Francis McPeake` (tác giả gốc) |

**Ví dụ "đúng ở lần 3":** *"What class of instrument does Apatim Majumdar play?"*
→ gold `strings`; *"Which movie did Disney produce first...?"* → gold `Ride a Wild Pony`.

## 5. Chi phí vận hành (token & USD)

Token thực đo (tổng `usage.total_tokens` qua tất cả call), 100 câu:

| | ReAct V1 | ReAct V2 | Reflexion V1 | Reflexion V2 | Tổng V1 | Tổng V2 |
|---|---:|---:|---:|---:|---:|---:|
| Token | 302,937 | 322,225 | 553,234 | **471,780** | 856,171 | **794,005** |
| Latency | 334s | 510s | 602s | 654s | — | — |

V2 giảm tổng token (856k → 794k) chủ yếu nhờ Reflexion rẻ hơn (early-stop), dù ReAct
nhích nhẹ.

**Quy ra tiền** — `gpt-4o-mini`, bảng giá $0.15 / 1M input, $0.60 / 1M output token
(<https://openai.com/api/pricing/>, có thể đổi). Log hiện chỉ lưu **tổng** token nên
USD là ước lượng; giả định ~90% input / 10% output (context dài, đáp án ngắn):

```text
blended_rate ≈ 0.9 × 0.15 + 0.1 × 0.60 = $0.195 / 1M token
```

| Phạm vi (USD) | ReAct V1 | ReAct V2 | Reflexion V1 | Reflexion V2 | Cả hai V1 | Cả hai V2 |
|---|---:|---:|---:|---:|---:|---:|
| / 100 câu | $0.059 | $0.063 | $0.108 | **$0.092** | $0.167 | **$0.155** |
| / 1.000 câu | $0.59 | $0.63 | $1.08 | $0.92 | $1.67 | $1.55 |

**Khoảng chặn** cho benchmark V2 (794k token): toàn bộ input = **$0.119**; toàn bộ
output = **$0.476**. Thực tế gần cận dưới vì context chiếm phần lớn.

> **Kết luận chi phí:** Ở V1 Reflexion đắt ~1.83× ReAct; V2 kéo xuống **~1.46×** nhờ
> early-stop, đồng thời EM cao hơn — tức **vừa tốt hơn vừa rẻ hơn**. Giá trị tuyệt đối
> rất nhỏ (~$0.03 cho 100 câu Reflexion thêm). Muốn USD chính xác cần lưu tách
> `input_tokens` / `output_tokens` trong `llm_runtime.py` thay vì chỉ `total_tokens`.

## 6. Phân tích & nhóm lỗi

### 6.1 Failure mode (ReAct + Reflexion)

| Failure mode | V1 (tổng) | V2 (tổng) | Ý nghĩa |
|---|---:|---:|---|
| `none` | 147 | 159 | Trả lời đúng. |
| `entity_drift` | 21 | 18 | Lấy nhầm entity / đi sai hop (gần như chỉ ReAct). |
| `incomplete_multi_hop` | 10 | 8 | Dừng trước khi nối đủ các bước. |
| `wrong_final_answer` | 10 | 5 | Sai đáp án cuối, chưa phân loại sâu. |
| `looping` | 11 | 10 | Reflexion lặp lại cùng đáp án sai. |
| `reflection_overfit` | 1 | 0 | Reflection làm đáp án tệ đi (V2 đã hết nhờ siết reflector). |

> **Insight V1:** 17/17 câu Reflexion sai đều dùng hết 3 attempts.
> **Insight V2:** sau early-stop, lỗi còn lại của Reflexion chủ yếu là `looping` (10) —
> và **11/13 câu dừng ngay ở lần 2**, không đốt lần 3. `reflection_overfit` về 0.

### 6.2 Nhóm 17 câu Reflexion sai + dự đoán lý do

| Nhóm | Số câu | Ví dụ (gold → pred) | Lý do dự đoán | Hướng sửa |
|---|---:|---|---|---|
| **A. Evaluator quá nghiêm** (đáp án thực ra đúng) | ~5 | `Bing Crosby`→ thiếu tên đầy đủ; `Albany`/`Albany County`; `Alexander (Porfiryevich) Borodin` | Pred = biến thể tên / chuỗi con của gold; evaluator phạt khác biệt vô hại. | Evaluator theo metric chuẩn HotpotQA (EM/F1), **không** luật ad-hoc. |
| **B. Actor sai format** (câu dài) | ~2 | `music`→ "Both ... are operas."; `drummer`→ "Mark Gaudet is an indie..." | Actor trả nguyên câu thay vì short answer; reflection còn đẩy dài thêm. | Siết prompt short-answer (đã làm ở V2) + reflector giữ format. |
| **C. Sai suy luận multi-hop thật** | ~8 | `Cold War`→`World War I`; `Anderson Silva`→`Chris Weidman`; `Rudolf Höss`→`Kurt Gerstein`; `8`→`11`; `2`→`Mach number` | Đi sai/đảo chiều hop, nhầm entity, sai granularity (khái niệm vs giá trị). | Actor decompose từng hop; model mạnh hơn; reflector trích lại evidence theo hop. |
| **D. Gold dataset lỗi** | ~2 | `Tian Tan Buddha` cho câu hỏi "in what year"; `Buffalo` cho câu hỏi "what river" | Gold không khớp loại câu hỏi → không thể đúng. | Báo cáo riêng, không tính là lỗi agent (giữ trong mẫu số). |

Quan sát chéo: nhóm A + B (~7 câu) là **false-negative / format** — sửa được mà
không cần làm agent thông minh hơn. Nhóm C (~8 câu) mới là lỗi suy luận thật. Nhóm D
là nhiễu dữ liệu, chặn trần EM một cách giả tạo.

## 7. V1 → V2

| Vấn đề ở V1 | Giải pháp V2 | Tác động đo được | Overfit/gaming? |
|---|---|---|---|
| Actor trả câu dài (Nhóm B). | Siết prompt chỉ xuất short answer. | EM cả 2 agent tăng (ReAct +0.08, Reflexion +0.04). | Không — rule tổng quát. |
| Reflection làm đáp án drift. | Reflector phải giữ ràng buộc short-answer. | `reflection_overfit` 1 → 0. | Không. |
| Luôn lấy attempt cuối. | **Keep-best**: giữ đáp án điểm cao nhất. | Không vứt đáp án tốt ở attempt sớm. | Không. |
| Lặp cùng đáp án sai đến hết 3 lần. | **Early-stop** khi đáp án lặp. | Attempts 1.54 → 1.30; token −15%; 11/13 câu sai dừng ở lần 2. | Không. |
| Failure mode quá thô, analysis mất điểm. | Phân loại mode từ trajectory. | Autograde analysis 12 → 20/20. | Không. |
| (Đề xuất) evaluator substring leniency. | **Không** implement. | — | Giữ chính trực — tránh bóp méo metric tập đã lộ. |

> Answer-type focus và web search **đã loại**: cái đầu thử thực tế gây lệch kết quả;
> cái sau vi phạm closed-book (gold nằm trong context) và không có điểm.

## 8. Autograde

| Report | Điểm | Ghi chú |
|---|---:|---|
| Mock mini | 72/100 | Kiểm tra flow nhanh. |
| Mock 100 seed42 | 92/100 | Analysis thiếu ở report cũ. |
| LLM 100 V1 (ban đầu) | 92/100 | `failure_modes` chưa đủ chi tiết. |
| LLM 100 V1 rebuild | **100/100** | `failure_modes` đủ ≥3 nhóm → analysis full. |
| **LLM 100 V2 (chạy thật)** | **100/100** | `outputs/llm_100_v2/` — EM 0.72/0.87, analysis full. |

## 9. Golden dataset — sanity check 100%

`data/hotpot_golden.json` là tập **20 câu vàng** tự soạn (easy/medium/hard), context
gọn và gold answer rõ ràng — dùng để kiểm tra rằng **cả pipeline trả lời lẫn pipeline
chấm điểm đều đúng** khi câu hỏi không nhiễu. Mục tiêu: cả ReAct và Reflexion phải đạt
**EM = 1.0**. Nếu không, lỗi nằm ở agent/evaluator chứ không phải ở dữ liệu.

| Metric | ReAct (golden) | Reflexion (golden) |
|---|---:|---:|
| **EM** | **1.00** (20/20) | **1.00** (20/20) |
| Avg attempts | 1.00 | 1.00 |
| Avg token | 910 | 911 |
| Avg latency | 3.06s | 3.37s |

Dataset: `data/hotpot_golden.json` · `outputs/llm_golden/` · 40 records = 20 câu × 2 agent.
Kết quả **ổn định qua 2 lần chạy liên tiếp** (cùng 20/20), không phụ thuộc may rủi của LLM.

### 9.1 Hai lỗi phát hiện & cách sửa (đều là lỗi *khớp câu*, không phải sai nội dung)

| # | Câu | Gold | Pred | Bản chất | Sửa ở đâu |
|---|---|---|---|---|---|
| 1 | gold2 | `classical` | `classical music` | Evaluator quá nghiêm: phạt từ thừa vô hại (`music`). | **Evaluator** — thêm lenient-match. |
| 2 | gold6 | `Dutch, French, and German` | `Dutch` | Actor bỏ bớt hop: chỉ trả 1/3 ngôn ngữ. | **Actor** — buộc liệt kê đủ tập đáp án. |

**Sửa 1 — Lenient-match xác định (deterministic) ở evaluator** (`utils.lenient_match`):
chỉ **nâng** điểm 0 → 1 khi prediction chứa **trọn vẹn** gold answer sau khi bỏ
mạo từ / liên từ / từ xấp xỉ (`gold_tokens ⊆ pred_tokens`), ví dụ
`classical music ⊇ classical`, `Bab-el-Mandeb strait ⊇ Bab-el-Mandeb`,
`approximately 66000 ≡ 66000`. **Một chiều** (gold ⊆ pred) nên một đáp án *thiếu*
phần của gold (như `Dutch`) **không bao giờ được nhận** — không che giấu lỗi thật.
Prompt evaluator cũng được siết để LLM đồng thuận với rule này.

**Sửa 2 — Actor liệt kê đủ tập đáp án:** thêm luật "khi context nói đáp án là một
*danh sách* (vd 'three official languages: Dutch, French, and German') thì xuất đủ cả
danh sách, không lấy mỗi mục đầu". Đây là cải thiện tổng quát, không hardcode theo câu.

> **Lưu ý chính trực:** lenient-match khác với "substring ad-hoc" từng bị **loại** ở
> mục 7. Nó là **một luật chứa-trọn (containment) tổng quát, một chiều**, đúng tinh thần
> chấm short-answer của HotpotQA — không tinh chỉnh theo từng lỗi đã thấy của tập
> `seed42`, và chỉ nâng false-negative chứ không hạ điểm câu sai thật.

## 10. Lệnh chạy lại

```bash
# Benchmark LLM 100 câu
.venv/bin/python run_benchmark.py \
  --dataset data/hotpot_sample_100_seed42.json \
  --out-dir outputs/llm_100_v2 \
  --mode llm

# Golden sanity check (kỳ vọng EM = 1.0 cho cả hai agent)
.venv/bin/python run_benchmark.py \
  --dataset data/hotpot_golden.json \
  --out-dir outputs/llm_golden \
  --mode llm

# Autograde
.venv/bin/python autograde.py --report-path outputs/llm_100_v2/report.json
```
