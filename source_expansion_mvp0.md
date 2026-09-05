# DANH MỤC NGUỒN DỮ LIỆU NGOÀI — MARKET INSIGHTS AGENT MVP0

*Tài liệu handoff cho DA (Bách) — phạm vi: agent kéo dữ liệu phục vụ phần Competitor & Market Analysis của Annual Planning*

**Phiên bản 2.8 — 04/09/2026** (bản 1.0 ngày 26/08/2026) — CVM, RBG. Tuân thủ spec Market Insights Agent v3.1 (sheet 04 whitelist, sheet 08 exclusions) và BRD 21/08/2026.

---

## 1. Mục đích và phạm vi MVP0

MVP0 chỉ làm một việc: kéo và lưu trữ toàn bộ dữ liệu ngoài cần thiết để tái tạo 4 nội dung của phần Competitor & Market Analysis trong Annual Planning:

1. Benchmark định lượng top 20 ngân hàng theo tổng tài sản (số liệu BCTC 30/06/2026), chia 2 nhóm:
   - **Nhóm A**: 3 ngân hàng quốc doanh niêm yết (BIDV, VietinBank, VCB) và 5 đối thủ trực tiếp phân khúc bán lẻ (MBB, VPBank, ACB, TPBank, VIB); TCB đứng thứ 7, là mốc đối chiếu.
   - **Nhóm B**: 7 ngân hàng kế tiếp theo quy mô (HDBank, SHB, LPBank, MSB, SeABank, OCB, ABBank).

   **DANH SÁCH CHỐT: 15 đối thủ + TCB**, dùng thống nhất cho mọi lớp và mọi tab.

   Loại khỏi danh sách:
   - Ngân hàng đang tái cấu trúc, số liệu biến động mạnh (Sacombank, Eximbank)
   - Ngân hàng chuyển giao bắt buộc không công bố BCTC công khai (MBV, VOBank, Vikki, VCBNeo)
   - Ngân hàng không có chương trình phân hạng khách hàng công bố chính thức nên không benchmark được CVP theo hạng (Agribank, Bac A Bank, Nam A Bank)

   Nhóm A kéo đủ 4 lớp; Nhóm B kéo Lớp 1 và Lớp 3, Lớp 2 chỉ quét trang tin và khuyến mại.

2. Quét CVP, offering và mô hình bán hàng theo phân khúc
3. Hồ sơ chiến lược từng ngân hàng
4. Các yếu tố vĩ mô, chính phủ, PEST

MVP0 không phân tích, không viết báo cáo. Mỗi bản ghi kéo về phải lưu kèm metadata: mã nguồn, URL, kỳ tham chiếu, ngày lấy, cơ sở số liệu (riêng lẻ hay hợp nhất), nhãn actual/proxy.

**Demo đạt khi**: chạy trọn một kỳ kéo dữ liệu cho cả 4 lớp, kho raw đầy đủ metadata, log nguồn lỗi, không có bản ghi nào từ domain cấm. Sau demo mới thiết kế MVP1.

---

## 2. Quy tắc phân loại vai trò nguồn (bắt buộc đọc trước khi cấu hình)

Mọi nguồn trong danh mục này thuộc đúng một trong bốn vai trò. Agent xử lý khác nhau theo vai trò, không tự suy diễn:

| Vai trò | Định nghĩa và cách xử lý |
|---|---|
| **Trích dẫn** | Nguồn công bố chính thức (cơ quan nhà nước, chính ngân hàng, tổ chức đa phương, tạp chí whitelist). Agent nạp, lưu, và số liệu từ đây được trích dẫn trong báo cáo sau này. Tuân thủ R-F02: mọi bản ghi có mã nguồn, kỳ tham chiếu, ngày lấy, link. |
| **Aggregator** | Kho trung gian chứa tài liệu gốc chính thức (ví dụ Vietstock tab Tải tài liệu chứa BCTC, nghị quyết ĐHCĐ do ngân hàng phát hành). Agent được dùng làm đường tải, nhưng nguồn ghi trong metadata là tài liệu gốc của ngân hàng, không phải trang aggregator. Không nạp bài viết tin tức của các trang này. |
| **Tín hiệu dò** | Báo chuyên ngành và tín hiệu thị trường. Agent không nạp làm dữ liệu, không trích dẫn số liệu. Ở MVP0, việc dò tín hiệu từ nhóm này là thao tác thủ công của con người ngoài hệ thống; số liệu phát hiện được phải truy về nguồn gốc trong nhóm Trích dẫn trước khi vào kho. |
| **Ngoài scope** | Chỉ số không tồn tại nguồn công bố chính thức bên ngoài. Agent không kéo. Dữ liệu lấy từ nguồn nội bộ TCB và nạp tay qua đường data/manual nếu cần, gắn nhãn nguồn nội bộ. |

**Domain cấm tuyệt đối theo sheet 08** (agent từ chối nạp và trích dẫn, vi phạm là FAIL kỳ theo R-G02): vnexpress.net, dantri.com.vn, tuoitre.vn, thanhnien.vn, facebook.com, tiktok.com, cafef.vn. Ngoài ra cấm mạng xã hội, diễn đàn đầu tư, tin đồn đối thủ, số liệu không rõ kỳ tham chiếu (R-G03).

---

## 3. Lớp 1 — Benchmark định lượng 15 đối thủ và TCB

### 3.1. Chỉ số cần kéo

| Chỉ số | Định nghĩa lấy số | Lưu ý |
|---|---|---|
| Tăng trưởng CASA lũy kế (YTD/9M) | Số dư tiền gửi không kỳ hạn KHCN từ thuyết minh BCTC quý hoặc investor deck; tính tăng trưởng so đầu năm | Ưu tiên số retail; thiếu thì dùng toàn hàng và gắn nhãn proxy |
| Tỷ lệ CASA (%CASA) | CASA trên tổng huy động KHCN | TCB, VCB, MBB, ACB công bố quý; BIDV chỉ có theo năm |
| Tăng trưởng huy động (TD + CD) | Tiền gửi có kỳ hạn và chứng chỉ tiền gửi, tách khỏi CASA | Từ thuyết minh tiền gửi khách hàng trong BCTC |
| Tăng trưởng tín dụng | Dư nợ cho vay KHCN nếu công bố; không thì toàn hàng | Ghi rõ cơ sở riêng lẻ hay hợp nhất trong metadata |
| Banca APE 9M | Không kéo. Nguồn: báo cáo Hiệp hội Bảo hiểm Việt Nam (IAV) do Head of Insurance nhận định kỳ, nạp tay (mục 3.4) | Agent không quét, không crawl iav.vn; số theo ngân hàng và tổng thị trường đều lấy từ báo cáo IAV nội bộ |

### 3.2. Nguồn chính thức từng ngân hàng (vai trò: Trích dẫn)

| Nguồn | Vai trò | URL | Dữ liệu kéo | Tần suất | Truy cập và ghi chú |
|---|---|---|---|---|---|
| Techcombank (TCB) | Trích dẫn | techcombank.com/en/investors (mục financial-statements-vas, financial-statements-ifrs, investor-presentations, annual-report) | BCTC quý VAS/IFRS, deck IR quý có tách CASA retail, tín dụng theo phân khúc RBG/BB/WB | Quý | PDF mở, URL tĩnh dạng /content/dam/..., crawl được. Deck tiếng Anh ra khoảng 20-30 ngày sau kỳ. Công bố tốt nhất nhóm |
| Vietcombank (VCB) | Trích dẫn | portal.vietcombank.com.vn/Investors (bản tiếng Anh: /en-us/Investors) | BCTC quý, deck IR tiếng Anh, tỷ lệ CASA, tách bán buôn và bán lẻ | Quý | Portal Oracle WebCenter, tham số aspx ItemID, thỉnh thoảng timeout; crawler cần retry |
| BIDV (BID) | Trích dẫn | bidv.com.vn/vn/quan-he-nha-dau-tu/bao-cao-va-tai-lieu/ (BCTC, báo cáo thường niên) | BCTC quý; tách retail và CASA chỉ xuất hiện trong báo cáo thường niên | Quý (BCTC), Năm (chi tiết) | KHÔNG có deck IR quý chuẩn hóa. Với chỉ số quý dùng số toàn hàng và bắt buộc gắn nhãn proxy |
| MB Bank (MBB) | Trích dẫn | mbbank.com.vn/Investor/thong-bao-nha-dau-tu | BCTC quý, tài liệu hợp analyst quý, tỷ lệ CASA | Quý | Điều hướng tiếng Việt là chính; crawl mức trung bình |
| ACB | Trích dẫn | acb.com.vn/en/investors (financial-statements, annual-report) | BCTC tiếng Anh, tài liệu IR quý về CASA, NIM, tăng trưởng tín dụng; cơ cấu cho vay và huy động cá nhân | Quý | PDF và HTML mở; có tách công ty con riêng |
| VietinBank (CTG) | Trích dẫn | investor.vietinbank.vn/vi/financialstatements2.aspx (BCTC); /vi/periodicreports.aspx (công bố định kỳ); /en/annualreports.aspx (BCTN) | BCTC quý hợp nhất và riêng lẻ; tài liệu kết quả kinh doanh; BCTN; tài liệu ĐHCĐ | Quý | Website IR mới ra mắt 01/2026, .aspx, HTML mở, crawl được. Tách bán lẻ và CASA chủ yếu ở tài liệu KQKD và BCTN; trang có ghi chú số liệu bên thứ ba, chỉ kéo file PDF do ngân hàng phát hành |
| VPBank (VPB) | Trích dẫn | vpbank.com.vn/quan-he-nha-dau-tu/bao-cao-tai-chinh; /quan-he-nha-dau-tu/dai-hoi-co-dong; mục Tài liệu dành cho nhà đầu tư (bản tiếng Anh /en/) | BCTC quý hợp nhất và riêng lẻ; deck IR quý; tài liệu ĐHCĐ; báo cáo phát triển bền vững | Quý | HTML mở, crawl được. Hợp nhất gồm FE Credit nên dư nợ và CASA bán lẻ phải tách số ngân hàng mẹ (riêng lẻ), ghi cơ sở trong metadata |
| TPBank (TPB) | Trích dẫn | tpb.vn/nha-dau-tu/bao-cao-tai-chinh; tpb.vn/nha-dau-tu/bao-cao-thuong-nien; tpb.vn/nha-dau-tu/dai-hoi-dong-co-dong | BCTC quý kèm giải trình; BCTN; tài liệu ĐHCĐ | Quý | Trang HTML mở, lọc theo năm; PDF qua link động /wps/wcm/connect (WebSphere). Ưu tiên benchmark app và thẻ ở Lớp 2; Lớp 1 lấy CASA và tín dụng toàn hàng |
| VIB | Trích dẫn | vib.com.vn/vn/nha-dau-tu (Kết quả kinh doanh, Báo cáo thường niên, Thông tin cổ đông, Công bố thông tin khác) | BCTC quý hợp nhất; tài liệu KQKD quý; BCTN; tài liệu ĐHCĐ | Quý | HTML mở; PDF qua link động /wps/wcm/connect (WebSphere). VIB công bố cơ cấu cho vay bán lẻ khá rõ trong tài liệu KQKD; thẻ TD là trọng tâm benchmark Lớp 2 |
| HDBank (HDB) — Nhóm B | Trích dẫn | hdbank.com.vn, mục Nhà đầu tư (Báo cáo tài chính, Báo cáo thường niên, ĐHCĐ) | BCTC quý hợp nhất; deck IR quý tiếng Anh; BCTN | Quý | Top 9 tổng tài sản 6T/2026. Hợp nhất gồm HD SAISON, dùng số riêng lẻ cho bán lẻ. Đường kéo chính: finance.vietstock.vn/{mã}/tai-tai-lieu.htm (aggregator, mục 3.3). Trang IR chính thức ở cột URL dùng để đối chiếu nguồn gốc; DA verify URL con lần cuối khi cấu hình |
| SHB — Nhóm B | Trích dẫn | shb.com.vn, mục Nhà đầu tư / Quan hệ cổ đông | BCTC quý; BCTN; tài liệu ĐHCĐ | Quý | Top 10 tổng tài sản. Nặng bán buôn, ít tách bán lẻ, gắn nhãn proxy toàn hàng. Đường kéo chính: finance.vietstock.vn/{mã}/tai-tai-lieu.htm (aggregator, mục 3.3). DA verify URL con lần cuối khi cấu hình |
| LPBank (LPB) — Nhóm B | Trích dẫn | lpbank.com.vn, mục Nhà đầu tư | BCTC quý; BCTN; tài liệu ĐHCĐ | Quý | Trên 500 nghìn tỷ tổng tài sản. Mạng lưới bưu điện, benchmark mass và nông thôn. Đường kéo chính: finance.vietstock.vn/{mã}/tai-tai-lieu.htm (aggregator, mục 3.3). DA verify URL con lần cuối khi cấu hình |
| MSB — Nhóm B | Trích dẫn | msb.com.vn, mục Nhà đầu tư | BCTC quý; tài liệu KQKD; BCTN | Quý | Có công bố CASA và thu phí khá rõ trong tài liệu KQKD. Đường kéo chính: finance.vietstock.vn/{mã}/tai-tai-lieu.htm (aggregator, mục 3.3). DA verify URL con lần cuối khi cấu hình |
| SeABank (SSB) — Nhóm B | Trích dẫn | seabank.com.vn, mục Nhà đầu tư | BCTC quý; BCTN; tài liệu ĐHCĐ | Quý | Đường kéo chính: finance.vietstock.vn/{mã}/tai-tai-lieu.htm (aggregator, mục 3.3). DA verify URL con lần cuối khi cấu hình |
| OCB — Nhóm B | Trích dẫn | ocb.com.vn, mục Nhà đầu tư | BCTC quý; deck IR quý; BCTN | Quý | Có deck IR quý tiếng Anh, tách retail ở mức tổng. Đường kéo chính: finance.vietstock.vn/{mã}/tai-tai-lieu.htm (aggregator, mục 3.3). DA verify URL con lần cuối khi cấu hình |
| ABBank (ABB) — Nhóm B | Trích dẫn | abbank.vn, mục Nhà đầu tư | BCTC quý; BCTN; tài liệu ĐHCĐ | Quý | Ngân hàng duy nhất tăng tài sản hai chữ số quý I/2026 (13%). Niêm yết UPCoM. Đường kéo chính: finance.vietstock.vn/{mã}/tai-tai-lieu.htm (aggregator, mục 3.3). DA verify URL con lần cuối khi cấu hình |

### 3.3. Aggregator và dữ liệu toàn hệ thống

| Nguồn | Vai trò | URL | Dữ liệu kéo | Tần suất | Truy cập và ghi chú |
|---|---|---|---|---|---|
| VietstockFinance (tab Tải tài liệu) | Aggregator | finance.vietstock.vn/{mã}/tai-tai-lieu.htm với mã tcb, vcb, bid, ctg, mbb, vpb, acb, tpb, vib (Nhóm A) và hdb, shb, lpb, msb, ssb, ocb, abb (Nhóm B). Với Nhóm B, Vietstock là đường kéo chính | BCTC, nghị quyết HĐQT, tài liệu và nghị quyết ĐHCĐ, báo cáo thường niên, giải trình KQKD (tài liệu gốc do ngân hàng phát hành) | Sự kiện | Danh sách tài liệu crawl được; một số trường số liệu cần đăng nhập thì bỏ qua. Metadata ghi nguồn là tài liệu gốc của ngân hàng |
| SBV — cổng mới | Trích dẫn | sbv.gov.vn (mục hệ thống TCTD, mục lãi suất) | Chỉ tiêu cơ bản hệ thống TCTD, LDR, nợ xấu, thống kê lãi suất, tin công bố tăng trưởng tín dụng, room tín dụng | Tháng | Cấu trúc web đã thay đổi: các URL webcenter cũ đã chết, không cấu hình theo link cũ |
| SBV — phân hệ thống kê | Trích dẫn | dttkt.sbv.gov.vn | Bảng chuỗi thời gian: tổng phương tiện thanh toán, tiền gửi khách hàng tại TCTD | Tháng (trễ 2-3 tháng) | Chặn bot (robots). Không crawl. Tải thủ công hàng tháng và nạp qua data/manual/G02 theo đúng phương án BRD |

### 3.4. Banca APE — ngoài scope agent, nạp từ báo cáo IAV

- Cập nhật 04/09/2026: Head of Insurance nhận định kỳ báo cáo của Hiệp hội Bảo hiểm Việt Nam (IAV) có số theo từng ngân hàng và tổng thị trường. Đây là nguồn duy nhất cho chỉ số Banca APE; agent không quét chỉ số này dưới bất kỳ hình thức nào.
- **Xử lý**: báo cáo IAV nạp tay qua đường data/manual, gắn nhãn nguồn "IAV qua Head of Insurance", ghi kỳ tham chiếu và ngày nhận. Bỏ hẳn crawler iav.vn khỏi Phase 1; iav.vn xóa khỏi danh sách nguồn cấu hình của agent.
- Bài APE trên báo chuyên ngành (Tin nhanh chứng khoán và tương tự) không dùng, kể cả để dò; nếu số báo chí lệch với báo cáo IAV thì báo cáo IAV thắng.

---

## 4. Lớp 2 — CVP, offering và mô hình bán hàng theo phân khúc

Đối tượng quét đầy đủ (trang tin, biểu phí, app release notes): 8 ngân hàng Nhóm A (VCB, BIDV, VietinBank, MBB, VPBank, ACB, TPBank, VIB). Nhóm B (HDBank, SHB, LPBank, MSB, SeABank, OCB, ABBank): chỉ quét trang tin và khuyến mại chính thức, tần suất tháng, không kéo app store và biểu phí ở MVP0.

Trọng tâm benchmark: VCB, BIDV, VietinBank cho HNW/Private và AFF; VPBank, TPBank, VIB cho MAF/EMAF và thẻ tín dụng; MBB, ACB cho Merchants và SME. Phân khúc bám cấu trúc slide: HNW/Private, AFF, MAF/EMAF, Merchants, SME.

| Nguồn | Vai trò | URL | Dữ liệu kéo | Tần suất | Truy cập và ghi chú |
|---|---|---|---|---|---|
| Trang tin tức và khuyến mại chính thức của từng ngân hàng | Trích dẫn | Mục Tin tức / Khuyến mại trên site chính. Nhóm A: portal.vietcombank.com.vn; bidv.com.vn/vn/; vietinbank.vn; mbbank.com.vn; vpbank.com.vn; acb.com.vn; tpb.vn; vib.com.vn. Nhóm B (tần suất tháng): hdbank.com.vn; shb.com.vn; lpbank.com.vn; msb.com.vn; seabank.com.vn; ocb.com.vn; abbank.vn | Ra mắt sản phẩm, CVP mới, đặc quyền theo phân khúc, hợp tác đối tác, chương trình ưu đãi | Tuần | HTML mở, crawl được. Đây là công bố chính thức của đối thủ nên hợp lệ theo R-G03 |
| Biểu phí và điều khoản điều kiện | Trích dẫn | Trang biểu phí và T&C của từng ngân hàng (ví dụ vpbank.com.vn/-/media/... cho file PDF) | Phí dịch vụ, lãi suất niêm yết, điều kiện gói sản phẩm theo phân khúc | Tháng | PDF và HTML mở; so sánh kỳ này với kỳ trước để bắt thay đổi |
| Google Play và Apple App Store — release notes | Trích dẫn | Trang ứng dụng của Techcombank Mobile, VCB Digibank, BIDV SmartBanking, VietinBank iPay, MBBank, VPBank NEO, ACB ONE, TPBank, MyVIB | Ghi chú phiên bản (tính năng mới do ngân hàng tự công bố), lịch sử cập nhật | Tuần | Crawl được nhưng phải rate-limit. Release notes là công bố của ngân hàng nên trích dẫn được |
| Google Play và App Store — review người dùng | Tín hiệu dò | Cùng trang ứng dụng trên | Cảm nhận người dùng về tính năng, sự cố | Không nạp | Nội dung do người dùng tạo, không phải công bố chính thức. MVP0 không nạp; cân nhắc lại ở MVP1 với khung riêng |
| Trang tuyển dụng (VietnamWorks, TopCV) | Tín hiệu dò | vietnamworks.com; topcv.vn | Tín hiệu mở rộng đội RM, private banking, merchant qua tin tuyển dụng | Không nạp | Chỉ dò thủ công ngoài hệ thống. LinkedIn yêu cầu đăng nhập và hạn chế crawl: loại khỏi MVP0 |

---

## 5. Lớp 3 — Hồ sơ chiến lược từng ngân hàng

| Nguồn | Vai trò | URL | Dữ liệu kéo | Tần suất | Truy cập và ghi chú |
|---|---|---|---|---|---|
| Báo cáo thường niên và tài liệu ĐHCĐ 16 ngân hàng | Trích dẫn | Trang IR từng ngân hàng ở mục 3.2, hoặc tải qua Vietstock aggregator ở mục 3.3 | Định hướng chiến lược, số lượng khách hàng cá nhân, cơ cấu thu phí, công bố công nghệ (core banking, open API, super app, BaaS, đối tác ví), phát ngôn lãnh đạo | Năm (ĐHCĐ quý 2, BCTN quý 1-2) | PDF. Kéo một lần mỗi năm và khi có tài liệu ĐHCĐ bất thường |
| Báo cáo phân tích công ty chứng khoán (SSI, VNDirect, VCBS, BSC) | Trích dẫn (Tier 2) | SSI: PDF công khai trên ftp2.ssi.com.vn và mục phân tích ssi.com.vn; VNDirect: vndirect.com.vn/category/bao-cao-phan-tich/; VCBS: vcbs.com.vn/trung-tam-phan-tich; BSC: bsc.com.vn | Nhận định phân tích, dự phóng, so sánh ngành ngân hàng | Sự kiện | Chỉ lấy PDF công khai, bỏ phần sau đăng nhập. Là Tier 2 (nhận định analyst): mọi số dự phóng gắn nhãn forecast kèm tên tổ chức theo R-F04, tách [Nhận định] khỏi [Fact] theo R-F07 |
| Tạp chí Ngân hàng (J02), Tạp chí Tài chính (J03) | Trích dẫn | tapchinganhang.gov.vn; tapchitaichinh.vn | Phân tích chính sách tiền tệ, tài khóa từ cơ quan nhà nước | Tháng | Đã có trong whitelist spec sheet 04 |
| Báo chuyên ngành tài chính (VnEconomy J01, Vietstock news, Tin nhanh chứng khoán) | Tín hiệu dò | vneconomy.vn; vietstock.vn; tinnhanhchungkhoan.vn | Dò sự kiện: thay đổi lãnh đạo, thương vụ, công bố công nghệ | Không nạp | Đúng quy tắc J01 đã chốt: chỉ dẫn tin, số liệu phải truy về nguồn gốc chính thức. CafeF thuộc domain cấm, không dùng kể cả để dò trong hệ thống |

---

## 6. Lớp 4 — Vĩ mô, chính phủ, PEST

### 6.1. Chính sách tiền tệ và tín dụng

| Nguồn | Vai trò | URL | Dữ liệu kéo | Tần suất | Truy cập và ghi chú |
|---|---|---|---|---|---|
| SBV — văn bản pháp lý và điều hành | Trích dẫn | sbv.gov.vn (mục văn bản, tin điều hành) | Thông tư về cho vay BĐS, cơ chế room tín dụng, trần lãi suất, chỉ tiêu tăng trưởng tín dụng năm | Tháng + sự kiện | Văn bản đang hiệu lực cần cấu hình theo dõi: Thông tư 08/2026/TT-NHNN; Công văn 4551/NHNN-CSTT (hiệu lực hết 2026, loại cho vay NOXH/KCN khỏi kiểm soát tín dụng BĐS); cơ chế phân bổ room theo Thông tư 52/2018. Lưu ý: lộ trình thí điểm bỏ room từ 2026 là định hướng, chưa phải kết quả, gắn nhãn forward-looking |
| Thư viện Pháp luật / LuatVietnam | Aggregator | thuvienphapluat.vn; luatvietnam.vn | Tra cứu và theo dõi văn bản theo số hiệu; văn bản trích dẫn là văn bản gốc của cơ quan ban hành | Sự kiện | Toàn văn một số văn bản cần đăng ký; dùng để phát hiện và định vị, metadata ghi số hiệu văn bản gốc |

### 6.2. Định hướng phát triển của Chính phủ

| Nguồn | Vai trò | URL | Dữ liệu kéo | Tần suất | Truy cập và ghi chú |
|---|---|---|---|---|---|
| Cổng TTĐT Chính phủ | Trích dẫn | chinhphu.vn | Nghị quyết, nghị định về đầu tư công, nhà ở xã hội, kinh tế tư nhân, chuyển đổi số | Tháng + sự kiện | Văn bản cần theo dõi sẵn: Nghị định 94/2025 (sandbox fintech: P2P lending, chấm điểm tín dụng, Open API); Nghị quyết 57-NQ/TW; Luật Dữ liệu và Trung tâm Dữ liệu quốc gia; định danh điện tử VNeID |

### 6.3. Thu nhập và hành vi tiêu dùng

| Nguồn | Vai trò | URL | Dữ liệu kéo | Tần suất | Truy cập và ghi chú |
|---|---|---|---|---|---|
| Cục Thống kê (GSO cũ) | Trích dẫn | gso.gov.vn (mục số liệu thống kê, tài khoản quốc gia) | Thu nhập và chi tiêu hộ gia đình (VHLSS), CPI, GDP, lao động | Tháng (CPI), Quý (GDP), Năm (VHLSS) | Đã tổ chức lại thành Cục Thống kê thuộc Bộ Tài chính nhưng website gso.gov.vn vẫn hoạt động; HTML và Excel mở, crawl được |
| Chính sách thuế TNCN | Trích dẫn | Văn bản gốc: Nghị quyết 110/2025/UBTVQH15 và Luật Thuế TNCN 109/2025 (định vị qua thuvienphapluat) | Mức giảm trừ gia cảnh mới từ 2026 (bản thân 15,5 triệu/tháng, người phụ thuộc 6,2 triệu/tháng), biểu thuế 5 bậc | Sự kiện | Tác động trực tiếp thu nhập khả dụng, đầu vào cho luận điểm hành vi tiêu dùng |
| Nghiên cứu người tiêu dùng (Cimigo, Decision Lab, Q&Me) | Trích dẫn (Tier 2) | cimigo.com (có báo cáo retail banking miễn phí); decisionlab.co; qandme.net | Hành vi Gen X/Y/Z, lifestyle banking, khảo sát công khai | Quý | Chỉ dùng phần công bố miễn phí; là Tier 2, tách [Nhận định], ghi rõ mẫu khảo sát |

### 6.4. AI trong ngân hàng và tài chính xanh

| Nguồn | Vai trò | URL | Dữ liệu kéo | Tần suất | Truy cập và ghi chú |
|---|---|---|---|---|---|
| VNBA và VietFintech | Trích dẫn | vnba.org.vn | Diễn biến open banking, AI trong ngân hàng, bình luận Nghị định 94 | Tháng | Đã có trong whitelist (N02) |
| Tín dụng xanh | Trích dẫn | Tin công bố chính thức trên sbv.gov.vn; tapchinganhang.gov.vn | Số liệu dư nợ tín dụng xanh do SBV công bố; Quyết định 21/2025 (danh mục xanh quốc gia); Thông tư 17/2022 (quản lý rủi ro môi trường) | Quý | Số tín dụng xanh chỉ lấy từ phát ngôn và tin chính thức của SBV, không lấy qua báo phổ thông |

---

## 7. Lịch kéo và lộ trình dựng MVP0

- **Phase 1 (dựng trước)**: Lớp 1. Crawler 8 trang IR Nhóm A + Vietstock tab tài liệu cho 15 mã (Nhóm A và Nhóm B), lịch quý bám cửa sổ 15-40 ngày sau kỳ. SBV thống kê: quy trình tải tay hàng tháng nạp qua data/manual/G02. Banca APE: không crawler; nạp tay từ báo cáo IAV theo mục 3.4.
- **Phase 2**: Lớp 2 và 3. Crawl tuần trang tin và khuyến mại + release notes app store (rate-limit). Báo cáo thường niên và ĐHCĐ kéo theo sự kiện. PDF công khai của công ty chứng khoán kéo theo sự kiện.
- **Phase 3**: Lớp 4. Quét tháng sbv.gov.vn, chinhphu.vn, gso.gov.vn; theo dõi văn bản theo số hiệu, bắn cờ khi có văn bản mới thuộc danh sách theo dõi.

---

## 8. Ràng buộc kỹ thuật và tuân thủ

- Tôn trọng robots.txt của mọi site ngân hàng và cơ quan nhà nước; nguồn chặn bot (dttkt.sbv.gov.vn) chuyển hẳn sang đường nạp tay, không lách.
- Rate-limit khi kéo app store và các portal ngân hàng; crawler có retry và log lần chạy theo R-F01.
- Không thu thập dữ liệu cá nhân dưới mọi hình thức (Nghị định 13/2023 về bảo vệ dữ liệu cá nhân); chỉ kéo dữ liệu doanh nghiệp và thị trường công khai.
- Mỗi bản ghi bắt buộc đủ metadata: mã nguồn, URL, kỳ tham chiếu, ngày lấy, cơ sở riêng lẻ hay hợp nhất, nhãn actual hoặc proxy hoặc forecast (kèm tổ chức dự báo).
- Bản ghi từ domain cấm hoặc thiếu kỳ tham chiếu: từ chối nạp và ghi log lý do.
- Trước khi cấu hình crawler cho cơ quan nhà nước, verify lại URL lần cuối vì đợt sắp xếp bộ máy 2025 làm nhiều đường dẫn thay đổi (đã ghi chú trong sheet 04).

---

## 9. Nhật ký thay đổi phiên bản 2.1 đến 2.8 (04/09/2026)

- Mở rộng đối tượng benchmark từ 5 lên top 20 ngân hàng theo tổng tài sản (BCTC 30/06/2026), chia Nhóm A (Big 4 + đối thủ trực tiếp retail: thêm VietinBank, Agribank, TPBank, VIB; VPBank nâng lên cả Lớp 1) và Nhóm B (ngân hàng theo quy mô: HDBank, SHB, LPBank, MSB, SeABank, OCB, Nam A Bank, ABBank). Nhóm B kéo Lớp 1 và 3 qua Vietstock là chính; Lớp 2 chỉ trang tin tháng. Ảnh hưởng: mục 1, 3, 3.2, 3.3, 4, 5, 7.
- Banca APE: chuyển hẳn sang nguồn báo cáo IAV do Head of Insurance cung cấp, nạp tay; bỏ crawler iav.vn và mọi tín hiệu dò báo chí về APE. Ảnh hưởng: mục 3.1, 3.4, 7.
- Lưu ý cho DA: VPBank hợp nhất gồm FE Credit và HDBank hợp nhất gồm HD SAISON nên dùng số riêng lẻ cho chỉ số bán lẻ.
- Phiên bản 2.2: thêm mục 10 định nghĩa đầu ra Excel (11 tab sản phẩm, 4 tab PEST theo segment, Banks, Sources, README) khớp hai slide template workshop PRBG.
- Phiên bản 2.3: loại Sacombank và Eximbank (đang tái cấu trúc, số liệu biến động mạnh giữa các kỳ, làm nhiễu benchmark). Danh sách còn 18 đối thủ + TCB. Tiêu chí loại ghi ở mục 1 để áp dụng cho các kỳ sau.
- Phiên bản 2.4: chốt 6 tab sản phẩm (CASA gồm debit card, TD, Unsecured Lending, Credit Card, Secured Lending, Wealth); thêm Tier_Mapping và 3 tab tier benefits theo hạng TCB. Mẫu Excel lên v0.3.
- Phiên bản 2.5: Tier_Mapping cập nhật từ research đầy đủ 18 ngân hàng (04/09/2026); loại Agribank và Bac A Bank khỏi scope tier benefits (không có chương trình phân hạng công bố, vẫn giữ ở Lớp 1). Mẫu Excel lên v0.4.
- Phiên bản 2.6: loại thêm Nam A Bank khỏi scope tier benefits (không có T&C công bố). Scope tier chốt 15 ngân hàng. Mẫu Excel lên v0.5.
- Phiên bản 2.7: bổ sung quy tắc tier mapping (Q1 đến Q4) vào mục 10 và tham chiếu file Tier-Mapping-Logic-and-Decisions-2026-09-04.md; Excel v0.6 thêm cột Mỏ neo và Cờ trong Tier_Mapping.
- Phiên bản 2.8: chốt MỘT danh sách 15 đối thủ + TCB dùng cho mọi lớp và mọi tab. Agribank, Bac A Bank, Nam A Bank loại hẳn khỏi danh sách (trước đó chỉ loại khỏi scope tier), để danh sách Lớp 1 và tier benefits trùng nhau. Excel v0.7 đồng bộ tab Banks.
- Tác động spec: cần bump whitelist sheet 04 (thêm domain 10 ngân hàng mới, xóa iav.vn) và BRD 21/08/2026 lên phiên bản kế tiếp trước khi Bách cấu hình crawler.

---

## 10. Đầu ra MVP0: mẫu Excel để fill slide workshop

- **Định dạng**: một file Excel theo mẫu "MVP0-Market-Insights-Output-Template-v1.1.xlsx" đi kèm tài liệu này. Agent ghi dữ liệu thô vào các ô nền trắng; CVM điền các cột nền vàng (strength, weakness, implication, review). Mẫu này fill trực tiếp hai slide của workshop PRBG: slide CVP và offering theo ngân hàng, slide Market overview (PEST).
- **Tab sản phẩm (6 tab đã chốt)**: CASA (gồm tài khoản thanh toán, tài khoản lương, sinh lời tự động và thẻ ghi nợ), TD, Unsecured_Lending, Credit_Card, Secured_Lending, Wealth. Mỗi dòng là một ngân hàng x một gói/offering, gồm positioning (claim nguyên văn), CVP chính, headline pricing, điều kiện, evidence, và đủ metadata nguồn.
- **Tab PEST (4 tab, mỗi tab một segment)**: PEST_MAFF, PEST_SME, PEST_PnP, PEST_Household. Mỗi dòng là một driver có nhóm P/E/S/T, chỉ số theo dõi, giá trị và thay đổi so kỳ trước, chiều tác động lên danh mục khách hàng, sản phẩm chịu ảnh hưởng, horizon 2027, và đủ metadata nguồn. Cột "Ưu tiên lên slide" do CVM chọn để ra 4 caption.
- **Tab tier benefits**: Tier_Mapping là kết quả research 18 ngân hàng (04/09/2026) map hạng khách hàng TCB (Inspire, Priority, Private) với hạng của từng đối thủ theo ngưỡng tài sản công bố, kèm độ tin cậy và việc cần verify. Scope tier trùng danh sách chốt 15 đối thủ ở mục 1; 3 tab Tier_Inspire, Tier_Priority, Tier_Private liệt kê quyền lợi TCB so với đối thủ ở hạng tương đương (1 dòng = 1 ngân hàng x 1 quyền lợi, 14 nhóm quyền lợi chuẩn hóa; pivot theo ngân hàng để ra bảng so sánh). Agent chỉ kéo trang hội viên và T&C hội viên chính thức của từng ngân hàng cho phần này. Tab hỗ trợ: Banks (16 ngân hàng gồm TCB, dropdown), Sources (source_id khớp danh mục này), README (quy ước, mapping slide, bảng đếm dòng).
- **Quy tắc tier mapping** (chi tiết và quyết định từng ngân hàng trong file tham chiếu "Tier-Mapping-Logic-and-Decisions-2026-09-04.md"): dải map theo AUM của TCB (Inspire 200 triệu đến dưới 1 tỷ, Priority 1 đến dưới 23 tỷ, Private từ 23 tỷ).
  - **Q1**: chọn mỏ neo là tiêu chí asset stock gần định nghĩa AUM nhất, ưu tiên tổng tài sản rồi tiền gửi rồi CASA; tiêu chí dòng chảy (lương, chi tiêu thẻ, dư nợ, phí bảo hiểm) không dùng để xếp dải.
  - **Q2**: so theo mặt số, không quy đổi giữa các loại tiêu chí.
  - **Q3**: khi tiêu chí hẹp hơn AUM làm đối dải thì gắn cờ cắt ngang và ghi ở cả hai dải, không phán đoán; chiều sai số luôn là đánh giá thấp đối thủ.
  - **Q4**: không hiệu chỉnh kỳ bình quân, giữ cột riêng.

  Tab Tier_Mapping có cột "Mỏ neo (Q1)" và "Cờ (Q3)" cho từng hạng. Hai cờ nghiệp vụ quan trọng: hạng "Private" của TPBank ngưỡng 20 tỷ vẫn thuộc dải Priority; chỉ SHB Super Premier và MB Private (chưa có T&C) chạm dải Private.
